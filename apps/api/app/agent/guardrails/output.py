def check_output(
    response: str, guardrail_config: dict | None = None
) -> tuple[bool, str | None]:
    """Check the LLM response against safety policies.

    Returns:
        tuple[bool, str | None]: (passed_validation, reason)
    """
    config = guardrail_config or {}

    # Check for blocked keywords or phrases (e.g. system instructions leaking)
    blocked_patterns = [
        "system prompt template",
        "according to my instructions",
        "as an ai",
    ]
    for pattern in blocked_patterns:
        if pattern.lower() in response.lower():
            return False, f"Response contained restricted phrase: '{pattern}'"

    # When citation requirements are enabled, verify the response provides
    # at least a minimal attribution signal.
    if config.get("require_citations", False):
        # Simple heuristic: look for source-like markers
        has_citation_marker = any(
            marker in response.lower()
            for marker in ["source:", "citation:", "according to", "from the"]
        )
        if not has_citation_marker and len(response) > 200:
            return False, (
                "Response is missing required citations. "
                "Please include sources for factual claims."
            )

    return True, None
