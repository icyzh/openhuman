"""Gamma MCP connector — OAuth2 authentication.

Uses the official Gamma MCP server (https://mcp.gamma.app/mcp).
Works against any Gamma workspace.
OAuth consent is interactive (the user must click "Allow" in the browser).
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

GAMMA_CONNECTOR = ConnectorSpec(
    slug="gamma",
    name="Gamma",
    description="Gamma MCP — generate and manage presentations, documents, and web pages",
    base_url="https://mcp.gamma.app/mcp",
    transport="streamable_http",
    auth_type="oauth2",
    authorize_url="https://gamma.app/oauth/authorize",
    token_url="https://gamma.app/oauth/token",
    default_scopes=["read", "write"],
    docs_url="https://gamma.app/docs",
    default_tool_allow=None,  # allow all tools
    default_tool_deny=[],
    supports_token_refresh=True,
    requires_manual_approval=False,
)
