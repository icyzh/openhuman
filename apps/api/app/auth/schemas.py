from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UpdateUserRequest(BaseModel):
    onboarding_completed: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clerk_id: str
    email: str
    name: str
    is_active: bool
    onboarding_completed: bool = False
    created_at: datetime
