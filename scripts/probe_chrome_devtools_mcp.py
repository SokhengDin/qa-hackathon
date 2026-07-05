import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"


async def main() -> None:
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8009"

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "chrome-devtools-mcp@latest", "--browserUrl", CDP_URL],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"--- available tools: {[t.name for t in tools.tools]} ---")

            pages = await session.call_tool("list_pages", {})
            print("\n=== list_pages (before anything) ===")
            for block in pages.content:
                if block.type == "text":
                    print(block.text)

            print(f"\n--- driving browser to {target_url} via Playwright ---")
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(CDP_URL)
                context = await browser.new_context()
                page    = await context.new_page()

                await page.goto(target_url)
                await page.click('a[href^="/product/"]')
                await page.click('button[data-testid="add-to-cart"]')
                await page.wait_for_load_state()
                await page.click('a[data-testid="cart-link"]')
                await page.wait_for_load_state()

                print("--- clicking checkout ---")
                async with page.expect_response(lambda r: "/checkout" in r.url) as resp_info:
                    await page.click('button[data-testid="checkout"]')
                response = await resp_info.value
                print(f"--- checkout response status: {response.status} ---")
                await page.wait_for_load_state()

                pages2 = await session.call_tool("list_pages", {})
                print("\n=== list_pages (after driving) ===")
                for block in pages2.content:
                    if block.type == "text":
                        print(block.text)

                print("\n=== calling list_network_requests (same session, after nav) ===")
                result = await session.call_tool("list_network_requests", {})
                print("isError:", result.isError)
                for block in result.content:
                    if block.type == "text":
                        print(block.text)

                print("\n=== calling list_console_messages (same session, after nav) ===")
                result2 = await session.call_tool("list_console_messages", {})
                print("isError:", result2.isError)
                for block in result2.content:
                    if block.type == "text":
                        print(block.text)

                await context.close()


if __name__ == "__main__":
    asyncio.run(main())
