"""Web Search MCP connector — free, key-less, no authentication required.

Uses a community-hosted or self-hosted open-websearch MCP server.
No API key, no signup, no cost — the simplest possible connector.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

WEB_SEARCH_CONNECTOR = ConnectorSpec(
    slug="web_search",
    name="Web Search",
    description="Free web search via open-websearch MCP — no API key required",
    base_url="https://rival-search-mcp.fly.dev/mcp",
    transport="streamable_http",
    auth_type="none",
    docs_url="https://github.com/taskiq/RivalSearchMCP",
    default_tool_allow=None,  # allow all tools from this server
    default_tool_deny=[],
)
