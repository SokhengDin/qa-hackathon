import asyncio
import logging
import subprocess

from playwright.async_api import Playwright, async_playwright

logger = logging.getLogger("qa_sentinel.shared_chromium")

CDP_PORT     = 9222
CDP_URL      = f"http://127.0.0.1:{CDP_PORT}"
READY_TIMEOUT_S = 15

_process: subprocess.Popen | None = None
_keepalive_playwright: Playwright | None = None
_keepalive_browser = None
_keepalive_page = None


async def start(headless: bool = False) -> str:
    """Launches Playwright's own bundled Chromium once, as a real OS
    subprocess with a CDP debugging port open, and keeps it alive for the
    whole server lifetime. Both Computer Use (via connect_over_cdp) and
    chrome-devtools-mcp (via --browserUrl) attach to this SAME instance —
    it is never launched or torn down per tool call. Returns the CDP URL.

    Holds one permanent blank page open via its own persistent connection —
    without this, Chromium exits on its own once the last page/context from
    a per-step connect_over_cdp call closes, killing the shared instance
    between steps."""
    global _process

    if _process is not None and _process.poll() is None:
        return CDP_URL

    p = await async_playwright().start()
    executable_path = p.chromium.executable_path
    await p.stop()

    args = [
        executable_path,
        f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
    ]
    if headless:
        args.append("--headless=new")

    logger.info("Launching shared Chromium: %s", " ".join(args))
    _process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        await _wait_until_ready()
    except RuntimeError:
        output = ""
        if _process.stdout is not None:
            output = _process.stdout.read()
        logger.error("Shared Chromium failed to start. Output:\n%s", output)
        raise

    await _open_keepalive_page()
    logger.info("Shared Chromium ready at %s (pid %s)", CDP_URL, _process.pid)
    return CDP_URL


async def stop() -> None:
    global _process

    await _close_keepalive_page()

    if _process is not None and _process.poll() is None:
        logger.info("Stopping shared Chromium (pid %s)", _process.pid)
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None


async def _open_keepalive_page() -> None:
    global _keepalive_playwright, _keepalive_browser, _keepalive_page

    _keepalive_playwright = await async_playwright().start()
    _keepalive_browser    = await _keepalive_playwright.chromium.connect_over_cdp(CDP_URL)
    context               = _keepalive_browser.contexts[0] if _keepalive_browser.contexts \
        else await _keepalive_browser.new_context()
    _keepalive_page = await context.new_page()
    await _keepalive_page.goto("about:blank")


async def _close_keepalive_page() -> None:
    global _keepalive_playwright, _keepalive_browser, _keepalive_page

    if _keepalive_playwright is not None:
        await _keepalive_playwright.stop()
    _keepalive_playwright = None
    _keepalive_browser    = None
    _keepalive_page       = None


async def _wait_until_ready() -> None:
    import httpx

    deadline = asyncio.get_event_loop().time() + READY_TIMEOUT_S
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            if _process is not None and _process.poll() is not None:
                raise RuntimeError(
                    f"Shared Chromium process exited early with code {_process.returncode}"
                )
            try:
                resp = await client.get(f"{CDP_URL}/json/version", timeout=1)
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Shared Chromium did not become ready on {CDP_URL} within {READY_TIMEOUT_S}s")
