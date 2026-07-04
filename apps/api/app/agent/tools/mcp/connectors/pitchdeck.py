"""AI Pitch Deck MCP connector — free, no authentication required.

AI-powered pitch deck generation. Create investor-ready decks, generate
individual slides, get structure recommendations, and fundraising metrics.
No API key required.
"""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

PITCHDECK_CONNECTOR = ConnectorSpec(
    slug="pitchdeck",
    name="Pitch Deck AI",
    description="Free AI pitch deck generator — create investor-ready slides, get structure and metric recommendations",
    base_url="https://pitchdeck-mcp.fly.dev/mcp",
    transport="streamable_http",
    auth_type="none",
    docs_url="https://github.com/crawde/ai-pitch-deck-mcp",
    default_tool_allow=None,
    default_tool_deny=[],
)
