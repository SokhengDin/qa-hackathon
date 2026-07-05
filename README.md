# QA Sentinel

An autonomous QA agent that tests a web app the way a careful human QA engineer would: it
drives the UI step by step in dependency order, and the moment something looks wrong, it
pulls the real console/network evidence, writes a fix grounded in that evidence, restarts
the app, re-verifies the fix against the actual failing action, and pushes a branch with
the fix — a developer who kicks this off before bed wakes up to a pushed fix, not a bug
report.

Built during the RAISE Summit Hackathon 2026 (Vultr / Google DeepMind track).

## How it works

Four ADK `LlmAgent`s wired into a `Workflow` graph:

1. **TestRunner** — drives the target app via Gemini Computer Use (a raw agent loop:
   screenshot → model call → parsed action → Playwright execution → repeat), one test step
   at a time, in dependency order. Its own Playwright session listens for real console
   errors and failed (>=400) network responses while it acts — no separate diagnostic
   round-trip needed to know something broke.
2. **FixerAgent** — only runs when TestRunner's own evidence says a step genuinely failed
   with enough signal to act on (deterministic confidence scoring, not an LLM's self-report).
   Clones the target repo locally, reads the suspect file, writes a fix, **restarts the live
   app on the same port**, re-issues the exact request that failed to confirm it's actually
   resolved, and only then commits and pushes a branch — an unverified fix is never pushed.
3. **TestRunner (loop-back)** — control returns to TestRunner, which re-drives the real
   browser flow against the now-fixed, restarted app, using the *original* failing step's
   exact instruction — not a substitute check. This is the actual proof the fix works, not
   just FixerAgent's own claim.
4. **Verifier** — confirms FixerAgent's branch genuinely exists on GitHub before anything
   is marked resolved.
5. **PRAgent** — opens a PR whose body *is* the evidence bundle (console line, network
   response, confidence score, fix summary) — never a vague "fixed a bug" message.

A step that never needed a fix (clean pass) never touches FixerAgent, Verifier, or PRAgent
at all — the routing is a real conditional graph, gated on deterministic evidence, not "call
everything every time."

A read-only Next.js dashboard (`web/`) shows run/step status and the live activity feed —
supporting evidence, not the deliverable. The deliverable is the pushed fix + PR.

## Repo layout

```
.
├── src/qa_sentinel/          # the agent pipeline
│   ├── agents/               # TestRunner, FixerAgent, Verifier, PRAgent, workflow graph
│   ├── tools/                # computer_use.py (Gemini Computer Use loop), local_fix.py
│   │                         # (clone/edit/restart/verify/push), github_pr.py
│   ├── callbacks/            # deterministic gates: feature dependencies, confidence
│   │                         # scoring, evidence capture, step verdicts
│   ├── api/                  # FastAPI: POST /api/agent/runs, the run loop
│   ├── schemas/               # pydantic models: TestCriteria, EvidenceBundle, ReviewDecision
│   └── state/                 # asyncpg session store (Prisma owns the schema/migrations)
├── demo_target_app/          # deliberately-buggy target app (plain Express + vanilla JS)
├── web/                      # read-only Next.js dashboard (Prisma schema lives here)
├── configs/test_criteria/    # test criteria as .md files (YAML frontmatter + step headings)
├── scripts/                  # one-off diagnostic probes used during development
└── docs/                     # authoritative API reference docs (Computer Use, Antigravity)
```

## Running it

**Prerequisites:** Python 3.12+, `uv`, Node 22+, PostgreSQL, a `GEMINI_API_KEY`, a
`GITHUB_TOKEN` with push access to whatever repo you're testing against.

```bash
uv sync
cp .env.example .env   # fill in GEMINI_API_KEY, GITHUB_TOKEN, DATABASE_URL
```

Start the demo target app (or point at your own):

```bash
cd demo_target_app
npm install
npm run build:css
node server.js
```

Start the QA Sentinel API (no `--reload` — it kills the shared Chromium mid-run):

```bash
uv run uvicorn src.qa_sentinel.api.app:app --host 0.0.0.0 --port 8000
```

Fire a test run, uploading a test-criteria `.md` file:

```bash
curl -X POST 'http://localhost:8000/api/agent/runs' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'port=3005' \
  -F 'repo_url=https://github.com/<owner>/<repo>.git' \
  -F 'repo_ref=main' \
  -F 'install_command=npm install' \
  -F 'local=true' \
  -F "test_criteria=@configs/test_criteria/cambria-shop-vanilla.md;type=text/markdown" \
  -F 'start_command=node server.js' \
  -F 'app_type=webapp'
```

`local=true` skips remote sandbox provisioning and tests directly against an
already-running local app (faster dev loop) — `start_command` is still required so
FixerAgent can restart the app after pushing a fix.

Watch the dashboard at `http://localhost:3000/runs` (run `npm run dev` in `web/`), or tail
the API process's logs directly — every tool call, screenshot, and evidence capture is
logged per step.

## Test criteria format

```markdown
---
app_name: cambria-shop
base_url: http://localhost:3005
---

## step_id

Natural-language instruction for Computer Use to follow.

- expected_outcome: what should happen if this step passes
- depends_on: other_step_id
- failure_class_hints: network, console
```

`depends_on` is enforced in code (`feature_gate`), not left to the LLM's judgment — a step
whose dependency hasn't passed is skipped outright.
