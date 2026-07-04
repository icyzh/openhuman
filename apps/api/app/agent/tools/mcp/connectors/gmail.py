"""Gmail MCP connector — OAuth2 authentication.

Uses Google's official Gmail MCP server (https://gmailmcp.googleapis.com/mcp/v1).
Works with any Gmail or Google Workspace account.
OAuth consent is interactive (the user must click "Allow" in the browser).

Requires a Google Cloud project with the Gmail API + Gmail MCP API enabled,
and a Web Application OAuth 2.0 client ID configured with the redirect URI
pointing to ``{api_url}/api/mcp/oauth/callback``.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

GMAIL_CONNECTOR = ConnectorSpec(
    slug="gmail",
    name="Gmail",
    description=(
        "Gmail MCP — search threads, read messages, create drafts, "
        "and manage labels"
    ),
    base_url="https://gmailmcp.googleapis.com/mcp/v1",
    transport="streamable_http",
    auth_type="oauth2",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    default_scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ],
    docs_url=(
        "https://developers.google.com/workspace/gmail/api/guides/"
        "configure-mcp-server"
    ),
    default_tool_allow=None,
    default_tool_deny=[],
    supports_token_refresh=True,
    requires_manual_approval=False,
)
