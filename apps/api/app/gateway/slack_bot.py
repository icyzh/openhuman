"""
Slack bot — one Socket Mode connection per AI employee.

An ``EmployeeSlackBot`` handles events for a **single** AI employee with
its own Slack app identity (Pattern A).  Each employee gets its own bot
user, sidebar entry, @mention, DMs, and avatar/name — no shared tokens.

When ``SLACK_IDENTITY_MODE=shared`` (legacy), the old ``WorkspaceSlackBot``
path in ``manager.py`` is used instead.
"""

from __future__ import annotations

import logging
from uuid import UUID

from langchain_core.messages import HumanMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from sqlalchemy import select

from app.agent.router import get_graph_for_employee
from app.channel_assignments.models import ChannelAssignment
from app.core.database import async_session_factory
from app.employees.models import Employee
from app.memory.service import remember
from app.organizations.models import Organization

logger = logging.getLogger(__name__)

_SAFE_ERROR_MESSAGE = (
    "I ran into a problem processing your request. Please try again later."
)


class EmployeeSlackBot:
    """One Slack Socket Mode connection per AI employee.

    Each employee has its own Slack app identity (its own ``xoxb-`` bot token
    and ``xapp-`` app-level token).  The bot responds in all channels by
    default; if the employee has ``channel_assignments`` those act as an
    allowlist — only messages in assigned channels (and DMs) are processed.
    """

    def __init__(
        self,
        employee_id: UUID,
        bot_token: str,
        app_token: str,
    ) -> None:
        self.employee_id = employee_id
        self.bot_token = bot_token
        self.app_token = app_token

        self.app = AsyncApp(token=bot_token)
        self._handler = AsyncSocketModeHandler(self.app, app_token)
        self.bot_user_id: str | None = None

        # Register event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.event("message")(self.handle_message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the Socket Mode WebSocket connection."""
        await self._handler.connect_async()
        try:
            auth_res = await self.app.client.auth_test()
            self.bot_user_id = auth_res.get("user_id")
        except Exception:
            logger.exception("Failed to fetch bot user_id on connection")
            self.bot_user_id = None
        logger.info(
            "EmployeeSlackBot connected (employee=%s, bot_user_id=%s)",
            self.employee_id,
            self.bot_user_id,
        )

    async def disconnect(self) -> None:
        """Close the Socket Mode WebSocket connection."""
        try:
            await self._handler.close_async()
        except Exception:
            logger.exception("Error closing EmployeeSlackBot Socket Mode connection")
        logger.info(
            "EmployeeSlackBot disconnected (employee=%s)",
            self.employee_id,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def handle_mention(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Respond to @mentions in public channels."""
        await self._process_slack_message(event, say)

    async def handle_message(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Respond to DMs, or thread replies where the bot is already participating."""
        channel_type = event.get("channel_type")
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        ts = event.get("ts")

        # 1. Direct Message (DM)
        if channel_type == "im":
            await self._process_slack_message(event, say)
            return

        # 2. Thread reply in a channel/group (without needing a direct mention)
        if thread_ts and thread_ts != ts and channel:
            text = event.get("text", "")
            # Skip if the message contains a direct mention (let handle_mention respond)
            if self.bot_user_id and f"<@{self.bot_user_id}>" in text:
                return

            try:
                replies = await self.app.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=50,
                )
                messages = replies.get("messages", [])
                bot_participated = any(
                    msg.get("user") == self.bot_user_id or msg.get("bot_id") is not None
                    for msg in messages
                )
                if bot_participated:
                    await self._process_slack_message(event, say)
            except Exception:
                logger.exception("Error checking thread participation for message event")

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_slack_message(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Process an incoming Slack event for this employee."""
        # Ignore messages from other bots (including ourselves)
        if "bot_id" in event:
            return

        text = event.get("text", "").strip()
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        is_dm = event.get("channel_type") == "im"

        # If employee has channel assignments, only respond in assigned channels
        if not is_dm and not await self._is_channel_allowed(channel):
            logger.debug(
                "Channel %s is not assigned to employee %s — ignoring",
                channel,
                self.employee_id,
            )
            return

        # Run the agent
        response_text = await self._run_agent(text)
        if not response_text:
            response_text = "I processed your request but had no response."

        # Reply in thread — bot's display name is already correct (set at provisioning)
        await say(
            text=response_text,
            channel=channel,
            thread_ts=thread_ts,
        )

    # ------------------------------------------------------------------
    # Channel allowlist
    # ------------------------------------------------------------------

    async def _is_channel_allowed(self, channel_id: str) -> bool:
        """Return ``True`` if this employee should respond in *channel_id*.

        If the employee has **no** Slack channel assignments, all channels
        are allowed.  Otherwise only assigned channels pass.
        """
        async with async_session_factory() as session:
            any_assignments = await session.scalar(
                select(ChannelAssignment).where(
                    ChannelAssignment.platform == "slack",
                    ChannelAssignment.employee_id == self.employee_id,
                ).limit(1)
            )
            if any_assignments is None:
                # No assignments → unrestricted, respond everywhere
                return True

            # Has assignments → check for this specific channel
            result = await session.execute(
                select(ChannelAssignment).where(
                    ChannelAssignment.platform == "slack",
                    ChannelAssignment.channel_id == channel_id,
                    ChannelAssignment.employee_id == self.employee_id,
                )
            )
            return result.scalars().first() is not None

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(self, content: str) -> str:
        """Run the LangGraph agent as this employee.

        Never leaks raw exception details — returns a safe fallback on failure.
        """
        initial_state = {
            "messages": [HumanMessage(content=content)],
            "platform": "slack",
            "employee_id": str(self.employee_id),
            "tool_round": 0,
        }

        try:
            async with async_session_factory() as session:
                graph, all_tools = await get_graph_for_employee(
                    session, self.employee_id,
                )
                config = {
                    "configurable": {
                        "db": session,
                        "employee_id": str(self.employee_id),
                        "all_tools": all_tools,
                    }
                }
                result = await graph.ainvoke(initial_state, config=config)
                return result.get("response", "")
        except Exception:
            logger.exception(
                "Agent graph failed for employee %s on Slack", self.employee_id,
            )
            return _SAFE_ERROR_MESSAGE


class WorkspaceSlackBot:
    """Legacy shared-mode Slack bot — one Socket Mode connection per unique
    bot token, routing messages to multiple employees via channel assignments.

    Only used when ``SLACK_IDENTITY_MODE=shared``.  When ``per_employee`` mode
    is active, :class:`EmployeeSlackBot` is used instead (one per employee).
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        employee_ids: list[UUID],
    ) -> None:
        self.bot_token = bot_token
        self.app_token = app_token
        self.employee_ids = employee_ids
        self._employee_id_set = frozenset(employee_ids)

        self.app = AsyncApp(token=bot_token)
        self._handler = AsyncSocketModeHandler(self.app, app_token)
        self.bot_user_id: str | None = None

        # Register event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.event("message")(self.handle_message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the Socket Mode WebSocket connection."""
        await self._handler.connect_async()
        try:
            auth_res = await self.app.client.auth_test()
            self.bot_user_id = auth_res.get("user_id")
        except Exception:
            logger.exception("Failed to fetch bot user_id on connection")
            self.bot_user_id = None
        logger.info(
            "WorkspaceSlackBot connected (token=...%s, employees=%d, bot_user_id=%s)",
            self.bot_token[-8:],
            len(self.employee_ids),
            self.bot_user_id,
        )

    async def disconnect(self) -> None:
        """Close the Socket Mode WebSocket connection."""
        try:
            await self._handler.close_async()
        except Exception:
            logger.exception("Error closing WorkspaceSlackBot Socket Mode connection")
        logger.info(
            "WorkspaceSlackBot disconnected (token=...%s)",
            self.bot_token[-8:],
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def handle_mention(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Respond to @mentions in public channels."""
        await self._process_slack_message(event, say)

    async def handle_message(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Respond to DMs, or thread replies where the bot is already participating."""
        channel_type = event.get("channel_type")
        thread_ts = event.get("thread_ts")
        channel = event.get("channel")
        ts = event.get("ts")

        if channel_type == "im":
            await self._process_slack_message(event, say)
            return

        if thread_ts and thread_ts != ts and channel:
            text = event.get("text", "")
            if self.bot_user_id and f"<@{self.bot_user_id}>" in text:
                return
            try:
                replies = await self.app.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=50,
                )
                messages = replies.get("messages", [])
                bot_participated = any(
                    msg.get("user") == self.bot_user_id or msg.get("bot_id") is not None
                    for msg in messages
                )
                if bot_participated:
                    await self._process_slack_message(event, say)
            except Exception:
                logger.exception("Error checking thread participation for message event")

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_slack_message(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Route an incoming Slack event to the right employee and respond."""
        if "bot_id" in event:
            return

        text = event.get("text", "").strip()
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        is_dm = event.get("channel_type") == "im"

        employee_id = await self._resolve_employee(channel if not is_dm else None)
        if employee_id is None:
            logger.debug(
                "No employee assigned for channel=%s (token=...%s) — ignoring",
                channel,
                self.bot_token[-8:],
            )
            return

        employee_name = "OpenHuman Agent"
        async with async_session_factory() as session:
            emp = await session.get(Employee, employee_id)
            if emp:
                if emp.role:
                    employee_name = f"{emp.name} ({emp.role})"
                else:
                    employee_name = emp.name

                # ── Auto-ingest Slack message into org memory ────────────
                try:
                    org = await session.scalar(
                        select(Organization).where(
                            Organization.id == emp.org_id
                        )
                    )
                    if (
                        org
                        and org.cognee_dataset_name
                        and org.cognee_system_user_id
                    ):
                        speaker = event.get("user", "unknown")
                        ch = event.get("channel", "unknown")
                        ts = event.get("ts", "")
                        ingest_text = (
                            f"Slack message from <@{speaker}> "
                            f"in <#{ch}> at {ts}:\n{text}"
                        )
                        await remember(
                            ingest_text,
                            org.cognee_dataset_name,
                            org.cognee_system_user_id,
                            dataset_id=org.cognee_dataset_id,
                            background=True,
                        )
                except Exception:
                    logger.debug(
                        "Slack message Cognee ingest skipped for employee %s",
                        employee_id,
                        exc_info=True,
                    )
                # ── End auto-ingest ──────────────────────────────────────

        response_text = await self._run_agent(employee_id, text)
        if not response_text:
            response_text = "I processed your request but had no response."

        await say(
            text=response_text,
            channel=channel,
            thread_ts=thread_ts,
            username=employee_name,
        )

    # ------------------------------------------------------------------
    # Channel → Employee routing
    # ------------------------------------------------------------------

    async def _resolve_employee(self, channel_id: str | None) -> UUID | None:
        """Return the employee UUID for *channel_id*, or ``None``."""
        async with async_session_factory() as session:
            if channel_id is not None:
                result = await session.execute(
                    select(ChannelAssignment).where(
                        ChannelAssignment.platform == "slack",
                        ChannelAssignment.channel_id == channel_id,
                        ChannelAssignment.employee_id.in_(self._employee_id_set),
                    )
                )
                ca = result.scalars().first()
                if ca is not None:
                    return ca.employee_id

                any_assignments = await session.scalar(
                    select(ChannelAssignment).where(
                        ChannelAssignment.platform == "slack",
                        ChannelAssignment.employee_id.in_(self._employee_id_set),
                    ).limit(1)
                )
                if any_assignments is not None:
                    return None

            if self.employee_ids:
                return await self._find_unrestricted_employee(session)

            return None

    async def _find_unrestricted_employee(self, session) -> UUID | None:
        """Return first candidate with no Slack channel assignments."""
        assigned_ids: set[UUID] = set()
        result = await session.execute(
            select(ChannelAssignment.employee_id).where(
                ChannelAssignment.platform == "slack",
                ChannelAssignment.employee_id.in_(self._employee_id_set),
            ).distinct()
        )
        assigned_ids = {row[0] for row in result.all()}

        for eid in self.employee_ids:
            if eid not in assigned_ids:
                return eid

        return self.employee_ids[0] if self.employee_ids else None

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(self, employee_id: UUID, content: str) -> str:
        """Run the LangGraph agent as *employee_id*."""
        initial_state = {
            "messages": [HumanMessage(content=content)],
            "platform": "slack",
            "employee_id": str(employee_id),
            "tool_round": 0,
        }

        try:
            async with async_session_factory() as session:
                graph, all_tools = await get_graph_for_employee(
                    session, employee_id,
                )
                config = {
                    "configurable": {
                        "db": session,
                        "employee_id": str(employee_id),
                        "all_tools": all_tools,
                    }
                }
                result = await graph.ainvoke(initial_state, config=config)
                return result.get("response", "")
        except Exception:
            logger.exception(
                "Agent graph failed for employee %s on Slack", employee_id,
            )
            return _SAFE_ERROR_MESSAGE
