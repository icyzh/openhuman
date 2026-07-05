from app.agent.tools.mcp.connectors.canva import CANVA_CONNECTOR
from app.agent.tools.mcp.connectors.gamma import GAMMA_CONNECTOR
from app.agent.tools.mcp.connectors.github import GITHUB_CONNECTOR
from app.agent.tools.mcp.connectors.gmail import GMAIL_CONNECTOR
from app.agent.tools.mcp.connectors.n8n import N8N_CONNECTOR
from app.agent.tools.mcp.connectors.notion import NOTION_CONNECTOR
from app.agent.tools.mcp.connectors.pitchdeck import PITCHDECK_CONNECTOR
from app.agent.tools.mcp.connectors.registry import REGISTRY
from app.agent.tools.mcp.connectors.spec import ConnectorSpec
from app.agent.tools.mcp.connectors.vercel import VERCEL_CONNECTOR
from app.agent.tools.mcp.connectors.visualization import VISUALIZATION_CONNECTOR
from app.agent.tools.mcp.connectors.web_search import WEB_SEARCH_CONNECTOR

__all__ = [
    "REGISTRY",
    "ConnectorSpec",
    "CANVA_CONNECTOR",
    "GITHUB_CONNECTOR",
    "GMAIL_CONNECTOR",
    "NOTION_CONNECTOR",
    "PITCHDECK_CONNECTOR",
    "VERCEL_CONNECTOR",
    "VISUALIZATION_CONNECTOR",
    "WEB_SEARCH_CONNECTOR",
    "GAMMA_CONNECTOR",
    "N8N_CONNECTOR",
]
