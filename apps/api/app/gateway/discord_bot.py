import logging
from uuid import UUID

import discord
from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.agent.router import agent_graph
from app.channel_assignments.models import ChannelAssignment
from app.core.database import async_session_factory

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

        # Trigger typing indicator to show the bot is thinking
        async with message.channel.typing():
            response_text = await self._run_agent(content)

        # Discord message character limit — chunk at 2000
        if not response_text:
            response_text = "I processed your request but had no response."

        for i in range(0, len(response_text), 2000):
            await message.reply(response_text[i : i + 2000])

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(self, content: str) -> str:
        """Run the LangGraph agent with a fresh DB session.

        Never leaks raw exception details to the caller — returns a safe
        fallback message on failure.
        """
        initial_state = {
            "messages": [HumanMessage(content=content)],
            "platform": "discord",
            "employee_id": str(self.employee_id),
            "tool_round": 0,
        }

        try:
            async with async_session_factory() as session:
                config = {
                    "configurable": {
                        "db": session,
                        "employee_id": str(self.employee_id),
                    }
                }
                result = await agent_graph.ainvoke(initial_state, config=config)
                return result.get("response", "")
        except Exception:
            logger.exception(
                "Agent graph failed for employee %s on Discord", self.employee_id,
            )
            return _SAFE_ERROR_MESSAGE
