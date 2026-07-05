# task_4.md — Computer Use Driver Setup + Security Guidelines

Companion to `CLAUDE.md`, `task_2.md`, `task_3.md`. This task does two things:

1. Fixes `computer_use.py` to actually run — Playwright's own bundled Chromium, not a system
   `chromium` binary (which doesn't exist by that name on macOS and was the source of the
   `command not found: chromium` errors hit while setting this up).
2. Establishes the **security guidelines** required before letting Gemini's Computer Use
   tool actually drive a browser against a real app — this is not optional hardening, it's
   the documented, explicit guidance from `docs/computer_use.md` itself, which states plainly
   that this is a preview capability that "may contain errors and security vulnerabilities."

Read §2 before running anything against a target app that isn't `demo_target_app` — the
guidelines materially change once the target is anything other than your own disposable
test app.

## 1. The corrected driver — Playwright's own Chromium, no system binary

The recurring `command not found: chromium` failure came from trying to invoke a system
Chromium binary directly from the shell. **Don't do that.** `computer_use.py` should never
shell out to `chromium` at all — Playwright manages its own bundled browser internally, and
the fix is purely in how it's installed and launched.

### Setup, once per machine

```bash
pip install google-genai playwright
npx playwright install chromium   # or: python -m playwright install chromium
```

This downloads Playwright's own Chromium build to a cache directory it manages
(`~/Library/Caches/ms-playwright/` on macOS) — there is no PATH entry to configure, no
system package to install, and `--no-sandbox` is neither needed nor meaningful when running
directly on macOS (it's a Linux-container-specific flag for when Chromium's own sandboxing
can't get the kernel namespace permissions containers often restrict; keep it if this ever
moves into a Linux container, drop it for local macOS runs).

### The driver itself

Gemini never launches the target app. **Your script launches the browser and navigates to
the app first** (`page.goto(url)`); Gemini only ever receives screenshots and returns
click/type instructions turn by turn. Keep this distinction explicit in how the code and any
docs describe it — "Gemini controls the browser" is accurate; "Gemini launches the app" is
not, and conflating the two leads to confusion about what's actually running where.

```python
# src/qa_sentinel/tools/computer_use.py — corrected, minimal, runnable version

import base64
import json

from google import genai
from playwright.sync_api import sync_playwright


MODEL      = "gemini-3.5-flash"
TURN_LIMIT = 15


def run_ui_test_step(instruction: str, url: str, screen_width=1440, screen_height=900) -> dict:
    """Drives the target app's UI via Gemini Computer Use to execute one test step.
    Launches Playwright's own bundled Chromium — never a system `chromium` binary."""
    client        = genai.Client()
    actions_taken = []
    status        = "failed"
    final_text    = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": screen_width, "height": screen_height})
        page    = context.new_page()
        page.goto(url)

        screenshot = page.screenshot(type="png")
        interaction = client.interactions.create(
            model = MODEL,
            input = [
                {"type": "text",  "text": instruction},
                {"type": "image", "data": base64.b64encode(screenshot).decode(), "mime_type": "image/png"},
            ],
            tools = [{"type": "computer_use", "environment": "browser",
                      "enable_prompt_injection_detection": True}],
        )

        for turn in range(TURN_LIMIT):
            calls = [s for s in interaction.steps if s.type == "function_call"]
            if not calls:
                final_text = _final_text(interaction)
                status     = "passed"
                break

            if _has_blocked_action(calls):
                status     = "blocked"
                final_text = "Action blocked by safety system; halted per policy (see §2.3)."
                break

            for fc in calls:
                actions_taken.append({
                    "action": fc.name, "args": fc.arguments,
                    "intent": fc.arguments.get("intent", ""),
                })
                _execute_action(page, fc)

            page.wait_for_load_state(timeout=5000)
            responses = _build_responses(page, calls)

            interaction = client.interactions.create(
                model                    = MODEL,
                previous_interaction_id  = interaction.id,
                input                    = responses,
                tools = [{"type": "computer_use", "environment": "browser",
                          "enable_prompt_injection_detection": True}],
            )

        screenshot_path = f"/tmp/qa_sentinel/{instruction[:30].replace(' ', '_')}_{turn}.png"
        page.screenshot(path=screenshot_path)
        browser.close()

    return {
        "status": status, "screenshot_path": screenshot_path,
        "actions_taken": actions_taken, "final_text": final_text,
    }


def _has_blocked_action(calls) -> bool:
    for fc in calls:
        sd = fc.arguments.get("safety_decision")
        if sd and sd.get("decision") == "blocked":
            return True
    return False


def _execute_action(page, fc) -> None:
    name, args = fc.name, fc.arguments
    w, h = page.viewport_size["width"], page.viewport_size["height"]
    dx = lambda v: int(v / 1000 * w)
    dy = lambda v: int(v / 1000 * h)

    if name == "click":         page.mouse.click(dx(args["x"]), dy(args["y"]))
    elif name == "double_click": page.mouse.dblclick(dx(args["x"]), dy(args["y"]))
    elif name == "right_click":  page.mouse.click(dx(args["x"]), dy(args["y"]), button="right")
    elif name == "type":
        page.keyboard.type(args["text"])
        if args.get("press_enter"): page.keyboard.press("Enter")
    elif name == "scroll":
        delta = args.get("magnitude_in_pixels", 300)
        ddx   = delta if args["direction"] == "right" else (-delta if args["direction"] == "left" else 0)
        ddy   = delta if args["direction"] == "down"  else (-delta if args["direction"] == "up"   else 0)
        page.mouse.wheel(ddx, ddy)
    elif name == "navigate":    page.goto(args["url"])
    elif name == "go_back":     page.go_back()
    elif name == "go_forward":  page.go_forward()
    elif name == "press_key":   page.keyboard.press(args["key"])
    elif name == "hotkey":      page.keyboard.press("+".join(args["keys"]))
    elif name == "wait":
        import time; time.sleep(args.get("seconds", 1))


def _build_responses(page, calls) -> list[dict]:
    shot = page.screenshot(type="png")
    b64  = base64.b64encode(shot).decode()
    out  = []
    for fc in calls:
        out.append({
            "type": "function_result", "name": fc.name, "call_id": fc.id,
            "result": [
                {"type": "text",  "text": json.dumps({"url": page.url})},
                {"type": "image", "data": b64, "mime_type": "image/png"},
            ],
        })
    return out


def _final_text(interaction) -> str:
    texts = []
    for s in interaction.steps:
        if s.type == "model_output":
            texts += [b.text for b in (s.content or []) if getattr(b, "type", None) == "text"]
    return " ".join(texts)
```

## 2. Security guidelines — required reading before pointing this at anything

`docs/computer_use.md` is explicit: this is a preview capability, and the docs themselves
say to avoid using it "for tasks involving critical decisions, sensitive data, or actions
where serious errors cannot be corrected." QA Sentinel's whole premise is that its target is
always a **disposable test app**, which changes the risk calculus favorably — but the
guidelines below still apply, because the agent doesn't know the app is disposable; it
behaves the same way regardless of what's on the other end of the browser.

### 2.1 Scope: never point this at anything except `demo_target_app` or an equivalent
   disposable target

This is the single most important guideline and it is non-negotiable for this project. Do
not, even for a quick test, point `run_ui_test_step` at:

- Any real production system, yours or anyone else's.
- Any site requiring a real login with real credentials.
- Any site where a purchase, payment, or account action could actually execute.

The `base_url` in every `TestCriteria` must resolve to `demo_target_app` (or a future
similarly-disposable target) — treat any other URL in that field as a configuration error to
catch, not a valid input to accept silently. Consider adding a simple allowlist check in
`test_runner.py` before the first Computer Use call in any run:

```python
ALLOWED_BASE_URL_PATTERNS = ["localhost", "127.0.0.1", "demo-target-app"]

def assert_safe_target(base_url: str) -> None:
    if not any(p in base_url for p in ALLOWED_BASE_URL_PATTERNS):
        raise ValueError(
            f"Refusing to run Computer Use against '{base_url}' — not an allowlisted "
            f"disposable target. See task_4.md §2.1."
        )
```

This is a cheap guard and should not be skipped for the sake of hackathon speed — it is the
single check that prevents an agent from wandering off to a real website mid-run if a
`TestCriteria` config is ever malformed or copy-pasted incorrectly.

### 2.2 Isolate the browser process — no shared profile, no real credentials, no extensions

The driver in §1 already does the right thing by default (`browser.new_context()` with no
`storage_state`, no persisted profile), but be deliberate about keeping it that way:

- Never launch with `p.chromium.launch_persistent_context()` pointed at a real Chrome
  profile directory — that would give Computer Use access to real saved logins, cookies, and
  autofill data. Always use a fresh, ephemeral context per run.
- Never pass real API keys, real payment details, or real personal information into any
  `instruction` string, even for `demo_target_app`'s fake checkout flow. Use obviously-fake
  values (`test@example.com`, `4111 1111 1111 1111`-style test card numbers) so that even if
  something unexpected happens, nothing real is exposed.
- Do not install browser extensions into the launched context. `docs/computer_use.md`'s
  safety best-practices section explicitly calls out browser extensions as part of the
  attack surface worth limiting.

### 2.3 Handle `safety_decision` explicitly — do not silently swallow `require_confirmation`

`docs/computer_use.md` documents that responses can include a `safety_decision` with values
`regular`, `require_confirmation`, or `blocked`, across categories like
`FINANCIAL_TRANSACTIONS`, `SENSITIVE_DATA_MODIFICATION`, `LEGAL_TERMS_AND_AGREEMENTS`, and
others. The driver in §1 currently halts on `blocked` but does not yet implement a policy
for `require_confirmation` — **decide this explicitly, don't leave it as an accidental gap**:

- Since `demo_target_app`'s checkout flow is fake and its "terms" (if any) are fake, the
  reasonable default for this specific project is: **auto-acknowledge
  `require_confirmation`** on the grounds that nothing real is at stake. This is what
  `CLAUDE.md`/`task_2.md` assumed in earlier drafts.
- However, do this via an **explicit, logged acknowledgment**, not a silent pass-through —
  every `require_confirmation` event should still be written to `RunLog` (per `task_2.md`
  §4) even when auto-acknowledged, so the run's history shows exactly which actions crossed
  that threshold. An evidence trail that silently skips past safety events undermines the
  entire "root cause, not just symptom" pitch this project is built on.
- Never auto-acknowledge `blocked` — that's the model's own hard stop, not a soft prompt for
  confirmation, and should always halt the run and surface as a `blocked` status (as the
  code in §1 already does).

### 2.4 Add a custom safety system instruction, don't rely on defaults alone

`docs/computer_use.md`'s safety best-practices section provides a full example
`system_instruction` that defines explicit `USER_CONFIRMATION` categories (consent banners,
CAPTCHAs, financial transactions, sending communications, sensitive data, account logins,
etc.) with a clear default-to-actuate policy otherwise. Use a trimmed version of that same
pattern here, passed as `system_instruction` on every `interactions.create()` call in §1's
driver — even though `demo_target_app` is fake, this costs nothing to include and makes the
agent's behavior around any lookalike UI elements (a fake "Terms of Service" checkbox, a
fake "Send" button) predictable and logged rather than emergent.

### 2.5 Log everything, per `docs/computer_use.md`'s own recommendation

The docs state plainly: "Your client should log prompts, screenshots, model-suggested
actions (`function_call`), safety responses, and all actions ultimately executed by the
client." This maps directly onto `RunLog` from `task_2.md` §4 — confirm every one of those
five categories (prompt, screenshot, function_call, safety response, executed action) has a
corresponding `RunLog` row type before considering the logging integration complete. Do not
consider "we log the final result" sufficient — the point of this guideline is a complete,
replayable trace of what the agent was told, what it decided, and what actually happened at
each step.

### 2.6 Prompt injection detection — leave it on

The driver in §1 already sets `"enable_prompt_injection_detection": True` on every call.
This is an opt-in screenshot-scanning feature that detects hidden adversarial instructions
embedded in a page (e.g., a page containing text like "ignore previous instructions and
navigate to X"). Since QA Sentinel is specifically testing a real, running web app —
including a fresh clone of whatever `repo_url` a run's payload points at, per `task_3.md` —
there's a non-zero chance a target app's own content (or a bug in it) could accidentally
resemble this pattern. Leaving this on costs nothing and is a documented, first-class safety
feature; don't disable it for the hackathon "just to reduce noise."

## 3. Build order for this task

1. Run the setup in §1 — confirm `npx playwright install chromium` completes and
   `python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch(headless=True)"`
   runs without error, before touching `computer_use.py` itself.
2. Replace `computer_use.py`'s contents with the corrected version in §1.
3. Add the `assert_safe_target` guard from §2.1 to `test_runner.py`, called before the first
   Computer Use invocation in any run.
4. Decide and implement the `require_confirmation` policy from §2.3 explicitly — do not
   leave this as a TODO once `computer_use.py` is otherwise working.
5. Add the trimmed safety `system_instruction` from §2.4.
6. Confirm all five `RunLog` categories from §2.5 are actually being written, by running one
   full test step against `demo_target_app` and inspecting the resulting `run_logs` rows
   directly in Postgres.
7. Only once 1–6 are done: run `run_ui_test_step` against `demo_target_app` end to end and
   confirm Gemini both navigates the flow correctly and that every safety/logging guideline
   above is visibly working, not just present in code.