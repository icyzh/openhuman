# Skeleton for Model Context Protocol client manager
class MCPClientManager:
    """Stub client manager for MCP servers."""

    async def connect(self, mcp_connections: list[dict]) -> list:
        """Stub connect method returning no tools."""
        return []

    async def disconnect(self) -> None:
        """Stub disconnect method."""
        pass
