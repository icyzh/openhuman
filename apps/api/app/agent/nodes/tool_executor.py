from langgraph.prebuilt import ToolNode
import logging

logger = logging.getLogger(__name__)


class CustomToolNode(ToolNode):
    """A ToolNode subclass that automatically increments the tool_round counter and logs executions."""

    async def ainvoke(self, input, config=None, **kwargs):  # type: ignore[no-untyped-def]
        current_round = input.get("tool_round", 0)
        logger.info("[Tool Node] Executing tools round %d", current_round)

        # Execute tools using base implementation
        result = await super().ainvoke(input, config, **kwargs)

        # Log outputs
        if isinstance(result, dict):
            for message in result.get("messages", []):
                tool_name = getattr(message, "name", "unknown")
                content = getattr(message, "content", "")
                logger.info(
                    "[Tool Executed] Tool: %s | Output Snippet: '%s...'",
                    tool_name,
                    str(content)[:150],
                )

        # Increment tool round in state
        result["tool_round"] = current_round + 1
        return result
