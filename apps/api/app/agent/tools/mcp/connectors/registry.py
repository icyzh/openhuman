"""Connector registry — one declarative module per MCP server.

Each connector is described by a ``ConnectorSpec`` that teaches
``MCPClientManager`` and the OAuth router how to talk to it without
any server-specific code in those components.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

# Re-export for backwards compatibility
__all__ = ["REGISTRY", "ConnectorSpec"]

# ---------------------------------------------------------------------------
# Registry — populated in Phase 1 with Web Search + GitHub.
# Phase 2 adds Notion, Vercel; Phase 3 adds Gamma.
# ---------------------------------------------------------------------------

from app.agent.tools.mcp.connectors.github import GITHUB_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.notion import NOTION_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.vercel import VERCEL_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.gmail import GMAIL_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.gamma import GAMMA_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.pitchdeck import PITCHDECK_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.visualization import VISUALIZATION_CONNECTOR  # noqa: E402
from app.agent.tools.mcp.connectors.web_search import WEB_SEARCH_CONNECTOR  # noqa: E402

REGISTRY: dict[str, ConnectorSpec] = {
    "web_search": WEB_SEARCH_CONNECTOR,
    "github": GITHUB_CONNECTOR,
    "notion": NOTION_CONNECTOR,
    "vercel": VERCEL_CONNECTOR,
    "gmail": GMAIL_CONNECTOR,
    "gamma": GAMMA_CONNECTOR,
    "visualization": VISUALIZATION_CONNECTOR,
    "pitchdeck": PITCHDECK_CONNECTOR,
}
