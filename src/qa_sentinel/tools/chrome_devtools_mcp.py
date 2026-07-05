from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams


def build_chrome_devtools_toolset(mcp_url: str = "http://127.0.0.1:9222/mcp") -> McpToolset:
    """Connects to the official Chrome DevTools MCP server and exposes only the
    read-only diagnostic tools TestRunner needs — never the action tools (click,
    navigate, fill), since Computer Use already owns acting on the page."""
    return McpToolset(
        connection_params = StreamableHTTPConnectionParams(url=mcp_url),
        tool_filter       = [
            "list_console_messages",
            "list_network_requests",
            "take_snapshot",
        ],
    )
