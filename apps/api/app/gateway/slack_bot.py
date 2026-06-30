"""
Slack bot — one Socket Mode connection per unique bot token.

A single ``WorkspaceSlackBot`` handles events for **all** employees that
share the same bot token (i.e. all employees in the same Slack workspace).
When a message arrives it looks up the ``channel_assignments`` table to
decide *which* employee should respond, then invokes the agent graph as
that employee.

This avoids the event-distribution problem that occurs when multiple
Socket Mode connections share one bot token (Slack sends each event to
only one connection; if that connection belongs to an employee not
assigned to the channel the message is silently dropped).
"""

from __future__ import annotations

import logging
from uuid import UUID

from langchain_core.messages import HumanMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from sqlalchemy import select

from app.agent.router import agent_graph
from app.channel_assignments.models import ChannelAssignment
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)

_SAFE_ERROR_MESSAGE = (
    "I ran into a problem processing your request. Please try again later."
)


class WorkspaceSlackBot:
    """One Slack Socket Mode connection per unique bot token.

    Routes incoming messages to the correct employee based on
    ``channel_assignments``, falling back to an unrestricted employee
    (one with no assignments) when no explicit assignment matches.
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
        self.bot_user_id = None

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
            "Slack Socket Mode connected (token=...%s, employees=%d, bot_user_id=%s)",
            self.bot_token[-8:],
            len(self.employee_ids),
            self.bot_user_id,
        )

    async def disconnect(self) -> None:
        """Close the Socket Mode WebSocket connection."""
        try:
            await self._handler.close_async()
        except Exception:
            logger.exception("Error closing Slack Socket Mode connection")
        logger.info(
            "Slack Socket Mode disconnected (token=...%s)",
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
        print(f"[DEBUG SLACK] handle_message: channel={channel}, type={channel_type}, thread_ts={thread_ts}, ts={ts}, bot_user_id={self.bot_user_id}")

        # 1. Direct Message (DM)
        if channel_type == "im":
            print(f"[DEBUG SLACK] DM received. Processing message...")
            await self._process_slack_message(event, say)
            return

        # 2. Thread reply in a channel/group (without needing a direct mention)
        if thread_ts and thread_ts != ts and channel:
            text = event.get("text", "")
            # Skip if the message contains a direct mention (let handle_mention respond)
            if self.bot_user_id and f"<@{self.bot_user_id}>" in text:
                print(f"[DEBUG SLACK] Thread reply contains mention. Letting handle_mention handle it.")
                return

            try:
                # Check if the bot is already participating in this thread
                replies = await self.app.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=50,
                )
                messages = replies.get("messages", [])
                print(f"[DEBUG SLACK] Thread replies count: {len(messages)}")
                for m in messages:
                    print(f"  Message user={m.get('user')}, bot_id={m.get('bot_id')}, text={m.get('text')[:30]}")

                bot_participated = any(
                    msg.get("user") == self.bot_user_id or msg.get("bot_id") is not None
                    for msg in messages
                )
                print(f"[DEBUG SLACK] bot_participated={bot_participated}")
                if bot_participated:
                    await self._process_slack_message(event, say)
            except Exception as e:
                print(f"[DEBUG SLACK] Error checking thread participation: {e}")
                logger.exception("Error checking thread participation for message event")

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_slack_message(self, event: dict, say) -> None:  # type: ignore[type-arg]
        """Route an incoming Slack event to the right employee and respond."""
        # Ignore messages from other bots (including ourselves)
        if "bot_id" in event:
            return

        text = event.get("text", "").strip()
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        is_dm = event.get("channel_type") == "im"

        # Resolve which employee should handle this
        employee_id = await self._resolve_employee(channel if not is_dm else None)
        if employee_id is None:
            logger.debug(
                "No employee assigned for channel=%s (token=...%s) — ignoring",
                channel,
                self.bot_token[-8:],
            )
            return

        # Fetch employee name for Slack display
        employee_name = "OpenHuman Agent"
        async with async_session_factory() as session:
            from app.employees.models import Employee
            emp = await session.get(Employee, employee_id)
            if emp:
                if emp.role:
                    employee_name = f"{emp.name} ({emp.role})"
                else:
                    employee_name = emp.name

        # Run the agent
        response_text = await self._run_agent(employee_id, text)
        if not response_text:
            response_text = "I processed your request but had no response."

        # Reply in thread with dynamic username
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
        """Return the employee UUID that should handle a message from
        *channel_id*, or ``None`` to ignore the message.

        Resolution order
        ----------------
        1. **Explicit assignment** — the channel appears in a
           ``ChannelAssignment`` row for one of our candidate employees.
        2. **Unrestricted fallback** — none of our candidates have *any*
           Slack channel assignments (they are all "respond everywhere"
           employees).  Use the first candidate.
        3. **No match** — return ``None`` (the channel is assigned to
           a different employee or no one at all).
        """
        async with async_session_factory() as session:
            if channel_id is not None:
                # ---- 1. Explicit assignment ----------------------------------
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

                # ---- 2. Are there ANY assignments among our candidates? -----
                any_assignments = await session.scalar(
                    select(ChannelAssignment).where(
                        ChannelAssignment.platform == "slack",
                        ChannelAssignment.employee_id.in_(self._employee_id_set),
                    ).limit(1)
                )
                if any_assignments is not None:
                    # Some employees are restricted → this channel is unassigned
                    return None

            # ---- 3. Unrestricted fallback (or DM) ---------------------------
            # No assignments at all among our candidates — everyone is
            # unrestricted.  Prefer an employee with no assignments
            # (purely unrestricted), falling back to the first candidate.
            if self.employee_ids:
                return await self._find_unrestricted_employee(session)

            return None

    async def _find_unrestricted_employee(self, session) -> UUID | None:
        """Return the first candidate employee that has *no* Slack channel
        assignments, or the first candidate overall if all have assignments."""
        from app.employees.models import Employee

        # Find employees among our candidates who have NO Slack assignments
        assigned_ids = set()
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

        # All have assignments — fall back to first candidate
        return self.employee_ids[0] if self.employee_ids else None

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(self, employee_id: UUID, content: str) -> str:
        """Run the LangGraph agent as *employee_id*.

        Never leaks raw exception details — returns a safe fallback on failure.
        """
        initial_state = {
            "messages": [HumanMessage(content=content)],
            "platform": "slack",
            "employee_id": str(employee_id),
            "tool_round": 0,
        }

        try:
            async with async_session_factory() as session:
                config = {
                    "configurable": {
                        "db": session,
                        "employee_id": str(employee_id),
                    }
                }
                result = await agent_graph.ainvoke(initial_state, config=config)
                return result.get("response", "")
        except Exception:
            logger.exception(
                "Agent graph failed for employee %s on Slack", employee_id,
            )
            return _SAFE_ERROR_MESSAGE
