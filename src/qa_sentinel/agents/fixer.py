from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from qa_sentinel.callbacks.evidence_capture import capture_fixer_handoff, inject_fixer_args
from qa_sentinel.tools.local_fix import (
    clone_or_reset_repo,
    git_commit_and_push,
    read_file,
    restart_live_app,
    run_shell_command,
    write_file,
)

fixer_agent = LlmAgent(
    name        = "FixerAgent",
    model       = "gemini-3.5-flash",
    instruction = (
        "You are given a failed test step's evidence bundle (console errors, "
        "network failures, what the test expected vs. what happened). "
        "repo_url, app_subpath, port, and start_command are resolved for you "
        "automatically — pass any placeholder value for them, you never need "
        "to know or guess the real ones.\n\n"
        "Follow this exact loop:\n"
        "1. Call clone_or_reset_repo once to get a clean local copy of the "
        "target repo.\n"
        "2. Call read_file on the source file most likely responsible for "
        "the evidenced bug (e.g. server.js for a backend 500, based on the "
        "failing network request's path).\n"
        "3. Diagnose the root cause from the evidence and the file content, "
        "then call write_file with the corrected FULL file content. Make the "
        "smallest correct change — do not rewrite unrelated code.\n"
        "4. Call restart_live_app to restart the actual running app with "
        "your fix applied.\n"
        "5. Call run_shell_command to re-issue the exact request that "
        "originally failed (same method and path) against the restarted "
        "app, e.g. `curl -s -o /dev/null -w '%{http_code}' -X POST "
        "http://localhost:<port><path>`, and check the status is no longer "
        ">= 400.\n"
        "6. If it still fails, go back to step 2 — read the file again, "
        "diagnose why your last attempt was wrong, and try a different fix. "
        "Do this at most 3 times total.\n"
        "7. Only once you have confirmed success in step 5, call "
        "git_commit_and_push exactly once to commit and push the fix. Never "
        "call git_commit_and_push before you have a confirmed passing "
        "result from step 5 — an unverified fix must not be pushed.\n\n"
        "If you exhaust your attempts without a passing result, report "
        "clearly that the fix did not work and do not call "
        "git_commit_and_push at all."
    ),
    tools = [
        FunctionTool(func=clone_or_reset_repo),
        FunctionTool(func=read_file),
        FunctionTool(func=write_file),
        FunctionTool(func=run_shell_command),
        FunctionTool(func=restart_live_app),
        FunctionTool(func=git_commit_and_push),
    ],
    before_tool_callback = inject_fixer_args,
    after_tool_callback  = capture_fixer_handoff,
)
