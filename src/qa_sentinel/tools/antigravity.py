import time

from google import genai

from qa_sentinel.config.settings import settings

AGENT = "antigravity-preview-05-2026"


def dispatch_fix_to_antigravity(
    evidence: dict,
    repo_url: str,
    app_subpath: str = "demo_target_app",
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

    environment = environment_id or {
        "type"   : "remote",
        "sources": [{
            "type"  : "repository",
            "source": repo_url,
            "target": "/workspace/app",
        }],
    }

    step_id      = evidence.get("step_id", "unknown-step")
    branch_name  = f"qa-sentinel/fix-{step_id}"
    app_dir      = f"/workspace/app/{app_subpath}".rstrip("/") if app_subpath else "/workspace/app"

    console_errors  = evidence.get("console_errors", [])
    network_failures = evidence.get("network_failures", [])
    intent          = evidence.get("model_stated_intent") or evidence.get("details") or evidence.get("error", "")

    prompt = (
        f"A UI test failed at step '{step_id}'.\n"
        f"Console errors: {console_errors}\n"
        f"Network failures: {network_failures}\n"
        f"Model's stated intent when the failure occurred: {intent}\n\n"
        f"The repository is cloned at /workspace/app. The target app's own code "
        f"lives at {app_dir} — only edit files under that path, do not touch "
        f"other directories in this repo.\n\n"
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
        "background" : True,
    }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    interaction = client.interactions.create(**kwargs)

    while interaction.status == "in_progress":
        time.sleep(5)
        interaction = client.interactions.get(id=interaction.id)

    return {
        "status"        : "success" if interaction.status == "completed" else "error",
        "environment_id": interaction.environment_id,
        "interaction_id": interaction.id,
        "branch_name"   : branch_name,
        "output_text"   : interaction.output_text,
    }
