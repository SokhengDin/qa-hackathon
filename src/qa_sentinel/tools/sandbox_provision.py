import base64
import time

from google import genai
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)

from qa_sentinel.config.settings import settings

AGENT             = "antigravity-preview-05-2026"
READY_TIMEOUT_S   = 60
POLL_INTERVAL_S   = 2
MAX_GET_RETRIES    = 5
RETRY_BACKOFF_BASE_S = 2

RETRYABLE_ERRORS = (InternalServerError, APITimeoutError, APIConnectionError)


def _get_with_retry(client, interaction_id: str):
    """client.interactions.get() with retry-and-backoff on transient server
    errors (5xx, timeouts) — a single blip from Google's backend (e.g. the
    504 'Deadline expired' seen in practice) must not be treated as fatal
    while the underlying interaction is very likely still running."""
    last_exc = None
    for attempt in range(MAX_GET_RETRIES):
        try:
            return client.interactions.get(id=interaction_id)
        except RETRYABLE_ERRORS as exc:
            last_exc = exc
            time.sleep(RETRY_BACKOFF_BASE_S * (2**attempt))
    raise last_exc


def provision_and_boot_app(
    repo_url       : str,
    port           : int,
    start_command  : str,
    repo_ref       : str = "main",
    install_command: str | None = None,
    github_pat     : str | None = None,
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
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    environment_config: dict = {
        "type"   : "remote",
        "sources": [{
            "type"  : "repository",
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
        interaction = _get_with_retry(client, interaction.id)

    if interaction.status != "completed":
        return {
            "status"        : "error",
            "environment_id": interaction.environment_id,
            "detail"        : "Boot command turn did not complete successfully.",
        }

    ready = _poll_port_ready(client, interaction.environment_id, interaction.id, port)

    return {
        "status"        : "ready" if ready else "boot_timeout",
        "environment_id": interaction.environment_id,
        "interaction_id": interaction.id,
    }


def _poll_port_ready(client, environment_id: str, previous_interaction_id: str, port: int) -> bool:
    """Polls from INSIDE the sandbox (curl against localhost) rather than from
    outside — there is no outside path to this port; see task_3.md §5."""
    deadline = time.time() + READY_TIMEOUT_S
    prev_id  = previous_interaction_id

    while time.time() < deadline:
        check = client.interactions.create(
            agent                   = AGENT,
            environment             = environment_id,
            previous_interaction_id = prev_id,
            input                   = (
                f"Run: curl -s -o /dev/null -w '%{{http_code}}' "
                f"http://localhost:{port} --max-time 2 || echo 'DOWN'"
            ),
        )
        while check.status == "in_progress":
            time.sleep(1)
            check = _get_with_retry(client, check.id)

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
    # demo_target_app uses (plain create-next-app-style npm project).
    return "npm install"


def _base64_basic_auth(pat: str) -> str:
    return base64.b64encode(f"x-oauth-basic:{pat}".encode()).decode()
