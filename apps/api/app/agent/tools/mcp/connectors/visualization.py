"""Visualization MCP connector — local stdio-based matplotlib server.

Ships the visualization_server.py alongside the connector and spawns it
as a child process via stdio transport.  No API key, no signup, no cost.
"""

import os
import sys

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_PATH = os.path.join(_SERVER_DIR, "visualization_server.py")

VISUALIZATION_CONNECTOR = ConnectorSpec(
    slug="visualization",
    name="Visualization",
    description="Create interactive charts locally: scatter plots, 3D graphs, histograms, heatmaps, line charts, and network diagrams",
    command=sys.executable,
    args=[_SERVER_PATH],
    transport="stdio",
    auth_type="none",
    docs_url="https://github.com/xlisp/visualization-mcp-server",
    default_tool_allow=None,
    default_tool_deny=[],
)
