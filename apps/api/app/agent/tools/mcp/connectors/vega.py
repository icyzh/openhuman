"""Vega MCP connector — free, no authentication required.

Uses the community Vega-Lite MCP server for rendering interactive charts.
No API key, no signup, no cost.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

VEGA_CONNECTOR = ConnectorSpec(
    slug="vega",
    name="Vega",
    description="Free Vega-Lite MCP — render interactive charts from JSON specs",
    base_url="https://vega-mcp-server.fly.dev/mcp",
    transport="streamable_http",
    auth_type="none",
    docs_url="https://github.com/hydrosquall/vega-mcp-server",
    default_tool_allow=None,
    default_tool_deny=[],
)
