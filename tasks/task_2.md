# task_2.md — Run Execution API + Environment Model + Revised Tables

Companion to `CLAUDE.md` and `task_1.md`. This task does three things:

1. **Corrects `CLAUDE.md` §8** — the Computer Use code sample there guessed at API shapes
   that turned out to be wrong once the real docs came in. §1 below is the corrected version;
   treat it as replacing `CLAUDE.md` §8 entirely.
2. Specifies the **`POST /api/agent/execute` endpoint** that kicks off a pipeline run against
   a target app, including the payload shape for "what app, what kind of app, what
   environment."
3. **Revises the database tables** from `task_1.md` §4 to add the run/session/environment
   layer that was missing — `task_1.md` assumed a session already existed; this task defines
   how one gets created and what "environment" means as a first-class row, not just a string
   ID passed around in function calls.

## 1. Correcting `CLAUDE.md` §8 — the real Computer Use shape

Everything in the original §8 that referenced `client.models.generate_content`,
`types.ComputerUse`, or `environment="ENVIRONMENT_BROWSER"` was an educated guess made
before the real docs were available. **Discard that code.** Here is the corrected version,
now grounded directly in the fetched `docs/computer_use.md`.

### Corrected `src/qa_sentinel/tools/computer_use.py`

```python
import base64
import json
import time

from google import genai
from playwright.sync_api import sync_playwright


MODEL      = "gemini-3.5-flash"
TURN_LIMIT = 15


def run_ui_test_step(
    instruction:  str,
    url:          str,
    screen_width:  int = 1440,
    screen_height: int = 900,
) -> dict:
    """Drives the target app's UI via Gemini Computer Use to execute one test step.

    Uses client.interactions.create with the computer_use tool — NOT
    generate_content, and NOT a types.ComputerUse object. The tool is a plain
    dict: {"type": "computer_use", "environment": "browser"}.

    Returns:
        dict with status ("passed"/"failed"/"blocked"), screenshot_path,
        actions_taken (each with its stated `intent`), and final_text.
    """
    client        = genai.Client()
    actions_taken = []
    status        = "failed"
    final_text    = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": screen_width, "height": screen_height})
        page    = context.new_page()
        page.goto(url)

        screenshot_bytes = page.screenshot(type="png")

        interaction = client.interactions.create(
            model = MODEL,
            input = [
                {"type": "text",  "text": instruction},
                {"type": "image", "data": base64.b64encode(screenshot_bytes).decode("utf-8"),
                 "mime_type": "image/png"},
            ],
            tools = [{
                "type":        "computer_use",
                "environment": "browser",
                "enable_prompt_injection_detection": True,
            }],
        )

        for turn in range(TURN_LIMIT):
            function_calls = [s for s in interaction.steps if s.type == "function_call"]

            if not function_calls:
                final_text = _extract_final_text(interaction)
                status     = "passed"
                break

            results = _execute_function_calls(function_calls, page, screen_width, screen_height)

            if any(r.get("blocked") for r in results.values()):
                status     = "blocked"
                final_text = "Action blocked by safety system; halted."
                break

            for fc in function_calls:
                actions_taken.append({
                    "action": fc.name,
                    "args":   fc.arguments,
                    "intent": fc.arguments.get("intent", ""),
                })

            function_responses = _build_function_responses(page, function_calls, results)

            interaction = client.interactions.create(
                model                    = MODEL,
                previous_interaction_id  = interaction.id,
                input                    = function_responses,
                tools = [{
                    "type":        "computer_use",
                    "environment": "browser",
                    "enable_prompt_injection_detection": True,
                }],
            )

        screenshot_path = f"/tmp/qa_sentinel/{instruction[:30].replace(' ', '_')}_{turn}.png"
        page.screenshot(path=screenshot_path)
        browser.close()

    return {
        "status":          status,
        "screenshot_path": screenshot_path,
        "actions_taken":   actions_taken,
        "final_text":      final_text,
    }


def _denorm_x(x: int, w: int) -> int: return int(x / 1000 * w)
def _denorm_y(y: int, h: int) -> int: return int(y / 1000 * h)


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

        safety = args.get("safety_decision")
        if safety and safety.get("decision") == "require_confirmation":
            # Hackathon default: auto-confirm non-destructive UI confirmations
            # (this is a QA agent clicking through its OWN test app, not a
            # production purchase flow) — but never auto-confirm FINANCIAL_TRANSACTIONS
            # or LEGAL_TERMS_AND_AGREEMENTS categories; block those and report up.
            out["safety_acknowledgement"] = True

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
            elif name == "navigate":  page.goto(args["url"])
            elif name == "go_back":   page.go_back()
            elif name == "go_forward": page.go_forward()
            elif name == "press_key": page.keyboard.press(args["key"])
            elif name == "hotkey":    page.keyboard.press("+".join(args["keys"]))
            elif name == "wait":      time.sleep(args.get("seconds", 1))
            elif name == "drag_and_drop":
                sx, sy = _denorm_x(args["start_x"], w), _denorm_y(args["start_y"], h)
                ex, ey = _denorm_x(args["end_x"], w),   _denorm_y(args["end_y"], h)
                page.mouse.move(sx, sy); page.mouse.down()
                page.mouse.move(ex, ey); page.mouse.up()
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
```

Key corrections baked in above, each traceable to `docs/computer_use.md`:

- `client.interactions.create(model=..., input=..., tools=[{"type": "computer_use",
  "environment": "browser", ...}])` — not `generate_content`, not a `types.ComputerUse`
  object.
- `environment` is `"browser"` / `"mobile"` / `"desktop"` (lowercase strings), matching
  `task_2.md`'s app-type payload in §2 below directly — this is the field that decides which
  action table applies.
- Multi-turn continuation via `previous_interaction_id` plus resending `function_result`
  steps that bundle **both** a JSON text blob and a fresh screenshot — both are required per
  turn, not just the screenshot.
- `safety_decision` handling is now explicit rather than silently ignored. **Decide this
  policy explicitly for the hackathon**: since QA Sentinel only ever acts on its own
  disposable target app (never a real production system, a purchase flow, or anyone's real
  account), auto-confirming most `require_confirmation` prompts is reasonable — but the code
  above still leaves `FINANCIAL_TRANSACTIONS` and `LEGAL_TERMS_AND_AGREEMENTS` categories
  unhandled/blocking, since those categories existing on a *test* app at all would itself be
  worth flagging as a bug, not clicking through.
- Coordinate range is 0-999, and denormalization divides by 1000 — matches the docs exactly.

## 2. `POST /api/agent/execute` — the run-kickoff endpoint

This is a Next.js Route Handler (not a Server Action, since this needs to be callable from
outside the browser — curl, a CI hook, a "run now" button) living in the `web/` app,
alongside the dashboard from `task_1.md`. It **enqueues a pipeline run** — it does not run
the ADK `Workflow` synchronously in the request/response cycle, since a full multi-feature
test run can take minutes and an HTTP request shouldn't hold that connection open.

### Payload shape

```typescript
// web/src/lib/types.ts — the request body for POST /api/agent/execute

type AppTarget =
  | {
      app_type:     "webapp";
      base_url:     string;              // e.g. "http://demo-target-app:3001"
      repo_url:     string;               // for FixWriter to clone and patch
      computer_use_environment: "browser"; // ALWAYS "browser" for webapp — see note below
    }
  | {
      app_type:     "native_mobile";
      package_name: string;                // e.g. "com.example.demoapp"
      apk_path:     string;                // path/URL to a build artifact to install
      repo_url:     string;
      computer_use_environment: "mobile";
    }
  | {
      app_type:     "native_desktop";
      binary_path:  string;
      repo_url:     string;
      computer_use_environment: "desktop";
    };

interface ExecuteRequest {
  target:        AppTarget;
  test_criteria: {
    app_name: string;
    steps: Array<{
      step_id:             string;
      instruction:         string;
      depends_on:          string[];
      expected_outcome:    string;
      failure_class_hints?: string[];
    }>;
  };
  // Optional: reuse a prior environment (Antigravity sandbox) instead of provisioning fresh.
  // See §3 for what "environment" means as a row, not just this ID.
  environment_id?: string;
}
```

**Note on `computer_use_environment` being redundant with `app_type`:** it's kept as an
explicit field rather than derived, because the mapping isn't quite 1:1 forever — a
`webapp` tested via a wrapped WebView on mobile might legitimately want
`computer_use_environment: "mobile"` even though `app_type` says `webapp`. Keep them
separate fields; derive a sane default in the handler, but let the caller override it.

For this hackathon: **you almost certainly only need `webapp`.** Don't build out real
support for `native_mobile`/`native_desktop` unless the demo target app genuinely needs it —
include them in the type union so the schema is honest about what Computer Use *supports*
(browser, mobile, desktop are all real per `docs/computer_use.md`), but only implement the
`webapp` code path. This keeps the type honest without wasting build time on unused paths.

### Route handler

```typescript
// web/src/app/api/agent/execute/route.ts
import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { randomUUID } from "crypto";

export async function POST(req: NextRequest) {
  const body = await req.json();  // validate against ExecuteRequest with zod in practice

  // 1. Create the Run row up front — status "queued" — so the dashboard can show it
  //    immediately, even before the Python pipeline has picked it up.
  const run = await db.run.create({
    data: {
      appType:        body.target.app_type,
      appName:        body.test_criteria.app_name,
      baseUrl:        body.target.base_url ?? null,
      repoUrl:        body.target.repo_url,
      environmentId:  body.environment_id ?? null,
      status:         "queued",
    },
  });

  // 2. Create Step rows from the test_criteria, all "pending", linked to this run.
  await db.step.createMany({
    data: body.test_criteria.steps.map((s: any) => ({
      id:              randomUUID(),
      runId:           run.id,
      stepId:          s.step_id,
      instruction:     s.instruction,
      dependsOn:       s.depends_on,
      expectedOutcome: s.expected_outcome,
      status:          "pending",
    })),
  });

  // 3. Hand off to the Python pipeline. Simplest hackathon-weekend option: the
  //    Python side polls `runs` for status="queued" (see §4) rather than this
  //    route trying to invoke Python directly over HTTP — avoids building a
  //    second API surface just for this handoff.
  //    If you'd rather push instead of poll, add a lightweight internal POST
  //    from here to the ADK app's own runner endpoint — only do this if the
  //    poll-based approach proves too slow to demo live.

  return NextResponse.json({ run_id: run.id, status: "queued" }, { status: 202 });
}
```

**Poll vs. push, pick one and move on:** the comment above defaults to polling because it's
the lower-integration-risk choice for a hackathon weekend — the Python pipeline already has
a database connection (per `CLAUDE.md` §17 `session_store.py`), so having it poll
`SELECT * FROM runs WHERE status = 'queued' ORDER BY created_at LIMIT 1` on a short interval
costs nothing extra to build. Only build a push-based webhook if the poll latency is visibly
a problem in rehearsal — don't build both.

## 3. Environment as a first-class row, not just a string passed around

`CLAUDE.md` treated `environment_id` as an opaque string handed between function calls. That
was fine for the pipeline's internal logic, but the dashboard (`task_1.md`) and this
execute endpoint both need to **show and reason about** environment state — is it fresh,
reused, idle, offline, gone — so it needs to be a real row, not just a value threaded through
Python calls.

```prisma
model Environment {
  id              String   @id @db.Uuid   // matches Antigravity's own environment_id verbatim
  status          String   @default("active")  // active | idle | offline | deleted
  sourceRepoUrl   String?  @map("source_repo_url")
  createdAt       DateTime @default(now()) @map("created_at")
  lastActiveAt    DateTime @default(now()) @map("last_active_at")
  runs            Run[]

  @@map("environments")
}
```

The `status` field mirrors the lifecycle documented in `docs/environment.md` (Created →
Active → Idle after 15 min → Offline after auto-snapshot, retained 7 days → Deleted) — the
Python pipeline updates this row whenever it observes a status change from the Antigravity
API, so the dashboard can show "this run's environment went idle at 2:14 AM, auto-snapshot
taken, still resumable" without querying Google's API just to render a page.

## 4. Revised tables — adding the `Run` layer above `Session`/`Step`

`task_1.md` §4 defined `Session` → `Step` → `Evidence`/`ReviewDecision`. That's still
correct for *what happened during* a pipeline invocation, but it never defined **how a run
gets kicked off or what "app under test" means as data** — this task adds that layer above
it. Rename `Session` to `Run` for clarity (a "run" is triggered by the execute endpoint; a
"session" was ambiguous about whether it meant one run or one Antigravity environment).

```prisma
// web/prisma/schema.prisma — full revised shape

model Run {
  id             String       @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  appType        String       @map("app_type")          // webapp | native_mobile | native_desktop
  appName        String       @map("app_name")
  baseUrl        String?      @map("base_url")
  repoUrl        String       @map("repo_url")
  environmentId  String?      @map("environment_id") @db.Uuid
  environment    Environment? @relation(fields: [environmentId], references: [id])
  status         String       @default("queued")         // queued | running | completed | failed
  createdAt      DateTime     @default(now()) @map("created_at")
  completedAt    DateTime?    @map("completed_at")
  steps          Step[]
  logs           RunLog[]

  @@map("runs")
}

model Environment {
  id            String   @id @db.Uuid
  status        String   @default("active")             // active | idle | offline | deleted
  sourceRepoUrl String?  @map("source_repo_url")
  createdAt     DateTime @default(now()) @map("created_at")
  lastActiveAt  DateTime @default(now()) @map("last_active_at")
  runs          Run[]

  @@map("environments")
}

model Step {
  id              String          @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  runId           String          @map("run_id") @db.Uuid
  run             Run             @relation(fields: [runId], references: [id])
  stepId          String          @map("step_id")
  instruction     String
  dependsOn       String[]        @map("depends_on")
  expectedOutcome String          @map("expected_outcome")
  status          String          @default("pending")     // pending | passed | failed | blocked | fixed_and_verified
  evidence        Evidence?
  reviewDecision  ReviewDecision?
  prUrl           String?         @map("pr_url")
  createdAt       DateTime        @default(now()) @map("created_at")

  @@unique([runId, stepId])
  @@map("steps")
}

model Evidence {
  id                String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  stepId            String   @unique @map("step_id") @db.Uuid
  step              Step     @relation(fields: [stepId], references: [id])
  screenshotPath    String   @map("screenshot_path")
  consoleErrors     Json     @map("console_errors")
  networkFailures   Json     @map("network_failures")
  modelStatedIntent String   @map("model_stated_intent")
  confidence        Float
  timestamp         DateTime @default(now())

  @@map("evidence_bundles")
}

model ReviewDecision {
  id           String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  stepId       String   @unique @map("step_id") @db.Uuid
  step         Step     @relation(fields: [stepId], references: [id])
  decision     String                                       // approved | rejected | false_positive
  reviewerNote String?  @map("reviewer_note")
  createdAt    DateTime @default(now()) @map("created_at")

  @@map("review_decisions")
}

// NEW — the piece task_1.md didn't have: raw agent activity, one row per
// tool call / interaction turn, for a "what is the agent doing right now"
// live view and for post-hoc debugging when a run behaves unexpectedly.
model RunLog {
  id        String   @id @default(dbgenerated("uuid_generate_v4()")) @db.Uuid
  runId     String   @map("run_id") @db.Uuid
  run       Run      @relation(fields: [runId], references: [id])
  stepId    String?  @map("step_id")                // nullable: some logs are run-level, not step-level
  source    String                                    // "test_runner" | "fix_writer" | "verifier" | "pr_agent"
  eventType String   @map("event_type")               // "tool_call" | "tool_result" | "model_output" | "status_change"
  payload   Json                                       // raw tool args / response / text, whatever's relevant
  createdAt DateTime @default(now()) @map("created_at")

  @@index([runId, createdAt])
  @@map("run_logs")
}
```

### What changed from `task_1.md` and why

- **`Session` → `Run`**: a run is the unit the execute endpoint creates; this matches the
  language in this task's own payload (`ExecuteRequest`) and avoids the ambiguity of
  "session" possibly meaning "Antigravity environment" instead.
- **`Environment` is now its own table**, referenced by `Run`, rather than a bare string.
  This is what lets the dashboard show environment lifecycle state without an extra API
  call, per §3.
- **`RunLog` is new** and wasn't in `task_1.md` at all. This is the piece your message is
  asking for under "the logs" — a running trace of what each agent (`TestRunner`,
  `FixWriter`, `Verifier`, `PRAgent`) actually did, turn by turn, independent of the final
  `Evidence` row. `Evidence` is the **curated, judged** artifact (console errors filtered to
  `level=error`, network failures filtered to `status>=400`); `RunLog` is the **raw, complete**
  trace — every tool call, every intent, every `function_result`. Keep both: `Evidence` is
  what a judge reads in 10 seconds, `RunLog` is what a developer reads when something went
  wrong and they need to know exactly what the agent tried and why.
- **`Run.status` and `Step.status` are separate fields** — a run can be `"running"` while
  individual steps are a mix of `"passed"`/`"pending"`/`"blocked"`. Don't conflate these into
  one status field; the dashboard's session-list view (`task_1.md` §1) needs the run-level
  rollup, while the step timeline needs per-step granularity.

## 5. What the dashboard (`task_1.md`) needs to add given this revision

- Rename all `Session`/`session` references in `task_1.md`'s components to `Run`/`run` —
  `SessionList.tsx` → `RunList.tsx`, `sessions/[sessionId]/page.tsx` →
  `runs/[runId]/page.tsx`, etc. Mechanical rename, no new logic.
- Add a small **live activity feed** on the run detail page, reading `RunLog` ordered by
  `createdAt`, auto-refreshing on the same `router.refresh()` interval already specified in
  `task_1.md` §6. This is the one addition that's worth the build time — "watch the agent's
  raw trace scroll by" is a genuinely strong live-demo moment, distinct from (and more
  granular than) the curated evidence panel. Keep it as a simple scrolling list of
  `{source}: {eventType} — {short payload summary}`, not a fancy timeline visualization —
  per `task_1.md` §9, resist turning this into an analytics feature.
- A "Run new test" trigger is **not** part of the dashboard's own UI per `task_1.md` §0/§9 —
  that's what `POST /api/agent/execute` is for, called via curl/CI/a script, not a form in
  the dashboard. Keep the dashboard read-only plus the single review action; don't add an
  execute-trigger button to it even though the endpoint now exists, or you've reintroduced
  the "dashboard as control panel" risk the framing section warned against.

## 6. Build order for this task

1. Fix `src/qa_sentinel/tools/computer_use.py` per §1 — this blocks all real Computer Use
   testing, so do it first regardless of what else is in flight.
2. Add `Run`, `Environment`, `RunLog` models to `web/prisma/schema.prisma` per §4, migrate.
3. Rename `Session` → `Run` throughout the `task_1.md`-built dashboard components (mechanical).
4. Build `web/src/app/api/agent/execute/route.ts` per §2, with `zod` validation on the
   request body (don't skip validation just because it's a hackathon — a malformed payload
   silently creating a broken `Run` row is a worse debugging experience under demo pressure).
5. Wire the Python pipeline's `state/session_store.py` to poll `runs` for `status="queued"`,
   pick one up, flip it to `"running"`, and begin writing `Step`/`Evidence`/`RunLog` rows as
   the `Workflow` executes.
6. Add the live activity feed to the run detail page per §5.
7. End-to-end test: `curl -X POST /api/agent/execute` with a real payload against
   `demo_target_app/`, watch the dashboard go from `queued` → `running` → populated steps →
   `completed`, with `RunLog` entries streaming in along the way.