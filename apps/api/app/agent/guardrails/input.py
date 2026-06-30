import re


def check_input(content: str, guardrail_config: dict | None = None) -> tuple[bool, str | None]:
    """Check the user input against safety/guardrail policies.

    Returns:
        tuple[bool, str | None]: (is_blocked, reason)
    """
    if len(content) > 4000:
        return True, "Message is too long (limit is 4000 characters)."

    config = guardrail_config or {}

    # Basic prompt injection checks
    injection_patterns = [
        r"(?i)\bignore previous instructions\b",
        r"(?i)\bsystem prompt override\b",
        r"(?i)\byou are now\b",
        r"(?i)\bforget everything you know\b",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, content):
            return True, "Potential prompt injection detected."

    # Basic PII check (email, phone, etc.) if enabled
    if config.get("block_pii", False):
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        if re.search(email_pattern, content) or re.search(phone_pattern, content):
            return True, "Personally Identifiable Information (PII) is not allowed."

    return False, None
