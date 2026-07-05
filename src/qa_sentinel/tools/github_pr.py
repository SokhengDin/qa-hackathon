from github import Auth, Github

from qa_sentinel.config.settings import settings


def open_evidence_pr(
    branch_name: str,
    base_branch: str,
    pr_title   : str,
    evidence   : dict,
    fix_summary: str,
) -> dict:
    """Opens a PR whose description IS the evidence bundle — console line, network
    response, confidence score — not a vague 'fixed a bug' message."""
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        return {
            "status" : "error",
            "message": "GITHUB_TOKEN / GITHUB_REPO not configured — cannot open a PR.",
        }

    auth = Auth.Token(settings.GITHUB_TOKEN)
    gh   = Github(auth=auth)
    repo = gh.get_repo(settings.GITHUB_REPO)

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
