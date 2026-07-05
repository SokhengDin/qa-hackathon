from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


def build_chrome_devtools_toolset(cdp_url: str = "http://127.0.0.1:9222") -> McpToolset:
    """Launches chrome-devtools-mcp as a stdio subprocess, pointed at the
    shared Chromium instance's CDP debugging port — this is the SAME browser
    Computer Use is driving via connect_over_cdp, not a separate instance.
    Exposes only the read-only diagnostic tools TestRunner needs — never the
    action tools (click, navigate, fill), since Computer Use already owns
    acting on the page."""
    return McpToolset(
        connection_params = StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "chrome-devtools-mcp@latest", "--browserUrl", cdp_url],
            ),
        ),
        tool_filter = [
            "list_pages",
            "select_page",
            "list_console_messages",
            "list_network_requests",
            "take_snapshot",
        ],
    )
