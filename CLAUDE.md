# CLAUDE.md — QA Sentinel

Build guideline for Claude Code. Read this whole file before writing any code. This is a
RAISE Summit Hackathon 2026 project (Sunday July 5 submission deadline — Vultr / Google
DeepMind In-Person track). Everything here must be built **during the event**; no prior work.

Reference docs already saved at `docs/computer_use.md`, `docs/antigravity_agent.md`,
`docs/environment.md`, `docs/build_managed_agent.md` — these are the authoritative source
for exact API shapes. Where this file gives code, it is consistent with those docs as of
this writing. If a signature here and a signature in `docs/` disagree, `docs/` wins — those
were pulled fresh from Google's own documentation.

## 1. What we are building, in one paragraph

QA Sentinel is an autonomous QA agent that tests a web app the way a careful human QA
engineer would: it drives the UI step-by-step in dependency order (feature 2 cannot be
tested until feature 1 passes), and the moment something looks wrong, it doesn't just
screenshot the failure — it pulls the actual console error and network trace that caused
it, writes a fix with that evidence as grounding, verifies the fix removes the error, and
opens a GitHub PR with the full evidence trail attached. A developer who kicks this off
before bed wakes up to a PR, not a bug report — with a citation trail proving the agent's
diagnosis, not just its confidence.

## 2. Why this satisfies the track statement — explain this back if asked

> "Most agents work from a snapshot ... forget it the second the task ends. Build one that
> can't get away with that ... The primitive you pick should be load-bearing ... Stronger
> still if the second primitive only fires because the first is already running."

Our two primitives:

- **Gemini Computer Use** — the actor. Drives the browser, clicks, types, reads screenshots.
  Load-bearing because without it, no testing happens at all — there is no fallback path.
- **Antigravity agent (Interactions API)** — the memory. Holds test state across the whole
  multi-feature run via `environment_id` reuse. Feature 2's session **cannot start** until
  feature 1's environment confirms pass/fail — this is a hard gate, not a soft dependency.
  The overnight-run story (idle after 15 min → auto-snapshot → offline retention 7 days →
  resume by ID) is native to the platform, not something we built ourselves.

The causal chain that satisfies "stronger still": **chrome-devtools-mcp only fires because
Computer Use's own observation already flagged a discrepancy.** It is dormant on every
passing step. It wakes up exactly once, at the failure moment, pulls console + network
evidence, and goes quiet again. This is the load-bearing, conditionally-triggered link
between "seeing" and "understanding why" — the thing a normal chatbot bolted onto Computer
Use would not have.

**Do not let this drift into "we called three APIs."** Every design decision should be
checked against: *does this tool call happen only because a previous step's own state made
it necessary?* If the answer is "no, we just always call it," reconsider.

## 3. Non-negotiable architectural facts (verified against docs/ — do not deviate)

- **Computer Use and the Antigravity agent cannot be combined in one call.** Per
  `docs/antigravity_agent.md`, the Antigravity agent's unsupported tools list explicitly
  excludes `computer_use` (along with `file_search` and `google_maps`). They are two
  separate agent surfaces that hand off state to each other — never assume you can pass a
  `computer_use` tool into an Antigravity `interactions.create()` call.
- Computer Use has **no ADK-native `BaseTool` wrapper**. It must enter our ADK graph as a
  custom `FunctionTool` — write the raw Gemini agent-loop (screenshot → `computer_use` call →
  parse `function_call` → execute via Playwright → repeat) inside one Python function, and
  let ADK treat the whole loop as a single tool call. See `docs/computer_use.md` for the
  exact agent-loop shape: request includes the tool, config (target environment), the
  prompt, and a screenshot; response includes a `function_call` and (for 3.5 Flash) an
  `intent` field explaining the reasoning, plus a `safety_decision`
  (`regular`/`require_confirmation`/`blocked`).
- **Antigravity function calling is stateful-only.** Per `docs/antigravity_agent.md`: must
  chain via `previous_interaction_id`; manual history reconstruction (stateless mode) is not
  supported for the agent (only for plain `gemini-3.5-flash` interactions). Never try to
  rebuild Antigravity conversation state by hand.
- **`background=True` on Antigravity requires `store=True`** (the default) — don't disable
  `store` on any background call or polling breaks.
- **Antigravity environment lifecycle** (`docs/environment.md`): Created → Active while an
  interaction runs → Idle + auto-snapshot after 15 min inactivity → Offline, retained 7 days,
  resumable by ID → Deleted. This IS our overnight-to-morning mechanism. Do not build a
  custom snapshot/resume system — use the platform's, by reusing `environment_id`.
- **Environment sources**: mount the target app repo directly via
  `{"type": "repository", "source": "<git url>", "target": "/workspace/app"}` in the
  `environment` config object (500 MB limit). For private repos, use the `network.allowlist`
  header-injection pattern in `docs/environment.md` (Basic auth with a GitHub PAT encoded as
  `x-oauth-basic:<PAT>` base64, or Bearer token for GCS) — never put credentials in an env var
  visible inside the sandbox; the egress proxy injects them.
- **chrome-devtools-mcp connects to ADK natively via `McpToolset`** — auto-discovers tools via
  MCP `list_tools` and converts them to ADK `BaseTool` instances. Use `tool_filter` to expose
  only `list_console_messages`, `list_network_requests`, `take_snapshot` — do not expose all
  29 tools; it adds noise to tool selection.
- **Antigravity's own `mcp_server` tool type** can register chrome-devtools-mcp directly
  inside an Antigravity call too (per `docs/antigravity_agent.md` MCP servers section) — this
  is how `Verifier` re-checks the fix without a second ADK round-trip. Requirements: `type`
  must be `"mcp_server"`, `name` must match `^[a-z0-9_-]+$` (strictly lowercase), only
  Streamable HTTP transport is supported (no SSE).
- Model to use throughout: `gemini-3.5-flash` (Computer Use built in natively; do not use the
  older standalone `gemini-2.5-computer-use-preview-10-2025` unless 3.5 Flash is unavailable
  in the demo environment). Antigravity agent string: `antigravity-preview-05-2026`.

## 4. Two-agent-surface architecture (not one agent with many tools)

    ┌─────────────────────────┐          ┌──────────────────────────────┐
    │   Computer Use Loop      │  state   │   Antigravity Agent            │
    │   (raw Gemini API,       │ handoff  │   (Interactions API,           │
    │    driven by our own     │ ───────▶ │    environment=persisted ID)   │
    │    FunctionTool wrapper) │ ◀─────── │                                │
    │                          │          │  - clones target app repo      │
    │  - drives the target app │          │  - writes fix from evidence    │
    │  - takes screenshots     │          │  - re-verifies via chrome-     │
    │  - ACTS, does not diagnose│         │    devtools-mcp itself         │
    └───────────┬──────────────┘          │  - commits, opens PR           │
                │ on discrepancy          └──────────────────────────────┘
                ▼ (conditional, not always-on)
    ┌─────────────────────────┐
    │   chrome-devtools-mcp    │
    │   (McpToolset, native)   │
    │  - list_console_messages │
    │  - list_network_requests │
    │  - take_snapshot          │
    │  WITNESSES, does not act │
    └─────────────────────────┘

All of this is orchestrated by an **ADK `Workflow`** (graph-based execution engine), not a
single monolithic agent. Four `LlmAgent`s, defined under `src/qa_sentinel/agents/`:

1. **TestRunner** — owns Computer Use tool + chrome-devtools-mcp (`McpToolset`). Runs one
   feature's test steps in order. Escalates to chrome-devtools-mcp only on discrepancy.
2. **FixWriter** — owns the Antigravity `FunctionTool` wrapper. Takes an evidence bundle,
   writes a fix in the persisted sandbox environment.
3. **Verifier** — re-invokes chrome-devtools-mcp (via Antigravity's own `mcp_server`
   registration) against the fixed app to confirm the console error is actually gone. Do not
   mark a fix "resolved" without this re-check — this is what separates us from "agent
   guessed a fix and hoped."
4. **PRAgent** — owns a GitHub `FunctionTool`. Commits, opens PR, writes the PR description
   using the full evidence bundle (console line + network response + confidence score) as
   the body — not a vague "fixed a bug" message.

Wire these as `Workflow(edges=[...])` with `before_agent_callback` as the feature-dependency
gate between TestRunner runs, per §7.

## 5. Directory map — build only these files, in this shape

    .
    ├── CLAUDE.md
    ├── PROJECT_STRUCTURE.md
    ├── README.md
    ├── pyproject.toml
    ├── uv.lock
    ├── main.py                          # thin repo-root entrypoint, imports src/qa_sentinel/main.py
    ├── docker/
    │   ├── app/         (Dockerfile)
    │   └── chrome/      (Dockerfile — only needed if Option A, see §15)
    ├── configs/
    │   ├── otel/        (collector-config.yaml)
    │   └── test_criteria/  (example_app.yaml — a TestCriteria instance)
    ├── docs/                             # already populated — read, do not overwrite
    │   ├── computer_use.md
    │   ├── antigravity_agent.md
    │   ├── build_managed_agent.md
    │   └── environment.md
    ├── demo_target_app/                  # the deliberately-buggy app QA Sentinel tests
    ├── scripts/
    │   └── spike_sandbox_headless.py     # Day-1 spike, §15
    ├── src/qa_sentinel/
    │   ├── __init__.py
    │   ├── main.py                       # adk web / adk run wiring, or custom runner
    │   ├── config/
    │   │   ├── __init__.py
    │   │   └── settings.py               # pydantic-settings, reads .env
    │   ├── schemas/                       # already scaffolded — fill in per §6
    │   │   ├── __init__.py
    │   │   ├── test_criteria.py
    │   │   ├── evidence_bundle.py
    │   │   └── review_decision.py
    │   ├── state/
    │   │   ├── __init__.py
    │   │   └── session_store.py          # ADK session state <-> Postgres sync
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   ├── computer_use.py           # §8 — raw Gemini agent-loop wrapped as FunctionTool
    │   │   ├── antigravity.py            # §11 — Interactions API wrapped as FunctionTool
    │   │   ├── chrome_devtools_mcp.py    # §9 — McpToolset config, tool_filter
    │   │   └── github_pr.py              # §13 — commit + PR creation
    │   ├── callbacks/
    │   │   ├── __init__.py
    │   │   ├── evidence_capture.py       # §7 — after_tool_callback: console/network -> state
    │   │   ├── feature_gate.py           # §7 — before_agent_callback: blocks feature N+1
    │   │   └── confidence_scoring.py     # §7 — scores evidence completeness per bug
    │   └── agents/
    │       ├── __init__.py
    │       ├── test_runner.py            # §10
    │       ├── fix_writer.py             # §11
    │       ├── verifier.py               # §12
    │       ├── pr_agent.py               # §13
    │       └── workflow.py               # §14 — root Workflow graph, wiring + gating
    └── tests/
        ├── __init__.py
        ├── unit/
        │   ├── __init__.py
        │   ├── test_evidence_bundle.py
        │   ├── test_feature_gate.py
        │   └── test_confidence_scoring.py
        └── integration/
            ├── __init__.py
            └── test_workflow_e2e.py

Note the two `main.py` files are intentional: repo-root `main.py` is a thin shim so
`uv run main.py` works from the repo root; `src/qa_sentinel/main.py` holds the real wiring.
Do not duplicate logic — the root one just imports and calls the inner one.

## 6. Data contracts — fill these in first, before any agent logic

### `src/qa_sentinel/schemas/test_criteria.py`
The feature-dependency graph and pass/fail rules, as data — never hardcode dependency logic
in Python control flow. The `Workflow` reads this to decide routing.

```python
from pydantic import BaseModel, Field


class TestStep(BaseModel):
    step_id:             str
    instruction:         str                  # natural language, fed to Computer Use
    depends_on:          list[str] = Field(default_factory=list)
    expected_outcome:    str                  # natural language, used for pass/fail comparison
    failure_class_hints: list[str] = Field(default_factory=list)  # "network" | "console" | "visual"


class TestCriteria(BaseModel):
    app_name: str
    base_url: str
    steps:    list[TestStep]

    def steps_by_id(self) -> dict[str, TestStep]:
        return {s.step_id: s for s in self.steps}
```

### `src/qa_sentinel/schemas/evidence_bundle.py`
The four-part record. This is the artifact that makes our "root cause, not just symptom"
claim credible to judges — never save just a screenshot.

```python
from datetime  import datetime
from pydantic  import BaseModel, Field


class EvidenceBundle(BaseModel):
    step_id:            str
    screenshot_path:    str
    console_errors:     list[dict] = Field(default_factory=list)  # level == "error" only
    network_failures:   list[dict] = Field(default_factory=list)  # status >= 400 only
    model_stated_intent: str                                       # Computer Use's `intent` field
    confidence:          float                                     # see §7 — completeness score
    timestamp:           datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_console_evidence(self) -> bool:
        return len(self.console_errors) > 0

    @property
    def has_network_evidence(self) -> bool:
        return len(self.network_failures) > 0
```

### `src/qa_sentinel/schemas/review_decision.py`
Human-in-the-loop feedback. Feeds back into future confidence thresholds — this is the
loop-closing mechanism the track's own examples emphasize (confirm/dismiss retunes next run).

```python
from typing   import Literal
from pydantic import BaseModel


class ReviewDecision(BaseModel):
    step_id:       str
    decision:      Literal["approved", "rejected", "false_positive"]
    reviewer_note: str | None = None
```

## 7. Callbacks — the observability + gating layer

### `src/qa_sentinel/callbacks/feature_gate.py`
Literal implementation of "feature 2 cannot begin until feature 1 is resolved." A
`before_agent_callback` on the TestRunner invocation for each step:

```python
def feature_gate(callback_context) -> dict | None:
    step = callback_context.state["current_step"]          # a TestStep
    for dep_id in step.depends_on:
        dep_status = callback_context.state.get(f"step.{dep_id}.status")
        if dep_status not in ("passed", "fixed_and_verified"):
            return {"skip": True, "reason": f"blocked on {dep_id}={dep_status}"}
    return None                                              # allow to proceed
```

Do not implement this as an if/else chain inside the agent's own instruction prompt — it
must be enforced in code via the callback, not left to the LLM's judgment. The LLM decides
*what* to test; the callback decides *whether it's allowed to test it yet*.

### `src/qa_sentinel/callbacks/evidence_capture.py`
`after_tool_callback` that turns raw chrome-devtools-mcp output into state:

```python
def capture_error_evidence(tool, args, tool_context, tool_response):
    step_id = tool_context.state.get("current_step_id")

    if tool.name == "list_console_messages":
        errors = [m for m in tool_response.get("messages", []) if m.get("level") == "error"]
        if errors:
            tool_context.state[f"evidence.{step_id}.console"] = errors

    if tool.name == "list_network_requests":
        failed = [r for r in tool_response.get("requests", []) if r.get("status", 200) >= 400]
        if failed:
            tool_context.state[f"evidence.{step_id}.network"] = failed

    return tool_response
```

### `src/qa_sentinel/callbacks/confidence_scoring.py`
Mirrors the Vultr track's own finance example almost exactly: a confidence score reflecting
how many flagged transactions were matched to a clear cause versus left unexplained. Ours:

```python
def score_confidence(has_console: bool, has_network: bool, intent_explains: bool) -> float:
    if has_console and has_network and intent_explains:
        return 0.9   # high  -> auto-proceed to FixWriter
    if has_console or has_network:
        return 0.5   # medium -> proceed, flag "partial evidence" in PR description
    return 0.1       # low   -> route to human review, never let FixWriter act on this
```

- **High** confidence: console error + network failure + intent explains the mismatch →
  auto-proceed to FixWriter.
- **Medium** confidence: only one of (console error / network failure) present → proceed but
  flag in the PR description as "partial evidence."
- **Low** confidence: neither present (agent just says "it looked wrong") → route to human
  review instead of auto-fixing. Never let FixWriter act on zero-evidence failures.

This is a genuine differentiator — it shows the agent knows what it doesn't know, rather
than confidently fixing things it can't actually diagnose.

### Evidence escalation trigger — do this deterministically, not via LLM judgment
For a live demo, do not rely on the LLM deciding "should I check console logs now?" — make
it a deterministic `after_tool_callback` check on the Computer Use tool's own result
(place this in `evidence_capture.py` alongside the callback above):

```python
def evidence_escalation_trigger(tool, args, tool_context, tool_response):
    if tool.name == "run_ui_test_step" and tool_response.get("status") != "passed":
        tool_context.state["needs_chrome_devtools_check"] = True
    return tool_response
```

The TestRunner's instruction should read this flag and call chrome-devtools-mcp tools only
when it's set. This is more reliable on stage than trusting model judgment every time, and
it's still accurate to describe as "the agent's own evidence pipeline" when pitching.

## 8. `src/qa_sentinel/tools/computer_use.py` — the Computer Use FunctionTool

Per `docs/computer_use.md`: implement an agent loop that sends the tool + config + prompt +
current screenshot, receives a `function_call` (with an `intent` field on 3.5 Flash
explaining the model's reasoning, and a `safety_decision` of
`regular`/`require_confirmation`/`blocked`), scales normalized coordinates to the viewport,
and executes via Playwright. Loop until the model signals completion or a max-step budget
is hit.

```python
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright


MODEL       = "gemini-3.5-flash"
MAX_STEPS   = 15


def run_ui_test_step(instruction: str, url: str, environment_id: str | None = None) -> dict:
    """Drives the target app's UI via Gemini Computer Use to execute one test step.

    Args:
        instruction: Natural-language description of the UI action to test
                      (e.g. "Click the signup button and verify redirect to onboarding").
        url:         The page URL to test against.
        environment_id: Optional persisted browser/session identifier for
                      multi-step continuity (reserved for future session reuse).

    Returns:
        dict with status ("passed"/"failed"/"blocked"), screenshot_path,
        actions_taken, and the model's final stated intent.
    """
    client         = genai.Client()
    actions_taken  = []
    final_intent   = ""
    status         = "failed"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        page.goto(url)

        for step_num in range(MAX_STEPS):
            screenshot_bytes = page.screenshot()

            response = client.models.generate_content(
                model    = MODEL,
                contents = [
                    types.Content(role="user", parts=[
                        types.Part(text=instruction),
                        types.Part(inline_data=types.Blob(
                            mime_type = "image/png",
                            data      = screenshot_bytes,
                        )),
                    ]),
                ],
                config = types.GenerateContentConfig(
                    tools=[types.Tool(computer_use=types.ComputerUse(
                        environment="ENVIRONMENT_BROWSER",
                    ))],
                ),
            )

            candidate  = response.candidates[0]
            fn_call    = _extract_function_call(candidate)

            if fn_call is None:
                final_intent = _extract_text(candidate) or "Model reported task complete."
                status       = "passed"
                break

            safety = getattr(fn_call, "safety_decision", "regular")
            if safety == "blocked":
                status       = "blocked"
                final_intent = "Action blocked by safety system."
                break

            intent = getattr(fn_call, "intent", "")
            final_intent = intent or final_intent
            actions_taken.append({"action": fn_call.name, "args": fn_call.args, "intent": intent})

            _execute_action(page, fn_call)

        screenshot_path = f"/tmp/qa_sentinel/{instruction[:30].replace(' ', '_')}_{step_num}.png"
        page.screenshot(path=screenshot_path)
        browser.close()

    return {
        "status":          status,
        "screenshot_path": screenshot_path,
        "actions_taken":   actions_taken,
        "final_intent":    final_intent,
    }


def _extract_function_call(candidate):
    for part in candidate.content.parts:
        if getattr(part, "function_call", None):
            return part.function_call
    return None


def _extract_text(candidate) -> str:
    texts = [p.text for p in candidate.content.parts if getattr(p, "text", None)]
    return " ".join(texts)


def _execute_action(page, fn_call) -> None:
    """Maps a computer_use function_call to a Playwright action.
    Coordinates from the model are normalized 0-1000; scale to the actual viewport."""
    name = fn_call.name
    args = fn_call.args
    vw   = page.viewport_size["width"]
    vh   = page.viewport_size["height"]

    if name == "click_at":
        x = int(args["x"] / 1000 * vw)
        y = int(args["y"] / 1000 * vh)
        page.mouse.click(x, y)
    elif name == "type_text":
        page.keyboard.type(args["text"])
    elif name == "scroll":
        page.mouse.wheel(0, args.get("delta_y", 300))
    elif name == "key_press":
        page.keyboard.press(args["key"])
    # extend with additional predefined actions as documented in docs/computer_use.md
```

**IMPORTANT — verify the exact `types.ComputerUse` / `types.Tool` field names against
`docs/computer_use.md` and the installed `google-genai` SDK version before treating this as
final.** The action-name strings (`click_at`, `type_text`, `scroll`, `key_press`) and the
`environment="ENVIRONMENT_BROWSER"` config value are illustrative of the shape described in
the docs, not copy-pasted from a verified working snippet — confirm against the SDK's actual
enum/schema at build time (`python -c "from google.genai import types; help(types.ComputerUse)"`)
since this is a preview API and field names may differ slightly from what's shown here.

## 9. `src/qa_sentinel/tools/chrome_devtools_mcp.py` — McpToolset config

```python
from google.adk.tools.mcp_tool import McpToolset


def build_chrome_devtools_toolset(debugging_url: str = "http://127.0.0.1:9222") -> McpToolset:
    """Connects to the official Chrome DevTools MCP server and exposes only the
    read-only diagnostic tools TestRunner needs — never the action tools (click,
    navigate, fill), since Computer Use already owns acting on the page."""
    return McpToolset(
        connection_params = {"url": debugging_url},
        tool_filter       = [
            "list_console_messages",
            "list_network_requests",
            "take_snapshot",
        ],
    )
```

If running the MCP server as a local subprocess instead of connecting to an existing
instance, follow `chrome-devtools-mcp@latest` stdio launch config
(`npx -y chrome-devtools-mcp@latest [--headless] [--autoConnect]`) and adapt
`connection_params` accordingly; the exact `McpToolset` constructor shape (stdio vs.
URL-based) should be confirmed against the installed `google-adk` version's
`tools-custom/mcp-tools` reference before finalizing.

## 10. `src/qa_sentinel/agents/test_runner.py`

```python
from google.adk.agents import LlmAgent

from qa_sentinel.tools.computer_use          import run_ui_test_step
from qa_sentinel.tools.chrome_devtools_mcp    import build_chrome_devtools_toolset
from qa_sentinel.callbacks.evidence_capture   import capture_error_evidence, evidence_escalation_trigger
from qa_sentinel.callbacks.feature_gate       import feature_gate


chrome_devtools = build_chrome_devtools_toolset()


def _after_tool(tool, args, tool_context, tool_response):
    tool_response = evidence_escalation_trigger(tool, args, tool_context, tool_response)
    tool_response = capture_error_evidence(tool, args, tool_context, tool_response)
    return tool_response


test_runner_agent = LlmAgent(
    name        = "TestRunner",
    model       = "gemini-3.5-flash",
    instruction = (
        "You test web app features one at a time, in dependency order, using "
        "run_ui_test_step to act on the page.\n\n"
        "After each step, compare the resulting screenshot/state against the "
        "expected outcome in the test criteria.\n\n"
        "IF the outcome matches expectations: mark the step passed, move on. "
        "Do NOT call any chrome-devtools tools — there's nothing to diagnose.\n\n"
        "IF the outcome does NOT match (or is ambiguous), and "
        "needs_chrome_devtools_check is set in state: immediately call "
        "list_console_messages and list_network_requests to capture the "
        "technical cause. Never report a failure without this evidence attached. "
        "A failure report with no console/network evidence is incomplete and "
        "must be flagged as low-confidence rather than a resolved bug."
    ),
    tools                 = [run_ui_test_step, chrome_devtools],
    before_agent_callback = feature_gate,
    after_tool_callback   = _after_tool,
)
```

## 11. `src/qa_sentinel/tools/antigravity.py` + `agents/fix_writer.py`

Per `docs/antigravity_agent.md`: use `client.interactions.create(agent=..., environment=...)`,
reuse `environment_id` across calls, use `background=True` + polling for long-running fixes,
and mount the target repo via the `environment.sources` config on the *first* call in a chain.

```python
# tools/antigravity.py
import time
from google import genai


AGENT = "antigravity-preview-05-2026"


def dispatch_fix_to_antigravity(
    evidence: dict,
    repo_url: str,
    environment_id: str | None = None,
    previous_interaction_id: str | None = None,
) -> dict:
    """Sends an evidence bundle to the Antigravity agent to diagnose and write a fix.
    Reuses environment_id across calls so file state and repo clone persist across
    the whole multi-feature test run — this IS the "load-bearing memory" primitive.

    Args:
        evidence: An EvidenceBundle, serialized to dict.
        repo_url: The target app's git repository.
        environment_id: Reuse an existing sandbox if provided; else provision fresh.
        previous_interaction_id: Chain onto a prior interaction for multi-turn state.

    Returns:
        dict with status, environment_id (for reuse), interaction_id (for chaining),
        and the agent's output_text describing the fix.
    """
    client = genai.Client()

    environment = environment_id or {
        "type":    "remote",
        "sources": [{
            "type":   "repository",
            "source": repo_url,
            "target": "/workspace/app",
        }],
    }

    prompt = (
        f"A UI test failed at step '{evidence['step_id']}'.\n"
        f"Console errors: {evidence['console_errors']}\n"
        f"Network failures: {evidence['network_failures']}\n"
        f"Model's stated intent when the failure occurred: {evidence['model_stated_intent']}\n\n"
        "Diagnose the root cause using this evidence, write a fix in /workspace/app, "
        "and explain the fix in one paragraph."
    )

    kwargs = {
        "agent":       AGENT,
        "input":       prompt,
        "environment": environment,
        "background":  True,
    }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    interaction = client.interactions.create(**kwargs)

    while interaction.status == "in_progress":
        time.sleep(5)
        interaction = client.interactions.get(id=interaction.id)

    return {
        "status":          "success" if interaction.status == "completed" else "error",
        "environment_id":  interaction.environment_id,
        "interaction_id":  interaction.id,
        "output_text":     interaction.output_text,
    }
```

```python
# agents/fix_writer.py
from google.adk.agents import LlmAgent
from qa_sentinel.tools.antigravity import dispatch_fix_to_antigravity


fix_writer_agent = LlmAgent(
    name        = "FixWriter",
    model       = "gemini-3.5-flash",
    instruction = (
        "You receive a failed test step's evidence bundle. Only act if confidence "
        "is medium or high (see state['evidence.<step_id>.confidence']) — if low, "
        "do not call dispatch_fix_to_antigravity; instead report that this needs "
        "human review. When you do act, always pass the SAME environment_id used "
        "for prior features in this run, so file state persists across the whole "
        "test session."
    ),
    tools = [dispatch_fix_to_antigravity],
)
```

## 12. `src/qa_sentinel/agents/verifier.py`

Re-invokes chrome-devtools-mcp *inside* the Antigravity call via its `mcp_server` tool type
(per `docs/antigravity_agent.md` MCP servers section), so the fix is verified in the same
persisted environment without a separate ADK round-trip:

```python
from google.adk.agents import LlmAgent
from google.adk.tools   import FunctionTool
from google              import genai


AGENT = "antigravity-preview-05-2026"


def verify_fix(environment_id: str, previous_interaction_id: str, page_url: str) -> dict:
    """Re-runs the app in its fixed state and checks the console for the original
    error via chrome-devtools-mcp, registered as a remote MCP tool on this call."""
    client = genai.Client()

    interaction = client.interactions.create(
        agent                   = AGENT,
        environment              = environment_id,
        previous_interaction_id  = previous_interaction_id,
        input                    = (
            f"Start the app and navigate to {page_url}. Use the chrome_devtools "
            "tools to check the console for errors. Report whether the "
            "originally-reported error is still present."
        ),
        tools = [{
            "type": "mcp_server",
            "name": "chrome_devtools",              # must be lowercase, ^[a-z0-9_-]+$
            "url":  "http://127.0.0.1:9222",         # streamable HTTP only, no SSE
        }],
    )

    return {
        "status":      "resolved" if "no error" in interaction.output_text.lower() else "still_failing",
        "output_text": interaction.output_text,
    }


verifier_agent = LlmAgent(
    name        = "Verifier",
    model       = "gemini-3.5-flash",
    instruction = (
        "Given a fix that was just applied, call verify_fix to confirm the "
        "original console/network error is actually gone before marking this "
        "feature 'fixed_and_verified'. Never trust FixWriter's own claim without "
        "this independent re-check."
    ),
    tools = [FunctionTool(func=verify_fix)],
)
```

## 13. `src/qa_sentinel/tools/github_pr.py` + `agents/pr_agent.py`

```python
# tools/github_pr.py
from github import Github, Auth


def open_evidence_pr(
    repo_full_name: str,
    branch_name:    str,
    base_branch:    str,
    pr_title:       str,
    evidence:       dict,
    fix_summary:    str,
    github_token:   str,
) -> dict:
    """Opens a PR whose description IS the evidence bundle — console line, network
    response, confidence score — not a vague 'fixed a bug' message."""
    auth   = Auth.Token(github_token)
    gh     = Github(auth=auth)
    repo   = gh.get_repo(repo_full_name)

    body = (
        f"## Root cause\n\n"
        f"**Console evidence:**\n```\n{evidence['console_errors']}\n```\n\n"
        f"**Network evidence:**\n```\n{evidence['network_failures']}\n```\n\n"
        f"**Agent's stated intent at failure:** {evidence['model_stated_intent']}\n\n"
        f"**Confidence:** {evidence['confidence']}\n\n"
        f"## Fix\n\n{fix_summary}\n\n"
        f"_Opened automatically by QA Sentinel — verified via re-run before this PR "
        f"was created, not just claimed._"
    )

    pr = repo.create_pull(
        title = pr_title,
        body  = body,
        head  = branch_name,
        base  = base_branch,
    )

    return {"status": "success", "pr_url": pr.html_url, "pr_number": pr.number}
```

```python
# agents/pr_agent.py
from google.adk.agents import LlmAgent
from google.adk.tools   import FunctionTool
from qa_sentinel.tools.github_pr import open_evidence_pr


pr_agent = LlmAgent(
    name        = "PRAgent",
    model       = "gemini-3.5-flash",
    instruction = (
        "Only open a PR for features marked 'fixed_and_verified'. Use the full "
        "evidence bundle as the PR body — never write a vague description. "
        "One PR per feature fixed in this run, not one giant combined PR."
    ),
    tools = [FunctionTool(func=open_evidence_pr)],
)
```

## 14. `src/qa_sentinel/agents/workflow.py` — wiring it all together

```python
from google.adk import Workflow

from qa_sentinel.agents.test_runner import test_runner_agent
from qa_sentinel.agents.fix_writer  import fix_writer_agent
from qa_sentinel.agents.verifier    import verifier_agent
from qa_sentinel.agents.pr_agent    import pr_agent


root_agent = Workflow(
    name  = "qa_sentinel_pipeline",
    edges = [
        ("START",           test_runner_agent),
        (test_runner_agent, fix_writer_agent),   # only proceeds if confidence gate passes
        (fix_writer_agent,  verifier_agent),
        (verifier_agent,    pr_agent),           # only proceeds if verifier confirms fix
    ],
)
```

Wire this into `src/qa_sentinel/main.py` for `adk web src/qa_sentinel` to discover it as
`root_agent` — confirm the expected module-level variable name against
`docs/build_managed_agent.md` / the ADK quickstart before finalizing.

## 15. Environment strategy — decide and confirm on Day 1, do not discover this on Day 2

Two options, pick based on `scripts/spike_sandbox_headless.py` results:

- **Option A (fallback):** Computer Use loop runs locally via Playwright; chrome-devtools-mcp
  points at that same local Chrome (`--autoConnect` if Chrome 144+, else
  `--remote-debugging-port=9222`).
- **Option B (preferred):** Both Computer Use's Playwright driver and chrome-devtools-mcp run
  *inside* the Antigravity sandbox (`environment="remote"`, Ubuntu, Node.js pre-installed per
  `docs/antigravity_agent.md`). Test session and fix session then share the same filesystem
  and `environment_id` — no cross-machine state sync needed. Stronger narrative for judges
  (one persisted environment for the whole task) but must be spiked first — confirm headless
  Chrome + display works in that sandbox before committing.

### Day-1 spike script — `scripts/spike_sandbox_headless.py`

```python
import time
from google import genai


def main():
    client = genai.Client()

    interaction = client.interactions.create(
        agent       = "antigravity-preview-05-2026",
        input       = (
            "Install chromium and node.js tooling if not present. Then run "
            "`npx -y chrome-devtools-mcp@latest --headless --browserUrl "
            "http://127.0.0.1:9222 &` in the background. Confirm the process "
            "started and print its PID."
        ),
        environment = "remote",
        background  = True,
    )

    while interaction.status == "in_progress":
        time.sleep(5)
        interaction = client.interactions.get(id=interaction.id)

    print(f"Status: {interaction.status}")
    print(f"Environment ID: {interaction.environment_id}")
    print(interaction.output_text)

    # Follow-up: confirm list_console_messages actually returns data for a test page,
    # by registering chrome_devtools as an mcp_server tool on a chained call (see §12
    # for the exact tool-registration shape) pointed at a trivial test HTML page.


if __name__ == "__main__":
    main()
```

If any step fails or is unreasonably slow, fall back to Option A (local Playwright + local
chrome-devtools-mcp) without losing further time arguing about it. This result determines
whether `docker/chrome/` is needed at all.

## 16. `pyproject.toml` (uv) — exact shape

```toml
[project]
name            = "qa-sentinel"
version         = "0.1.0"
description     = "Autonomous QA agent: Computer Use + Antigravity + chrome-devtools-mcp"
requires-python = ">=3.12"
dependencies    = [
    "google-adk>=2.0",
    "google-genai>=1.0",
    "playwright>=1.48",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "asyncpg>=0.30",
    "PyGithub>=2.4",
    "opentelemetry-sdk>=1.28",
    "opentelemetry-exporter-otlp>=1.28",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "ruff>=0.7"]

[tool.ruff]
line-length = 100

[build-system]
requires      = ["hatchling"]
build-backend = "hatchling.build"
```

Do not use `requirements.txt` or `pip freeze` anywhere in this repo. Install with `uv sync`
(and `uv run playwright install chromium` once, for Option A). Run with
`uv run adk web src/qa_sentinel`, or `uv run main.py` from repo root.

## 17. Docker Compose — services and when each is needed

- **`app`** — the ADK Workflow process. Builds from `docker/app/Dockerfile` (uv-based,
  multi-stage: `uv sync --frozen`, copy `src/`, run `uv run adk web src/qa_sentinel`).
  Depends on `postgres`, and on `chrome` only if using Option A. Exposes port 8000 for the
  ADK web UI. Mounts `./src` and `./configs` for fast iteration.
- **`postgres`** — `postgres:17-alpine`, stores evidence bundles + session state + review
  decisions. UUID primary keys (`uuid_generate_v4()`, `pgcrypto` or `uuid-ossp` extension),
  never `SERIAL`. Exposes 5432, persists to a named volume.
- **`chrome`** — only if Option A. Builds from `docker/chrome/Dockerfile`: headless Chrome
  with `--remote-debugging-port=9222` exposed, `chrome-devtools-mcp` preinstalled via `npx`.
  Needs `shm_size: "2gb"` to avoid Chrome crashing in the container.
- **`otel-collector`** — optional but recommended: `otel/opentelemetry-collector-contrib`
  image, config from `configs/otel/collector-config.yaml`, OTLP gRPC (4317) and HTTP (4318).
  ADK ships built-in OpenTelemetry instrumentation; wiring this up gives a live
  trace-timeline visual for the demo — "here's the span where Computer Use clicked, here's
  the span where the console error was caught, here's the span where Antigravity wrote the
  fix." Stronger demo artifact than narrating over static screenshots.

If Option B wins the Day-1 spike, the `chrome` service is unnecessary — the Antigravity
sandbox IS the browser host, and `docker/chrome/` can be deleted.

## 18. Code style (apply throughout)

- Vertically align assignment values — pad keys/variable names so `=`/`:` line up in blocks,
  as shown in every code sample above.
- Clear vertical spacing between logical groups within a function.
- UUID primary keys everywhere in Postgres, never `SERIAL`.
- No `---` dividers in generated docs/markdown output.
- Every `FunctionTool` must return a `dict` with a `status` key
  (`"success"`/`"error"`/`"pending"`) per ADK convention — the LLM reasons over this field,
  so make it descriptive, not a bare error code.

## 19. Build order — do not parallelize this out of sequence

1. `scripts/spike_sandbox_headless.py` — confirm environment strategy (§15).
2. `demo_target_app/` — build or select the deliberately-buggy target app FIRST. Nothing
   else can be tested without it.
3. `src/qa_sentinel/schemas/` — all three pydantic models, fully defined (§6), before any
   agent code.
4. `src/qa_sentinel/tools/computer_use.py` — tested standalone against the target app before
   wiring into ADK. Confirm the `types.ComputerUse` field shape against the installed SDK
   first (§8 note).
5. `src/qa_sentinel/tools/chrome_devtools_mcp.py` — confirm `McpToolset` connects and
   `tool_filter` works.
6. `src/qa_sentinel/agents/test_runner.py` — wire Computer Use + chrome-devtools-mcp
   together with the evidence escalation trigger. Test alone against a known-broken feature
   before adding the rest of the pipeline.
7. `src/qa_sentinel/callbacks/feature_gate.py` + `confidence_scoring.py`.
8. `src/qa_sentinel/tools/antigravity.py` + `agents/fix_writer.py` + `agents/verifier.py`.
9. `src/qa_sentinel/tools/github_pr.py` + `agents/pr_agent.py`.
10. `src/qa_sentinel/agents/workflow.py` — wire the full graph.
11. OTel wiring for the live demo trace visual — only after the pipeline works end to end.

## 20. Judging-criteria self-check before demo day

- **Impact (25%)** — one sentence: who this helps and why it's not a toy. ("Any team
  shipping fast without full test coverage; the agent finds root causes, not just symptoms,
  and hands over a reviewable PR, not a bug list.")
- **Demo (50%)** — does it actually run live, end to end, on the target app, with a visible
  moment where chrome-devtools-mcp fires *because* Computer Use flagged something?
- **Creativity (15%)** — the conditional-escalation trigger and the confidence-scoring gate
  are the two "this wasn't obvious" details — make sure both are visible in the pitch, not
  buried in code.
- **Pitch (10%)** — 3 minutes: one paragraph from §1, one diagram from §4, one live moment
  from §7/§15, one screenshot of a real PR it opened.

**Hard rule from the rules doc:** do not let the morning-review screen become the star of
the demo — a project where a dashboard is the main feature is explicitly disqualifying. The
PR + evidence bundle is the deliverable; the review screen is secondary, supporting evidence
only.