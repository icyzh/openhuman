"""n8n MCP connector — PAT bearer authentication against an org-specific MCP URL.

n8n exposes MCP per instance, so each OpenHuman connection must store the
instance's MCP endpoint URL (for example ``https://your-n8n.example.com/mcp-server/http``)
alongside a personal MCP access token.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

N8N_CONNECTOR = ConnectorSpec(
    slug="n8n",
    name="n8n",
    description="n8n MCP — search workflows, trigger runs, and build or edit workflows on your n8n instance",
    transport="streamable_http",
    auth_type="pat_bearer",
    requires_custom_server_url=True,
    docs_url="https://docs.n8n.io/build/ways-of-building-workflows/connect-to-n8n-mcp-server/",
    default_tool_allow=None,
    default_tool_deny=[],
    request_timeout_seconds=60.0,
    supports_token_refresh=False,
    requires_manual_approval=False,
)
