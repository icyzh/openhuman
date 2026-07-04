"""Pitch deck generation MCP connector backed by ``pptx-generator-mcp``."""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

PITCHDECK_CONNECTOR = ConnectorSpec(
    slug="pitchdeck",
    name="PPTX Generator",
    description="Generate PowerPoint pitch decks from structured markdown prompts",
    transport="stdio",
    command="pptx-generator-mcp",
    args=[],
    auth_type="none",
    docs_url="https://github.com/dmytro-ustynov/pptx-generator-mcp",
    default_tool_allow=None,
    default_tool_deny=[],
)
