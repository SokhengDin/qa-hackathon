from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from qa_sentinel.callbacks.evidence_capture import inject_repo_full_name
from qa_sentinel.tools.github_pr import open_evidence_pr

pr_agent = LlmAgent(
    name        = "PRAgent",
    model       = "gemini-3.5-flash",
    instruction = (
        "You have exactly ONE tool available: open_evidence_pr. You cannot "
        "browse files, list directories, or run shell commands — do not "
        "attempt to call any tool other than open_evidence_pr. The target "
        "repo, credentials, and head branch are all resolved for you "
        "automatically from the FixWriter step that ran before you; you "
        "never need to supply a repo name, token, or branch_name — pass any "
        "placeholder string for branch_name.\n\n"
        "Only open a PR for features marked 'fixed_and_verified'. Call "
        "open_evidence_pr exactly once, passing: base_branch ('main'), "
        "pr_title (a concise one-line summary), evidence (the full evidence "
        "bundle for this step as a dict — console errors, network failures, "
        "model_stated_intent, confidence), and fix_summary (FixWriter's "
        "explanation of the fix). Use the full evidence bundle as the PR "
        "body — never write a vague description. One PR per feature fixed "
        "in this run, not one giant combined PR."
    ),
    tools                = [FunctionTool(func=open_evidence_pr)],
    before_tool_callback = inject_repo_full_name,
)
