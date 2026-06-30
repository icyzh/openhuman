from langgraph.prebuilt import ToolNode


class CustomToolNode(ToolNode):
    """A ToolNode subclass that automatically increments the tool_round counter."""

    async def ainvoke(self, input, config=None, **kwargs):  # type: ignore[no-untyped-def]
        # Execute tools using base implementation
        result = await super().ainvoke(input, config, **kwargs)
        # Increment tool round in state
        current_round = input.get("tool_round", 0)
        result["tool_round"] = current_round + 1
        return result
