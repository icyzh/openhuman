"""Canva MCP connector — OAuth2 authentication.

Uses the official, Canva-hosted remote MCP server (https://mcp.canva.com/mcp).
Free on every Canva plan (including the free tier) — generates, edits,
searches, and exports designs (including presentations/pitch decks as PPTX,
PDF, PNG, etc.) directly from natural language.

OAuth consent is interactive (the user must click "Allow" in the browser).
Client credentials are obtained via Canva's OAuth Dynamic Client Registration
endpoint (``POST https://mcp.canva.com/register``) — no manual app review
required, unlike most OAuth providers.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

CANVA_CONNECTOR = ConnectorSpec(
    slug="canva",
    name="Canva",
    description=(
        "Canva MCP — generate, edit, and export designs and presentations "
        "(pitch decks, PPTX, PDF, PNG) from natural language"
    ),
    base_url="https://mcp.canva.com/mcp",
    transport="streamable_http",
    auth_type="oauth2",
    authorize_url="https://mcp.canva.com/authorize",
    token_url="https://mcp.canva.com/token",
    default_scopes=[],
    docs_url="https://www.canva.dev/docs/mcp/",
    default_tool_allow=None,  # allow all tools
    default_tool_deny=[],
    token_auth_method="basic",
    supports_token_refresh=True,
    requires_manual_approval=False,
)
