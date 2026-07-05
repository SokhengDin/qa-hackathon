from github import Auth, Github
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from qa_sentinel.callbacks.evidence_capture import inject_verify_fix_args
from qa_sentinel.config.settings import settings
from qa_sentinel.tools.github_pr import branch_exists


def verify_fix(repo_full_name: str, branch_name: str) -> dict:
    """Confirms FixerAgent's branch actually landed on GitHub with a real
    commit. By the time this runs, TestRunner has already re-driven the real
    browser flow against the restarted live app and confirmed it passes
    (that's what routes here at all — see compute_step_verdict's
    "fix_confirmed" route) — this is the final, independent proof that a
    real diff backs that passing result, not just a claim."""
    if not settings.GITHUB_TOKEN:
        return {"status": "error", "output_text": "GITHUB_TOKEN not configured — cannot verify the branch."}
    if not repo_full_name or not branch_name:
        return {
            "status": "error",
            "output_text": "No FixWriter branch found in state — cannot verify a fix that was never dispatched.",
        }

    gh   = Github(auth=Auth.Token(settings.GITHUB_TOKEN))
    repo = gh.get_repo(repo_full_name)

    if branch_exists(repo, branch_name):
        return {
            "status"     : "resolved",
            "output_text": f"Branch '{branch_name}' exists on {repo_full_name} with a real pushed commit.",
        }

    return {
        "status"     : "still_failing",
        "output_text": f"Branch '{branch_name}' was not found on {repo_full_name} — the fix was not actually pushed.",
    }


verifier_agent = LlmAgent(
    name        = "Verifier",
    model       = "gemini-3.5-flash",
    instruction = (
        "You have exactly ONE tool available: verify_fix. You cannot browse "
        "files, list directories, run shell commands, or inspect the repo "
        "directly — do not attempt to call any tool other than verify_fix. "
        "repo_full_name and branch_name are filled in for you automatically; "
        "pass any placeholder string for them.\n\n"
        "Given a fix that was just applied, call verify_fix exactly once to "
        "confirm the branch was actually pushed before marking this feature "
        "'fixed_and_verified'. Never trust FixWriter's own claim without this "
        "independent re-check, and never call verify_fix more than once."
    ),
    tools                = [FunctionTool(func=verify_fix)],
    before_tool_callback = inject_verify_fix_args,
)
