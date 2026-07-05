# task_3.md — Sandbox Provisioning: From Repo URL to a Live App Computer Use Can Test

Companion to `CLAUDE.md` and `task_2.md`. This task replaces the earlier draft of
`task_3.md` (which specced a demo target app — that app now lives in its own repo, with its
own `CLAUDE.md`, and is out of scope here).

This task answers one question precisely: **given a `repo_url` in the `/api/agent/execute`
payload (`task_2.md` §2), how does that become a running app, on a real port, that Computer
Use can point a browser at — with zero cross-machine networking to configure?**

The answer is: everything happens inside one Antigravity sandbox. The sandbox clones the
repo, boots the app in the background, and also hosts Computer Use's own Playwright/Chromium
process — so "the app" and "the thing testing the app" are the same machine, reachable at
`localhost`. This is Option B from `CLAUDE.md` §15, now made concrete and mandatory rather
than a fallback choice.

## 1. Why this replaces the Option A/B decision, not just picks one

`CLAUDE.md` §15 framed Option A (local Playwright, local Chrome) vs. Option B (both inside
the Antigravity sandbox) as an open question to spike on Day 1. Given the repo is now
uploaded as part of the execute payload rather than being a fixed local app you already have
running, **Option A stops being viable at all** — there is no "local Chrome" that can reach
an app that only exists as a git URL until something clones and boots it. The sandbox has to
do the cloning and booting regardless of where Computer Use runs, and once the sandbox is
already doing that, running Computer Use there too avoids a real networking problem (see §5)
for zero extra cost. Treat §15's "Option A fallback" as no longer applicable to this
codebase; delete that branch of the decision rather than spiking it.

## 2. What `/api/agent/execute`'s payload actually needs, revised from `task_2.md`

`task_2.md` §2 already has `repo_url` on the `AppTarget` type. This task adds the fields the
sandbox provisioning step actually needs to act on that URL correctly:

```typescript
// web/src/lib/types.ts — extending the webapp variant of AppTarget

type WebAppTarget = {
  app_type:                 "webapp";
  repo_url:                 string;    // e.g. "https://github.com/your-org/demo-target-app"
  repo_ref?:                string;    // branch/tag/commit; default "main"
  install_command?:         string;    // default: auto-detected from lockfile presence
  start_command:            string;    // e.g. "npm run dev -- -p 3001" — REQUIRED, no safe default
  port:                     number;    // e.g. 3001 — REQUIRED, must match start_command
  computer_use_environment: "browser";
  private_repo_auth?: {
    // only needed for private repos — see §4's credential-injection note
    github_pat_env_var: string;        // name of an env var on the execute server
                                        // holding the PAT; NEVER the PAT itself in the payload
  };
};
```

`start_command` and `port` are deliberately **required, not inferred** — auto-detecting "how
does this particular repo start itself" across arbitrary Next.js/Vite/whatever configs is a
real source of the exact hangs described in community reports of agents guessing wrong
commands and getting stuck. Requiring the caller to state both explicitly removes an entire
class of provisioning failure for a small cost (one extra field in the payload).

## 3. Provisioning sequence — what happens when a run moves from `queued` to `running`

This is the piece that runs inside `src/qa_sentinel/agents/test_runner.py` (or a small setup
step immediately before it) once the Python pipeline polls a `queued` `Run` row (per
`task_2.md` §2's poll-based handoff) and picks it up.

```python
# src/qa_sentinel/tools/sandbox_provision.py

import re
import time

from google import genai


AGENT           = "antigravity-preview-05-2026"
READY_TIMEOUT_S = 60
POLL_INTERVAL_S = 2


def provision_and_boot_app(
    repo_url:        str,
    port:            int,
    start_command:   str,
    repo_ref:        str = "main",
    install_command: str | None = None,
    github_pat:      str | None = None,
) -> dict:
    """Clones the target app repo into a fresh Antigravity sandbox, installs
    dependencies, and boots the app as a backgrounded process, then polls until
    the port actually responds before returning. This environment_id is then
    reused for the entire test run — Computer Use, FixWriter, and Verifier all
    operate inside this same sandbox.

    Returns:
        dict with status, environment_id (reuse this for the whole run),
        and the boot log tail for debugging if readiness times out.
    """
    client = genai.Client()

    environment_config: dict = {
        "type":    "remote",
        "sources": [{
            "type":   "repository",
            "source": repo_url,
            "target": "/workspace/app",
        }],
    }

    if github_pat:
        # Credential injection per docs/environment.md's "Private sources" pattern —
        # the token is injected by the egress proxy via a header transform, and is
        # NEVER placed in an env var visible inside the sandbox itself.
        token_b64 = _base64_basic_auth(github_pat)
        environment_config["network"] = {
            "allowlist": [
                {"domain": "github.com", "transform": {"Authorization": f"Basic {token_b64}"}},
                {"domain": "*"},
            ]
        }

    install_cmd = install_command or _infer_install_command()
    boot_prompt = (
        f"In /workspace/app, checkout ref '{repo_ref}' if not already on it. "
        f"Run: {install_cmd}\n"
        f"Then start the app with this EXACT command, backgrounded and detached "
        f"so it keeps running after this turn ends — do not run it in the "
        f"foreground, it must not block:\n"
        f"nohup {start_command} > /workspace/app/dev.log 2>&1 &\n"
        f"After launching, report back that you've started it; do not wait for "
        f"it to print 'ready' yourself — the caller will poll for readiness."
    )

    interaction = client.interactions.create(
        agent       = AGENT,
        input       = boot_prompt,
        environment = environment_config,
        background  = True,
    )

    while interaction.status == "in_progress":
        time.sleep(3)
        interaction = client.interactions.get(id=interaction.id)

    if interaction.status != "completed":
        return {"status": "error", "environment_id": interaction.environment_id,
                "detail": "Boot command turn did not complete successfully."}

    ready = _poll_port_ready(client, interaction.environment_id, interaction.id, port)

    return {
        "status":         "ready" if ready else "boot_timeout",
        "environment_id": interaction.environment_id,
        "interaction_id": interaction.id,
    }


def _poll_port_ready(client, environment_id: str, previous_interaction_id: str, port: int) -> bool:
    """Polls from INSIDE the sandbox (curl against localhost) rather than from
    outside — there is no outside path to this port; see §5."""
    deadline = time.time() + READY_TIMEOUT_S
    prev_id  = previous_interaction_id

    while time.time() < deadline:
        check = client.interactions.create(
            agent                   = AGENT,
            environment              = environment_id,
            previous_interaction_id  = prev_id,
            input                    = (
                f"Run: curl -s -o /dev/null -w '%{{http_code}}' "
                f"http://localhost:{port} --max-time 2 || echo 'DOWN'"
            ),
        )
        while check.status == "in_progress":
            time.sleep(1)
            check = client.interactions.get(id=check.id)

        prev_id = check.id
        if "DOWN" not in check.output_text and "000" not in check.output_text:
            return True

        time.sleep(POLL_INTERVAL_S)

    return False


def _infer_install_command() -> str:
    # A real implementation should check for lockfile presence
    # (package-lock.json -> npm ci, pnpm-lock.yaml -> pnpm install --frozen-lockfile,
    # yarn.lock -> yarn install --frozen-lockfile) via a preceding `ls` turn, rather
    # than hardcoding npm. Left as npm for the hackathon default since that's what
    # the demo_target_app repo uses (per its own CLAUDE.md, plain create-next-app
    # defaults).
    return "npm install"


def _base64_basic_auth(pat: str) -> str:
    import base64
    return base64.b64encode(f"x-oauth-basic:{pat}".encode()).decode()
```

## 4. Credential handling — do not put the PAT in the request payload, ever

Note `WebAppTarget.private_repo_auth` in §2 carries an **env var name**, not the token
itself. The execute endpoint (`web/src/app/api/agent/execute/route.ts`) reads the actual PAT
server-side from its own environment (`process.env[github_pat_env_var]`), and only that
resolved value ever reaches `provision_and_boot_app`. This matters because the `Run` row
gets written to Postgres and shown on the dashboard (`task_1.md`) — a token embedded in the
stored payload would leak into the UI and into `RunLog` entries. Per `docs/environment.md`'s
own pattern, the token only ever exists as a header value injected by Google's egress proxy,
never as plaintext inside the sandbox or inside your own stored rows.

For the hackathon: the `demo_target_app` repo should just be **public**, avoiding this
entire section in practice. Keep `private_repo_auth` in the type for completeness/honesty
about what the architecture supports, but don't spend build time exercising this path if the
demo repo is public — confirm it's public and skip straight past §4's complexity.

## 5. Why polling from inside the sandbox, not from your `web`/`app` container

This is the concrete version of the networking question raised when this task was scoped:
**inbound port exposure from an Antigravity sandbox to the outside world is not a documented
capability** — `docs/environment.md` covers outbound network allowlisting in detail (for the
sandbox to reach GitHub, GCS, arbitrary APIs) but says nothing about exposing a port
*inward*, from the sandbox to your own infrastructure. Treat this as **not supported** unless
you find explicit documentation saying otherwise before building against it.

The practical consequence: your `app`/`web` containers (running on your own
docker-compose network) **cannot** curl into the sandbox to check readiness, and Computer
Use's Playwright **cannot** run outside the sandbox and reach `localhost:3001` inside it —
there is no "localhost" shared between two different machines. This is precisely why
Computer Use's browser must also run inside the same sandbox (§1) — at that point
`localhost:{port}` is genuinely the same machine, and the readiness poll in §3 works by
asking the sandbox to curl its own loopback interface and reporting the result back through
the Interactions API's normal turn-based response, not through any inbound network path.

## 6. Where Computer Use's Playwright process actually runs, concretely

Since `docs/environment.md` confirms the sandbox is Ubuntu with Node.js 22 pre-installed and
full `code_execution`, installing Chromium + Playwright there is a normal `apt`/`npm` step,
not a novel one:

```python
# extend the boot_prompt in provision_and_boot_app, or issue as a follow-up
# turn on the same environment_id, BEFORE running the Computer Use test loop:

setup_prompt = (
    "Install Google Chrome or Chromium for headless browser automation "
    "(apt-get install -y chromium-browser, or the appropriate package for "
    "this distro) if not already present. Confirm with `chromium --version` "
    "or equivalent."
)
```

The `run_ui_test_step` function from `task_2.md` §1 then needs its Playwright launch call
adjusted to run *as a command inside this environment* rather than as a local subprocess on
whatever machine `src/qa_sentinel` itself is running on. Concretely, this means
`run_ui_test_step`'s actual browser automation code should be **sent to the sandbox as a
Python/Node script via `code_execution`**, not executed by the ADK process's own local
Playwright install — the ADK process orchestrates *which* script runs and *when*, but the
script's `sync_playwright()` call executes on the sandbox's Ubuntu box, against the app also
running there.

This is the one piece of `task_2.md` §1's `run_ui_test_step` that needs a shape change given
this task's sandbox-first architecture — flag this explicitly rather than silently leaving
the two documents inconsistent: **`task_2.md` §1's code, as written, assumes a local
Playwright process. Wrap it as a script string, send it via the sandbox's `code_execution`
tool (or as an Antigravity turn instructing it to run the equivalent Python inline), and
retrieve the resulting screenshot/actions_taken via the sandbox's file read capability or
inline in the turn's output — rather than calling `sync_playwright()` directly from
`src/qa_sentinel`'s own process.**

## 7. Environment reuse across the whole run — tying back to `CLAUDE.md` §3/§7

Once `provision_and_boot_app` returns a `ready` status and an `environment_id`, that ID is:

- Written onto the `Run` row (`task_2.md` §4's `Run.environmentId` field) immediately, so the
  dashboard can show which environment backs this run.
- Passed to every subsequent Computer Use test step for this run (all features, in dependency
  order) — the app boots once, stays running across the whole multi-feature test, exactly
  matching the "feature 2's session cannot start until feature 1's environment confirms
  pass/fail" framing in `CLAUDE.md` §2, since it's the literal same running process being
  tested throughout.
- Passed to `FixWriter` (`CLAUDE.md` §11) unchanged — the fix gets written into the same
  `/workspace/app` checkout that's currently running, meaning `Verifier` (`CLAUDE.md` §12)
  can trigger a restart of the same backgrounded process and re-check the same port, rather
  than re-provisioning anything.

## 8. Build order for this task

1. Confirm the `demo_target_app` repo (its own repo, own `CLAUDE.md`) is public — skip §4
   entirely if so.
2. Write `src/qa_sentinel/tools/sandbox_provision.py` per §3.
3. Spike it standalone first: call `provision_and_boot_app` directly against the real
   `demo_target_app` repo URL, confirm it returns `status: "ready"` within a reasonable time,
   and manually curl the reported environment via a follow-up Antigravity turn to sanity
   check the app is actually serving real Cambria pages (not just an empty 200).
4. Install Chromium inside the same environment per §6, confirm `chromium --version` works
   as a follow-up turn on the same `environment_id`.
5. Adjust `run_ui_test_step` (`task_2.md` §1) per §6's note — move its Playwright execution
   into a sandbox-dispatched script rather than a local process call. This is the one real
   refactor this task requires against already-written code.
6. Wire `Run.environmentId` population into the execute endpoint flow, per §7.
7. Only once steps 1–6 work standalone: run the full pipeline end to end against a real
   `queued` run and confirm TestRunner successfully tests a Cambria feature inside the
   provisioned sandbox.

Do not attempt step 7 before 1–6 are independently confirmed — provisioning failures are
much easier to diagnose in isolation (a boot log, a readiness timeout, a missing Chromium
package) than buried inside a full ADK `Workflow` run where the failure could be anywhere.