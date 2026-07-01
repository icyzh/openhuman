"""GitHub MCP connector — PAT bearer + OAuth2 authentication.

Uses the official GitHub Copilot MCP server.

**PAT mode** (default): every org pastes a free GitHub PAT with the scopes
they want to grant (``repo``, ``read:org``, …).  No Copilot subscription
required.  Use the ``POST …/{slug}`` credential-paste API.

**OAuth mode**: if ``GITHUB_CLIENT_ID`` / ``GITHUB_CLIENT_SECRET`` are
configured in the environment, the ``GET …/{slug}/install`` OAuth flow is
also available — the user grants access through a GitHub consent screen.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

GITHUB_CONNECTOR = ConnectorSpec(
    slug="github",
    name="GitHub",
    description="GitHub Copilot MCP — code search, repository management, issues, PRs",
    base_url="https://api.githubcopilot.com/mcp/",
    transport="streamable_http",
    auth_type="pat_bearer",
    # OAuth metadata — set when GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET are
    # configured; the install endpoint uses the presence of authorize_url to
    # decide whether OAuth is available.
    authorize_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    default_scopes=["repo", "read:org", "user"],
    docs_url="https://docs.github.com/en/enterprise-cloud@latest/copilot/developing-with-copilot/mcp/using-github-copilot-mcp-server",
    default_tool_allow=None,  # allow all tools from this server
    default_tool_deny=[],
    supports_token_refresh=False,
    requires_manual_approval=False,
)
