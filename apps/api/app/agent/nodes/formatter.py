from langchain_core.messages import AIMessage

from app.agent.state import AgentState


async def formatter_node(state: AgentState) -> dict:
    """Format final output response according to platform constraints.

    Handles:
    - Blocked inputs / failed output guardrails (safe-fallback already set)
    - Tool-round-limit reached without a text response
    - Platform-specific length truncation (Discord 2000, Slack 4000)
    - Empty message lists
    """
    # If a guardrail blocked the message the response is already set in state
    if state.get("input_blocked") or not state.get("output_guardrail_passed", True):
        return {"response": state.get("response")}

    messages = state.get("messages", [])
    if not messages:
        return {"response": ""}

    # Find the last assistant message
    ai_msg = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)), None
    )
    if not ai_msg:
        return {"response": ""}

    response_text = str(ai_msg.content) if ai_msg.content else ""

    # When the tool-round limit was reached and the LLM returned tool_calls
    # instead of a text answer, produce a graceful fallback.
    if not response_text.strip() and state.get("tool_round", 0) >= 5:
        response_text = (
            "I wasn't able to complete this request within the allowed "
            "number of research steps. Could you try rephrasing or "
            "breaking it into smaller questions?"
        )

    platform = state.get("platform", "api")

    # Platform-specific formatting rules
    if platform == "discord":
        # Discord limit is 2000 characters
        if len(response_text) > 2000:
            response_text = (
                response_text[:1900]
                + "... [Truncated due to Discord character limits]"
            )
    elif platform == "slack":
        # Slack limit is 4000 characters
        if len(response_text) > 4000:
            response_text = (
                response_text[:3900]
                + "... [Truncated due to Slack character limits]"
            )

    return {"response": response_text}
