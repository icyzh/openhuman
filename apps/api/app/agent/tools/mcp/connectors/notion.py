"""Notion MCP connector — OAuth2 authentication only.

Uses the official Notion MCP server (https://mcp.notion.com/mcp).
Works against any Notion workspace — free tier included.
OAuth consent is interactive (the user must click "Allow" in the browser).
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

NOTION_CONNECTOR = ConnectorSpec(
    slug="notion",
    name="Notion",
    description="Notion MCP — search, read, create, and update Notion pages and databases",
    base_url="https://mcp.notion.com/mcp",
    transport="streamable_http",
    auth_type="oauth2",
    authorize_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    default_scopes=[],
    docs_url="https://developers.notion.com/docs/authorization",
    default_tool_allow=None,  # allow all tools
    default_tool_deny=[],
    supports_token_refresh=False,
    requires_manual_approval=False,
)
