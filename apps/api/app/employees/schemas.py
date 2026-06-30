from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.channel_assignments.schemas import ChannelAssignmentResponse


class CreateEmployeeRequest(BaseModel):
    name: str
    role: str | None = None
    personality: dict | None = None
    specialization: str | None = None
    duties: list | None = None
    memory_policy: dict | None = None


class UpdateEmployeeRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    personality: dict | None = None
    specialization: str | None = None
    duties: list | None = None
    memory_policy: dict | None = None
    status: str | None = None


class DiscordTokenRequest(BaseModel):
    token: str


class SlackTokenRequest(BaseModel):
    token: str


class StatusRequest(BaseModel):
    status: str  # "active" | "inactive"


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    id: UUID
    org_id: UUID
    name: str
    role: str | None = None
    personality: dict | None = None
    specialization: str | None = None
    duties: list | None = None
    memory_policy: dict | None = None
    mcp_connections: list | None = None
    status: str
    has_discord_token: bool
    has_slack_token: bool
    cognee_user_id: str | None = None
    cognee_dataset_name: str | None = None
    channel_assignments: list[ChannelAssignmentResponse] = []
    created_at: datetime
    updated_at: datetime | None = None
