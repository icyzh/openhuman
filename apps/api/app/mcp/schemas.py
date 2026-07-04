"""Pydantic schemas for the MCP management API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectorStatus(BaseModel):
    """A registry connector with its connection state for an org/employee."""

    slug: str
    name: str
    description: str
    auth_type: str
    auth_types: list[str] = []
    docs_url: str = ""
    is_connected: bool = False
    connection_count: int = 0


class McpConnectionRead(BaseModel):
    """Public representation of a stored MCP connection."""

    id: UUID
    connector_slug: str
    auth_type: str
    scopes: list | None = None
    status: str
    is_org_wide: bool = False
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class McpConnectionCreate(BaseModel):
    """Payload for creating/updating an API-key or PAT MCP connection."""

    credential: str = Field(..., description="The API key, PAT, or access token to store")
    scopes: list[str] | None = None
    org_wide: bool = Field(
        default=False, description="If True, connection is available to all employees in the org"
    )


class McpConnectionList(BaseModel):
    """Wrapper for listing connections."""

    connections: list[McpConnectionRead]
