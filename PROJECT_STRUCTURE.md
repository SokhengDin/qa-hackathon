# Project Structure

    QA-AGENT/                          # repo root
    ├── CLAUDE.md                         # <- build guideline for Claude Code (main deliverable)
    ├── README.md                         # human-facing readme, written last
    ├── pyproject.toml                    # uv-managed, single source of truth for deps
    ├── uv.lock                           # committed, reproducible installs
    ├── .python-version                   # pins 3.12
    ├── .env.example                      # documents required secrets, never commit real .env
    ├── .gitignore
    ├── docker-compose.yml                # orchestrates: app, postgres, chrome, otel-collector
    ├── docker/
    │   ├── app/
    │   │   └── Dockerfile                # uv-based, multi-stage
    │   └── chrome/
    │       └── Dockerfile                # headless Chrome + chrome-devtools-mcp preinstalled
    │
    ├── src/
    │   └── qa_sentinel/
    │       ├── __init__.py
    │       ├── main.py                   # entrypoint: adk web / adk run wiring
    │       │
    │       ├── agents/                   # ADK LlmAgent + Workflow definitions
    │       │   ├── __init__.py
    │       │   ├── test_runner.py        # drives Computer Use, escalates to chrome-devtools-mcp
    │       │   ├── fix_writer.py         # delegates to Antigravity agent (Interactions API)
    │       │   ├── verifier.py           # re-runs chrome-devtools-mcp to confirm fix
    │       │   ├── pr_agent.py           # commits + opens GitHub PR with evidence bundle
    │       │   └── workflow.py           # root Workflow graph, wiring + gating
    │       │
    │       ├── tools/                    # custom FunctionTools (non-ADK-native integrations)
    │       │   ├── __init__.py
    │       │   ├── computer_use.py       # wraps the raw Gemini computer_use agent loop
    │       │   ├── antigravity.py        # wraps Interactions API calls to Antigravity agent
    │       │   ├── github_pr.py          # commit + PR creation via GitHub API
    │       │   └── chrome_devtools_mcp.py # McpToolset config + tool_filter setup
    │       │
    │       ├── callbacks/                # ADK lifecycle hooks — the observability layer
    │       │   ├── __init__.py
    │       │   ├── evidence_capture.py   # after_tool_callback: console/network -> state
    │       │   ├── feature_gate.py       # before_agent_callback: blocks feature N+1
    │       │   └── confidence_scoring.py # scores evidence completeness per bug
    │       │
    │       ├── schemas/                  # pydantic models — the shared data contracts
    │       │   ├── __init__.py
    │       │   ├── test_criteria.py      # feature graph + pass/fail criteria model
    │       │   ├── evidence_bundle.py    # screenshot + console + network + intent
    │       │   └── review_decision.py    # human confirm/dismiss feedback model
    │       │
    │       ├── state/                    # session state persistence helpers
    │       │   ├── __init__.py
    │       │   └── session_store.py      # ADK session state <-> Postgres sync
    │       │
    │       └── config/
    │           ├── __init__.py
    │           └── settings.py           # pydantic-settings, reads .env
    │
    ├── configs/
    │   ├── test_criteria/
    │   │   └── example_app.yaml          # sample feature-dependency test spec
    │   └── otel/
    │       └── collector-config.yaml
    │
    ├── tests/
    │   ├── unit/
    │   │   ├── test_evidence_bundle.py
    │   │   ├── test_feature_gate.py
    │   │   └── test_confidence_scoring.py
    │   └── integration/
    │       └── test_workflow_e2e.py      # runs against a small target demo app
    │
    ├── demo_target_app/                  # the intentionally-buggy app QA-AGENT tests
    │   └── (whatever your demo app is — separate repo is also fine, just mount it)
    │
    └── scripts/
        ├── spike_sandbox_headless.py     # Day-1 spike: confirm headless Chrome in Antigravity env
        └── run_demo.sh                   # one-command demo runner for judging

## Notes on choices

- **uv** manages `pyproject.toml` + `uv.lock`; no `requirements.txt`, no `pip freeze`. Install with
  `uv sync`, run with `uv run adk web src/qa_sentinel`.
- **docker-compose** services: `app` (the ADK workflow), `postgres` (evidence bundle + session
  state persistence), `chrome` (headless Chrome with remote debugging exposed, running
  chrome-devtools-mcp), `otel-collector` (optional, for the live trace-timeline demo visual).
- `tools/` holds only the **non-ADK-native** integrations (Computer Use, Antigravity, GitHub).
  `chrome_devtools_mcp.py` is a thin config file, not a wrapper — the actual tool objects come
  from ADK's `McpToolset`, which auto-discovers them from the MCP server.
- `demo_target_app/` should be a deliberately-buggy small app (signup flow, checkout flow,
  whatever is easiest to break in interesting ways) — build or pick this FIRST, before the agent
  pipeline, since everything else is tested against it.