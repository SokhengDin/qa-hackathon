from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from qa_sentinel.tools.github_pr import open_evidence_pr

pr_agent = LlmAgent(
    name        = "PRAgent",
    model       = "gemini-3.5-flash",
    instruction = (
        "Only open a PR for features marked 'fixed_and_verified'. Use the full "
        "evidence bundle as the PR body — never write a vague description. "
        "One PR per feature fixed in this run, not one giant combined PR."
    ),
    tools = [FunctionTool(func=open_evidence_pr)],
)
