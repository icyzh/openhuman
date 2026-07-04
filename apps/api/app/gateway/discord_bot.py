import json
import logging
from uuid import UUID

import discord
from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.activity.context import (
    activity_channel_id,
    activity_employee_id,
    activity_employee_name,
    activity_org_id,
    activity_platform,
)
from app.agent.jobs.queue import cancel_active_jobs_for_thread, is_cancel_intent
from app.agent.router import get_graph_for_employee
from app.activity.service import record_activity
from app.channel_assignments.models import ChannelAssignment
from app.core.database import async_session_factory
from app.employees.models import Employee

logger = logging.getLogger(__name__)

# Safe fallback message exposed to public channels — never includes raw
# exception details.
_SAFE_ERROR_MESSAGE = (
    "I ran into a problem processing your request. Please try again later."
)


class EmployeeDiscordBot(discord.Client):
    """Discord Client wrapper representing a single AI employee instance."""

    def __init__(self, employee_id: UUID, *args, **kwargs):  # type: ignore[no-untyped-def]
        intents = discord.Intents.default()
        intents.message_content = True
        kwargs["intents"] = intents
        super().__init__(*args, **kwargs)

        self.employee_id = employee_id

    async def on_ready(self) -> None:
        logger.info(
            "Discord bot for employee %s connected as %s", self.employee_id, self.user,
        )

    # ------------------------------------------------------------------
    # Message filter helpers
    # ------------------------------------------------------------------

    def _is_dm(self, message: discord.Message) -> bool:
        return isinstance(message.channel, discord.DMChannel)

    def _is_mentioned(self, message: discord.Message) -> bool:
        return self.user in message.mentions if self.user else False

    async def _is_assigned_channel(self, channel_id: int) -> bool:
        """Return True if this employee has no channel assignments (respond
        everywhere), or if *channel_id* appears in their assignments."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(ChannelAssignment).where(
                    ChannelAssignment.employee_id == self.employee_id,
                    ChannelAssignment.platform == "discord",
                )
            )
            assignments = result.scalars().all()
        if not assignments:
            # No restrictions — respond in any channel
            return True
        return any(a.channel_id == str(channel_id) for a in assignments)

    # ------------------------------------------------------------------
    # Message handler
    # ------------------------------------------------------------------

    async def on_message(self, message: discord.Message) -> None:
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Must be a DM or a mention
        if not self._is_dm(message) and not self._is_mentioned(message):
            return

        # Channel assignment filter — skip if employee is only supposed to
        # respond in specific channels.
        if not self._is_dm(message):
            if not await self._is_assigned_channel(message.channel.id):
                return

        # Clean the content (remove the bot mention tag)
        content = message.content
        if not self._is_dm(message) and self._is_mentioned(message):
            content = content.replace(
                f"<@!{self.user.id}>", ""
            ).replace(
                f"<@{self.user.id}>", ""
            )
        content = content.strip()

        # -- Phase 3: lightweight cancel keyword fast path -------------------
        if is_cancel_intent(content):
            channel_id = str(message.channel.id)
            message_id = str(message.id)
            thread_key = f"discord:{self.employee_id}:{channel_id}:{message_id}"
            async with async_session_factory() as session:
                cancelled = await cancel_active_jobs_for_thread(session, thread_key)
            if cancelled:
                names = ", ".join(j.job_type for j in cancelled)
                await message.reply(f"🫡 Cancelled: {names}.")
                # Record cancellation (best-effort)
                try:
                    async with async_session_factory() as s:
                        emp = await s.get(Employee, self.employee_id)
                        if emp:
                            await record_activity(
                                s,
                                emp.org_id,
                                "agent_run",
                                f"Cancelled {len(cancelled)} background task(s): {names}",
                                employee_id=self.employee_id,
                                employee_name=emp.name,
                                platform="discord",
                                status="cancelled",
                                metadata={
                                    "cancelled_jobs": names,
                                    "channel_id": str(message.channel.id),
                                },
                            )
                except Exception:
                    pass
            else:
                await message.reply(
                    "Nothing to cancel — there are no active "
                    "background tasks in this conversation."
                )
            return

        # Thread recording context for per-tool activity
        try:
            async with async_session_factory() as s:
                emp = await s.get(Employee, self.employee_id)
                if emp:
                    activity_org_id.set(str(emp.org_id))
                    activity_employee_name.set(emp.name)
        except Exception:
            pass
        activity_employee_id.set(str(self.employee_id))
        activity_platform.set("discord")
        activity_channel_id.set(str(message.channel.id))

        # Trigger typing indicator to show the bot is thinking
        async with message.channel.typing():
            response_text, is_error = await self._run_agent(
                content,
                channel_id=str(message.channel.id),
                message_id=str(message.id),
            )

        # Record activity (best-effort)
        try:
            async with async_session_factory() as s:
                emp = await s.get(Employee, self.employee_id)
                if emp:
                    await record_activity(
                        s,
                        emp.org_id,
                        "agent_conversation",
                        f"Responded to: {content[:100]}",
                        employee_id=self.employee_id,
                        employee_name=emp.name,
                        platform="discord",
                        status="failed" if is_error else "succeeded",
                        description=json.dumps({
                            "response": response_text[:500] if response_text else None,
                            "channel_id": str(message.channel.id),
                        }),
                        metadata={
                            "channel_id": str(message.channel.id),
                            "message_id": str(message.id),
                            "discord_user_id": str(message.author.id),
                            "is_dm": self._is_dm(message),
                        },
                    )
        except Exception:
            pass

        # Discord message character limit — chunk at 2000
        if not response_text:
            response_text = "I processed your request but had no response."

        for i in range(0, len(response_text), 2000):
            await message.reply(response_text[i : i + 2000])

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(
        self, content: str,
        channel_id: str = "",
        message_id: str = "",
    ) -> tuple[str, bool]:
        """Run the LangGraph agent with a fresh DB session.

        Returns (response_text, is_error). Never leaks raw exception
        details to the caller — returns a safe fallback message on failure.
        """
        root_id = message_id or "direct"
        thread_key = f"discord:{self.employee_id}:{channel_id}:{root_id}"

        initial_state = {
            "messages": [HumanMessage(content=content)],
            "platform": "discord",
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
                        "thread_id": thread_key,
                        "platform": "discord",
                        "channel_id": channel_id,
                    }
                }
                result = await graph.ainvoke(initial_state, config=config)
                error = result.get("error")
                return (result.get("response", ""), error is not None)
        except Exception:
            logger.exception(
                "Agent graph failed for employee %s on Discord", self.employee_id,
            )
            return (_SAFE_ERROR_MESSAGE, True)
