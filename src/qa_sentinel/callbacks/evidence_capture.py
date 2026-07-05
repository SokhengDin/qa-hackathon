def evidence_escalation_trigger(tool, args, tool_context, tool_response):
    """Deterministic after_tool_callback on the Computer Use tool's own result —
    do not rely on the LLM deciding "should I check console logs now?". Always
    escalate, even when run_ui_test_step self-reports "passed": that status is
    itself a visual judgment call by Computer Use, and a silent server-side
    failure (e.g. a 403 the page never displays) looks identical to success
    on screen.

    run_ui_test_step's own Playwright session listens for console errors and
    failed (>=400) network responses directly while Computer Use drives the
    page (see _attach_evidence_listeners in tools/computer_use.py) and
    returns them in its result dict — this is captured here into state,
    keyed by step_id, with no separate MCP round-trip required. chrome-
    devtools-mcp round-tripping was dropped after live testing confirmed it
    silently reports data for whichever page happens to be selected in its
    own internal state, not necessarily the page Computer Use just acted on,
    and the ordering/selection dance added real failure modes with no
    corresponding reliability gain over listening directly on the same
    Playwright page object."""
    if tool.name != "run_ui_test_step":
        return tool_response

    step_id = tool_context.state.get("current_step_id")
    tool_context.state[f"evidence.{step_id}.run_status"]  = tool_response.get("status", "failed")
    tool_context.state[f"evidence.{step_id}.intent"]      = tool_response.get("final_text", "")
    tool_context.state[f"evidence.{step_id}.console"]     = tool_response.get("console_errors", [])
    tool_context.state[f"evidence.{step_id}.network"]     = tool_response.get("network_failures", [])

    return tool_response


FIX_DISPATCH_TOOL_NAMES = ("dispatch_fix_to_antigravity", "dispatch_fix_locally")


def capture_antigravity_handoff(tool, args, tool_context, tool_response):
    if tool.name not in FIX_DISPATCH_TOOL_NAMES:
        return tool_response

    environment_id = tool_response.get("environment_id")
    interaction_id = tool_response.get("interaction_id")
    branch_name    = tool_response.get("branch_name")

    if environment_id:
        tool_context.state["antigravity.environment_id"] = environment_id
    if interaction_id:
        tool_context.state["antigravity.previous_interaction_id"] = interaction_id
    if branch_name:
        tool_context.state["antigravity.branch_name"] = branch_name

    return tool_response


def inject_repo_url_for_fix(tool, args, tool_context):
    """The fix-dispatch tool's repo_url must be the real target repo for this
    run, not something the LLM guesses — it was observed passing '/workspace'
    (a local sandbox path, not a git URL) instead of the actual repo_url from
    the run's own payload. Also injects the existing environment_id/
    previous_interaction_id from state when dispatching to Antigravity and a
    prior call in this run already established a sandbox, so file state
    persists across steps as intended — the LLM no longer needs to (and
    cannot correctly) supply any of these itself."""
    if tool.name not in FIX_DISPATCH_TOOL_NAMES:
        return None

    step_id = tool_context.state.get("current_step_id")
    already_dispatched = tool_context.state.get(f"step.{step_id}.fix_dispatched")
    if already_dispatched:
        return {
            "status" : "error",
            "message": (
                "A fix was already dispatched for this step — do not call this "
                "again with a different step_id or framing. Use the result you "
                "already have."
            ),
        }
    tool_context.state[f"step.{step_id}.fix_dispatched"] = True

    repo_url = tool_context.state.get("repo_url")
    if not repo_url:
        return {
            "status" : "error",
            "message": "repo_url not found in state — cannot dispatch a fix without a resolved target repo.",
        }

    args["repo_url"] = repo_url
    args["app_subpath"] = tool_context.state.get("app_subpath", "")

    if tool.name == "dispatch_fix_to_antigravity":
        environment_id = tool_context.state.get("antigravity.environment_id")
        interaction_id = tool_context.state.get("antigravity.previous_interaction_id")
        if environment_id:
            args["environment_id"] = environment_id
        if interaction_id:
            args["previous_interaction_id"] = interaction_id

    return None


def inject_repo_full_name(tool, args, tool_context):
    """Also injects the real evidence bundle from state instead of trusting
    PRAgent to reconstruct it — it was observed inventing its own shape
    (console_errors as a string, network_response instead of
    network_failures, confidence_score instead of confidence), which crashed
    open_evidence_pr's direct dict indexing. Same fix pattern as
    inject_repo_url_for_fix for dispatch_fix_locally."""
    if tool.name != "open_evidence_pr":
        return None

    repo_full_name = tool_context.state.get("repo_full_name")
    branch_name    = tool_context.state.get("antigravity.branch_name")

    if not repo_full_name:
        return {
            "status" : "error",
            "message": "repo_full_name not found in state — cannot open a PR without a resolved target repo.",
        }
    if not branch_name:
        return {
            "status" : "error",
            "message": "No branch was pushed by FixWriter for this step — cannot open a PR without a real head branch.",
        }

    step_id = tool_context.state.get("current_step_id")
    args["repo_full_name"] = repo_full_name
    args["branch_name"]    = branch_name
    args["evidence"] = {
        "console_errors"     : tool_context.state.get(f"evidence.{step_id}.console", []),
        "network_failures"   : tool_context.state.get(f"evidence.{step_id}.network", []),
        "model_stated_intent": tool_context.state.get(f"evidence.{step_id}.intent", ""),
        "confidence"         : tool_context.state.get(f"step.{step_id}.confidence", 0.0),
    }
    return None


FIXER_TOOL_NAMES = (
    "clone_or_reset_repo",
    "read_file",
    "write_file",
    "run_shell_command",
    "git_commit_and_push",
    "restart_live_app",
)


def inject_fixer_args(tool, args, tool_context):
    """FixerAgent's tools all need the real repo_url/port/start_command for
    this run — never something the LLM guesses. git_commit_and_push also
    gets the real step_id (for its branch name) and is blocked entirely if a
    fix was already dispatched for this step, so FixerAgent cannot push a
    second, possibly-conflicting fix after already succeeding once."""
    if tool.name not in FIXER_TOOL_NAMES:
        return None

    repo_url = tool_context.state.get("repo_url")
    if not repo_url:
        return {
            "status" : "error",
            "message": "repo_url not found in state — cannot operate without a resolved target repo.",
        }
    args["repo_url"] = repo_url

    if tool.name in ("clone_or_reset_repo", "read_file", "write_file", "run_shell_command"):
        return None

    if tool.name == "restart_live_app":
        args["port"] = tool_context.state.get("port")
        args["start_command"] = tool_context.state.get("start_command")
        return None

    if tool.name == "git_commit_and_push":
        step_id = tool_context.state.get("current_step_id")
        already_dispatched = tool_context.state.get(f"step.{step_id}.fix_dispatched")
        if already_dispatched:
            return {
                "status" : "error",
                "message": "A fix was already committed and pushed for this step — do not push again.",
            }
        tool_context.state[f"step.{step_id}.fix_dispatched"] = True
        args["step_id"] = step_id

    return None


def capture_fixer_handoff(tool, args, tool_context, tool_response):
    """Captures the pushed branch_name from git_commit_and_push, and
    increments this step's fix_attempts counter so compute_step_verdict knows
    a loop-back re-test is underway (and can cap retries)."""
    if tool.name != "git_commit_and_push":
        return tool_response

    step_id = tool_context.state.get("current_step_id")
    attempts = tool_context.state.get(f"step.{step_id}.fix_attempts", 0)
    tool_context.state[f"step.{step_id}.fix_attempts"] = attempts + 1

    branch_name = tool_response.get("branch_name")
    if branch_name:
        tool_context.state["antigravity.branch_name"] = branch_name

    return tool_response


def inject_verify_fix_args(tool, args, tool_context):
    if tool.name != "verify_fix":
        return None

    repo_full_name = tool_context.state.get("repo_full_name")
    branch_name    = tool_context.state.get("antigravity.branch_name")

    if not repo_full_name or not branch_name:
        return {
            "status"     : "error",
            "output_text": (
                "No FixWriter branch found in state — cannot verify a fix that "
                "was never dispatched."
            ),
        }

    args["repo_full_name"] = repo_full_name
    args["branch_name"] = branch_name

    return None
