import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"


async def drive_browser(target_url: str) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = await browser.new_context()
        page    = await context.new_page()

        print(f"--- navigating to {target_url} ---")
        await page.goto(target_url)
        await page.click('a[href^="/product/"]')
        await page.click('button[data-testid="add-to-cart"]')
        await page.wait_for_load_state()
        await page.click('a[data-testid="cart-link"]')
        await page.wait_for_load_state()
        await page.click('button[data-testid="checkout"]')
        await page.wait_for_load_state()
        print(f"--- final page: {page.url} ---")
        await context.close()


async def probe_mcp() -> None:
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "chrome-devtools-mcp@latest", "--browserUrl", CDP_URL],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"--- available tools: {[t.name for t in tools.tools]} ---")

            for tool_name in ("list_console_messages", "list_network_requests"):
                print(f"\n=== calling {tool_name} ===")
                result = await session.call_tool(tool_name, {})
                print("isError:", result.isError)
                for block in result.content:
                    if block.type == "text":
                        print(block.text)


async def main() -> None:
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8009"
    await drive_browser(target_url)
    await probe_mcp()


if __name__ == "__main__":
    asyncio.run(main())
