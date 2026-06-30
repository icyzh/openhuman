from uuid import UUID

from pydantic import BaseModel


class Citation(BaseModel):
    """An attribution citation for information returned by the agent."""

    source: str
    content: str
    confidence: float | None = None


class MessageInput(BaseModel):
    """Payload representing an incoming message from any gateway or tester."""

    content: str
    platform: str  # "discord" | "slack" | "api"
    channel_id: str
    user_id: str
    employee_id: UUID
    employee_name: str | None = None
    org_name: str | None = None
    system_prompt_template: str | None = None


class AgentResponse(BaseModel):
    """Payload returned by the agent after compiling a response."""

    response: str | None
    tool_calls_count: int
    error: str | None = None
