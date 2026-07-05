import re
import time

from github import Auth, Github, GithubException
from github.GithubException import BadCredentialsException, UnknownObjectException

from qa_sentinel.config.settings import settings

_REPO_URL_RE     = re.compile(r"github\.com[:/](?P<full_name>[^/]+/[^/]+?)(?:\.git)?/?$")
_BRANCH_RETRIES  = 3
_BRANCH_RETRY_DELAY_SECONDS = 5


def repo_full_name_from_url(repo_url: str) -> str | None:
    match = _REPO_URL_RE.search(repo_url)
    return match.group("full_name") if match else None


def _find_existing_pr(repo, branch_name: str, base_branch: str):
    open_prs = repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch_name}", base=base_branch)
    return open_prs[0] if open_prs.totalCount > 0 else None


def branch_exists(repo, branch_name: str) -> bool:
    try:
        repo.get_branch(branch_name)
        return True
    except UnknownObjectException:
        return False


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

    try:
        repo = gh.get_repo(repo_full_name)
    except BadCredentialsException:
        return {"status": "error", "message": "GITHUB_TOKEN was rejected — check it hasn't expired or been rotated."}
    except UnknownObjectException:
        return {"status": "error", "message": f"Repo '{repo_full_name}' not found or token lacks access to it."}

    for attempt in range(_BRANCH_RETRIES):
        if branch_exists(repo, branch_name):
            break
        if attempt < _BRANCH_RETRIES - 1:
            time.sleep(_BRANCH_RETRY_DELAY_SECONDS)
    else:
        return {
            "status" : "error",
            "message": (
                f"Branch '{branch_name}' does not exist on {repo_full_name} after "
                f"{_BRANCH_RETRIES} checks — FixWriter's push may not have landed yet."
            ),
        }

    existing = _find_existing_pr(repo, branch_name, base_branch)
    if existing is not None:
        return {"status": "success", "pr_url": existing.html_url, "pr_number": existing.number, "already_existed": True}

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

    try:
        pr = repo.create_pull(
            title = pr_title,
            body  = body,
            head  = branch_name,
            base  = base_branch,
        )
    except GithubException as exc:
        return {
            "status" : "error",
            "message": f"GitHub rejected the PR creation ({exc.status}): {exc.data.get('message', exc.data)}",
        }

    return {"status": "success", "pr_url": pr.html_url, "pr_number": pr.number, "already_existed": False}
