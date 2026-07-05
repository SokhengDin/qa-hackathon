from github import Auth, Github


def open_evidence_pr(
    repo_full_name: str,
    branch_name   : str,
    base_branch   : str,
    pr_title      : str,
    evidence      : dict,
    fix_summary   : str,
    github_token  : str,
) -> dict:
    """Opens a PR whose description IS the evidence bundle — console line, network
    response, confidence score — not a vague 'fixed a bug' message."""
    auth = Auth.Token(github_token)
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
