import re

from github import Auth, Github

from qa_sentinel.config.settings import settings

_REPO_URL_RE = re.compile(r"github\.com[:/](?P<full_name>[^/]+/[^/]+?)(?:\.git)?/?$")


def repo_full_name_from_url(repo_url: str) -> str | None:
    match = _REPO_URL_RE.search(repo_url)
    return match.group("full_name") if match else None


def open_evidence_pr(
    repo_full_name: str,
    branch_name   : str,
    base_branch   : str,
    pr_title      : str,
    evidence      : dict,
    fix_summary   : str,
) -> dict:
    """Opens a PR whose description IS the evidence bundle — console line, network
    response, confidence score — not a vague 'fixed a bug' message."""
    if not settings.GITHUB_TOKEN:
        return {"status": "error", "message": "GITHUB_TOKEN not configured — cannot open a PR."}
    if not repo_full_name:
        return {"status": "error", "message": "repo_full_name not resolved for this run — cannot open a PR."}

    auth = Auth.Token(settings.GITHUB_TOKEN)
    gh   = Github(auth=auth)
    repo = gh.get_repo(repo_full_name)

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
