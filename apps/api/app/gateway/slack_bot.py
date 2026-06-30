import logging
from uuid import UUID

from langchain_core.messages import HumanMessage
from slack_bolt.async_app import AsyncApp
from sqlalchemy import select

from app.agent.router import agent_graph
from app.channel_assignments.models import ChannelAssignment
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)

_SAFE_ERROR_MESSAGE = (
    "I ran into a problem processing your request. Please try again later."
)


class EmployeeSlackBot:
    """Slack App wrapper representing a single AI employee instance using
    Socket Mode or standard events."""

    def __init__(self, employee_id: UUID, bot_token: str):
        self.employee_id = employee_id
        self.app = AsyncApp(token=bot_token)

        # Register event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.event("message")(self.handle_message)

    # ------------------------------------------------------------------
    # Event filters
    # ------------------------------------------------------------------

    async def _is_assigned_channel(self, channel_id: str) -> bool:
        """Return True if this employee has no channel assignments (respond
        everywhere), or if *channel_id* appears in their assignments."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(ChannelAssignment).where(
                    ChannelAssignment.employee_id == self.employee_id,
                    ChannelAssignment.platform == "slack",
                )
            )
            assignments = result.scalars().all()
        if not assignments:
            return True
        return any(a.channel_id == channel_id for a in assignments)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def handle_mention(self, event: dict, say: dict) -> None:  # type: ignore[type-arg]
        """Respond to direct mentions in public channels."""
        await self._process_slack_message(event, say)

    async def handle_message(self, event: dict, say: dict) -> None:  # type: ignore[type-arg]
        """Respond to DMs (ignore channel messages that are not mentions)."""
        if event.get("channel_type") == "im":
            await self._process_slack_message(event, say)

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _process_slack_message(self, event: dict, say: dict) -> None:  # type: ignore[type-arg]
        # Ignore bot messages
        if "bot_id" in event:
            return

        text = event.get("text", "").strip()
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Channel assignment filter — only applies to public channels, not DMs
        if event.get("channel_type") != "im":
            if not await self._is_assigned_channel(channel):
                return

        response_text = await self._run_agent(text)

        if not response_text:
            response_text = "I processed your request but had no response."

        # Reply inside a thread
        await say(text=response_text, channel=channel, thread_ts=thread_ts)

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    async def _run_agent(self, content: str) -> str:
        """Run the LangGraph agent with a fresh DB session.

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
                "Agent graph failed for employee %s on Slack", self.employee_id,
            )
            return _SAFE_ERROR_MESSAGE
