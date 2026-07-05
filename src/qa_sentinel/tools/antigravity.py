import base64
import time

from google import genai

from qa_sentinel.config.settings import settings

AGENT = "antigravity-preview-05-2026"


def _github_push_credential_header() -> list[dict] | None:
    if not settings.GITHUB_TOKEN:
        return None
    encoded = base64.b64encode(f"x-oauth-basic:{settings.GITHUB_TOKEN}".encode()).decode()
    return [{"Authorization": f"Basic {encoded}"}]


def dispatch_fix_to_antigravity(
    evidence: dict,
    repo_url: str,
    app_subpath: str = "",
    environment_id: str | None = None,
    previous_interaction_id: str | None = None,
) -> dict:
    """Sends an evidence bundle to the Antigravity agent to diagnose and write a fix.
    Reuses environment_id across calls so file state and repo clone persist across
    the whole multi-feature test run — this IS the "load-bearing memory" primitive.

    Args:
        evidence: An EvidenceBundle, serialized to dict.
        repo_url: The target app's git repository.
        app_subpath: Path within the repo where the target app actually lives,
            e.g. "demo_target_app" for a monorepo. Empty string means the app
            is at the repo root.
        environment_id: Reuse an existing sandbox if provided; else provision fresh.
        previous_interaction_id: Chain onto a prior interaction for multi-turn state.

    Returns:
        dict with status, environment_id (for reuse), interaction_id (for chaining),
        branch_name (the git branch the sandbox was instructed to push the fix to),
        and the agent's output_text describing the fix.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    if environment_id:
        environment = environment_id
    else:
        push_header = _github_push_credential_header()
        environment = {"type": "remote"}
        if push_header:
            environment["network"] = {
                "allowlist": [
                    {"domain": "github.com", "transform": push_header},
                    {"domain": "*"},
                ]
            }

    step_id      = evidence.get("step_id", "unknown-step")
    branch_name  = f"qa-sentinel/fix-{step_id}"
    app_dir      = f"/workspace/app/{app_subpath}".rstrip("/") if app_subpath else "/workspace/app"

    console_errors  = evidence.get("console_errors", [])
    network_failures = evidence.get("network_failures", [])
    intent          = evidence.get("model_stated_intent") or evidence.get("details") or evidence.get("error", "")

    clone_step = (
        f"First, clone the repository yourself: git clone {repo_url} /workspace/app\n\n"
        if not environment_id else
        "The repository is already cloned at /workspace/app from a prior step in "
        "this session — do not clone it again.\n\n"
    )

    prompt = (
        f"A UI test failed at step '{step_id}'.\n"
        f"Console errors: {console_errors}\n"
        f"Network failures: {network_failures}\n"
        f"Model's stated intent when the failure occurred: {intent}\n\n"
        f"{clone_step}"
        f"The target app's own code lives at {app_dir} — only edit files under "
        f"that path, do not touch other directories in this repo.\n\n"
        f"Diagnose the root cause using this evidence and write a fix under {app_dir}.\n\n"
        "Then, from /workspace/app (the repository root — git commands must run "
        "here, not inside the app subdirectory), run exactly these git steps yourself:\n"
        f"1. git checkout -b {branch_name}\n"
        "2. git add -A\n"
        f"3. git commit -m 'Fix: {step_id}'\n"
        f"4. git push origin {branch_name}\n\n"
        "Do not skip the push step — a PR will be opened against this exact branch "
        "name afterward, so the branch must exist on the remote when you finish. "
        f"End your final response with the exact line: BRANCH={branch_name}\n\n"
        "Finally, explain the fix in one paragraph."
    )

    kwargs = {
        "agent"      : AGENT,
        "input"      : prompt,
        "environment": environment,
    }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    interaction = client.interactions.create(**kwargs)

    while getattr(interaction, "status", "completed") == "in_progress":
        time.sleep(5)
        interaction = client.interactions.get(id=interaction.id)

    final_status = getattr(interaction, "status", "completed")

    return {
        "status"        : "success" if final_status in ("completed", None) else "error",
        "environment_id": interaction.environment_id,
        "interaction_id": interaction.id,
        "branch_name"   : branch_name,
        "output_text"   : interaction.output_text,
    }
