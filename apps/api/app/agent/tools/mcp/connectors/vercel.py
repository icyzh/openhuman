"""Vercel MCP connector — OAuth 2.1 authentication.

Uses the official Vercel MCP server (https://mcp.vercel.com).
Works with any Vercel account including the free Hobby plan.
OAuth consent is interactive (the user must click "Allow" in the browser).
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

VERCEL_CONNECTOR = ConnectorSpec(
    slug="vercel",
    name="Vercel",
    description="Vercel MCP — manage projects, deployments, domains, logs, and env vars",
    base_url="https://mcp.vercel.com",
    transport="streamable_http",
    auth_type="oauth2",
    alternative_auth_types=["pat_bearer"],
    authorize_url="https://vercel.com/oauth/authorize",
    token_url="https://api.vercel.com/v2/oauth/access_token",
    default_scopes=[],
    docs_url="https://vercel.com/docs/rest-api",
    default_tool_allow=None,  # allow all tools
    default_tool_deny=[],
    supports_token_refresh=False,
    requires_manual_approval=False,
)
