import base64
import json
import time
from pathlib import Path

from google import genai
from playwright.sync_api import sync_playwright

from qa_sentinel.config.settings import settings

MODEL        = "gemini-3.5-flash"
TURN_LIMIT   = 15
EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "evidence" / "screenshots"

TOOLS = [{
    "type"       : "computer_use",
    "environment": "browser",

    "enable_prompt_injection_detection": True,
}]

SYSTEM_INSTRUCTION = """
You are testing a disposable QA target application — never a real production
system. Follow these rules:

RULE 1 — Seek confirmation before consequential actions. Perform all
preparatory steps (navigating, filling forms, typing) freely. Before the
final, irreversible action in a flow (e.g. clicking "Submit", "Confirm
Purchase", "Send"), you may proceed — this target app is disposable and
its purchase/consent flows are fake test fixtures, not real transactions.

RULE 2 — Never attempt to solve or bypass CAPTCHAs or other human-verification
mechanisms. If one appears, stop and report it rather than trying to defeat it.

RULE 3 — Default behavior is to actuate: proactively perform the steps needed
to complete the requested test instruction, using only the on-screen UI.
""".strip()


def run_ui_test_step(
    instruction  : str,
    url          : str,
    screen_width : int = 1440,
    screen_height: int = 900,
    headless     : bool = True,
) -> dict:
    """Drives the target app's UI via Gemini Computer Use to execute one test step.

    Uses client.interactions.create with the computer_use tool — NOT
    generate_content, and NOT a types.ComputerUse object. The tool is a plain
    dict: {"type": "computer_use", "environment": "browser"}.

    Gemini never launches the target app — this function launches Playwright's
    own bundled Chromium and navigates to `url` first; Gemini only ever
    receives screenshots and returns click/type instructions turn by turn.
    "Gemini controls the browser" is accurate; "Gemini launches the app" is
    not. See tasks/task_4.md §1.

    `headless` defaults to True for automated pipeline runs (agents/test_runner.py
    always uses this default — the pipeline itself doesn't need a display).
    Pass headless=False with DISPLAY=:99 set in the calling shell to watch
    Computer Use work live over VNC on Ubuntu — see tasks/task_5.md §3/§4.
    Headed mode on macOS crashes Playwright's bundled Chromium on Apple
    Silicon (SIGBUS); Ubuntu is the confirmed environment for this project.

    Returns:
        dict with status ("passed"/"failed"/"blocked"), screenshot_path,
        actions_taken (each with its stated `intent`), final_text, and `log`
        — a list of structured events covering all five categories
        docs/computer_use.md asks clients to log: prompt, screenshot,
        function_call, safety response, executed action (tasks/task_4.md §2.5).
        The caller (runner.py) writes each `log` entry to RunLog.
    """
    client        = genai.Client(api_key=settings.GEMINI_API_KEY)
    actions_taken = []
    status        = "failed"
    final_text    = ""
    turn          = 0
    log: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": screen_width, "height": screen_height})
        page    = context.new_page()
        page.goto(url)

        screenshot_bytes = page.screenshot(type="png")
        log.append({"category": "prompt", "instruction": instruction, "url": url})
        log.append({"category": "screenshot", "turn": 0, "url": page.url})

        interaction = client.interactions.create(
            model              = MODEL,
            system_instruction = SYSTEM_INSTRUCTION,
            input = [
                {"type": "text",  "text": instruction},
                {"type": "image", "data": base64.b64encode(screenshot_bytes).decode("utf-8"),
                 "mime_type": "image/png"},
            ],
            tools = TOOLS,
        )

        for turn in range(TURN_LIMIT):
            function_calls = [s for s in interaction.steps if s.type == "function_call"]

            if not function_calls:
                final_text = _extract_final_text(interaction)
                status     = "passed"
                break

            for fc in function_calls:
                log.append({"category": "function_call", "turn": turn, "name": fc.name, "args": fc.arguments})

            blocked, acknowledge_ids = _log_safety_decisions(function_calls, log, turn)
            if blocked:
                status     = "blocked"
                final_text = "Action blocked by safety system; halted per policy (see tasks/task_4.md §2.3)."
                break

            results = _execute_function_calls(function_calls, page, screen_width, screen_height)
            for call_id in acknowledge_ids:
                # Must be echoed back in the function_result payload, not just
                # noted on the incoming call — the API rejects the next turn
                # otherwise with "safety decision ... must be acknowledged in
                # the corresponding function response."
                results.setdefault(call_id, {})["safety_acknowledgement"] = True

            for fc in function_calls:
                actions_taken.append({
                    "action": fc.name,
                    "args"  : fc.arguments,
                    "intent": fc.arguments.get("intent", ""),
                })
                log.append({
                    "category": "executed_action",
                    "turn"    : turn,
                    "name"    : fc.name,
                    "result"  : results.get(fc.id, {}),
                })

            page.wait_for_load_state(timeout=5000)
            function_responses = _build_function_responses(page, function_calls, results)
            log.append({"category": "screenshot", "turn": turn + 1, "url": page.url})

            interaction = client.interactions.create(
                model                   = MODEL,
                system_instruction      = SYSTEM_INSTRUCTION,
                previous_interaction_id = interaction.id,
                input                   = function_responses,
                tools                   = TOOLS,
            )

        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_path = str(EVIDENCE_DIR / f"{instruction[:30].replace(' ', '_')}_{turn}.png")
        page.screenshot(path=screenshot_path)
        browser.close()

    return {
        "status"         : status,
        "screenshot_path": screenshot_path,
        "actions_taken"  : actions_taken,
        "final_text"     : final_text,
        "log"            : log,
    }


def _log_safety_decisions(function_calls, log: list[dict], turn: int) -> tuple[bool, list[str]]:
    """Handles safety_decision explicitly per tasks/task_4.md §2.3 — never a
    silent pass-through. `blocked` halts the run (the model's own hard stop).
    `require_confirmation` is auto-acknowledged for this project (the target
    is always a disposable test app, never a real transaction), but every
    such event is still logged so the run's history shows exactly which
    actions crossed that threshold.

    Returns (blocked, acknowledge_ids) — acknowledge_ids is the list of
    function_call ids whose function_result must carry
    safety_acknowledgement=True. The API rejects the next turn if a
    require_confirmation decision isn't echoed back in the response, so the
    caller must apply this to the outgoing result, not the incoming call."""
    blocked        = False
    acknowledge_ids: list[str] = []

    for fc in function_calls:
        safety = fc.arguments.get("safety_decision")
        if not safety:
            continue

        decision = safety.get("decision")
        log.append({
            "category": "safety_response",
            "turn"    : turn,
            "name"    : fc.name,
            "decision": decision,
            "explanation": safety.get("explanation", ""),
        })

        if decision == "blocked":
            blocked = True
        elif decision == "require_confirmation":
            acknowledge_ids.append(fc.id)

    return blocked, acknowledge_ids


def _denorm_x(x: int, w: int) -> int:
    return int(x / 1000 * w)


def _denorm_y(y: int, h: int) -> int:
    return int(y / 1000 * h)


def _execute_function_calls(function_calls, page, w, h) -> dict:
    """Maps 3.5 Flash streamlined action names to Playwright calls.
    Real action set, per docs/computer_use.md 'Browser environment' table:
    click, double_click, triple_click, middle_click, right_click, mouse_down,
    mouse_up, move, type, drag_and_drop, wait, press_key, key_down, key_up,
    hotkey, take_screenshot, scroll, go_back, navigate, go_forward."""
    results = {}

    for fc in function_calls:
        name = fc.name
        args = fc.arguments
        out  = {}

        try:
            if name in ("click", "double_click", "triple_click", "middle_click", "right_click", "move", "mouse_down", "mouse_up"):
                x, y = _denorm_x(args["x"], w), _denorm_y(args["y"], h)
                if   name == "click":        page.mouse.click(x, y)
                elif name == "double_click": page.mouse.dblclick(x, y)
                elif name == "right_click":  page.mouse.click(x, y, button="right")
                elif name == "middle_click": page.mouse.click(x, y, button="middle")
                elif name == "move":         page.mouse.move(x, y)
                elif name == "mouse_down":   page.mouse.down()
                elif name == "mouse_up":     page.mouse.up()
            elif name == "type":
                if "x" in args and "y" in args:
                    page.mouse.click(_denorm_x(args["x"], w), _denorm_y(args["y"], h))
                page.keyboard.type(args["text"])
                if args.get("press_enter"):
                    page.keyboard.press("Enter")
            elif name == "scroll":
                x, y  = _denorm_x(args["x"], w), _denorm_y(args["y"], h)
                delta = args.get("magnitude_in_pixels", 300)
                dx    = delta if args["direction"] == "right" else (-delta if args["direction"] == "left" else 0)
                dy    = delta if args["direction"] == "down"  else (-delta if args["direction"] == "up"   else 0)
                page.mouse.move(x, y)
                page.mouse.wheel(dx, dy)
            elif name == "navigate":   page.goto(args["url"])
            elif name == "go_back":    page.go_back()
            elif name == "go_forward": page.go_forward()
            elif name == "press_key":  page.keyboard.press(args["key"])
            elif name == "hotkey":     page.keyboard.press("+".join(args["keys"]))
            elif name == "wait":       time.sleep(args.get("seconds", 1))
            elif name == "drag_and_drop":
                sx, sy = _denorm_x(args["start_x"], w), _denorm_y(args["start_y"], h)
                ex, ey = _denorm_x(args["end_x"], w),   _denorm_y(args["end_y"], h)
                page.mouse.move(sx, sy)
                page.mouse.down()
                page.mouse.move(ex, ey)
                page.mouse.up()
            elif name == "take_screenshot":
                pass  # screenshot captured below regardless

            page.wait_for_load_state(timeout=5000)

        except Exception as e:
            out["error"] = str(e)

        results[fc.id] = out

    return results


def _build_function_responses(page, function_calls, results) -> list[dict]:
    """Per docs/computer_use.md step 4: send one function_result per call,
    each carrying text (JSON: url + result) AND a fresh screenshot."""
    screenshot_bytes = page.screenshot(type="png")
    screenshot_b64   = base64.b64encode(screenshot_bytes).decode("utf-8")
    current_url      = page.url
    responses        = []

    for fc in function_calls:
        responses.append({
            "type":    "function_result",
            "name":    fc.name,
            "call_id": fc.id,
            "result": [
                {"type": "text",  "text": json.dumps({"url": current_url, **results[fc.id]})},
                {"type": "image", "data": screenshot_b64, "mime_type": "image/png"},
            ],
        })

    return responses


def _extract_final_text(interaction) -> str:
    texts = []
    for step in interaction.steps:
        if step.type == "model_output":
            for block in getattr(step, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    texts.append(block.text)
    return " ".join(texts)
