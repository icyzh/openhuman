"""Pitch Deck MCP connector — local stdio-based python-pptx server.

Ships pitchdeck_server.py alongside the connector and spawns it as a
child process via stdio transport. No API key, no OAuth, no waitlist,
no cost — generates a real styled .pptx file entirely in-process and
auto-attaches it to the chat.
"""

import os
import sys

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_PATH = os.path.join(_SERVER_DIR, "pitchdeck_server.py")

PITCHDECK_CONNECTOR = ConnectorSpec(
    slug="pitchdeck",
    name="Pitch Deck Generator",
    description="Generate styled .pptx pitch decks locally — free, no API key, no signup required",
    command=sys.executable,
    args=[_SERVER_PATH],
    transport="stdio",
    auth_type="none",
    docs_url="",
    default_tool_allow=None,
    default_tool_deny=[],
)
