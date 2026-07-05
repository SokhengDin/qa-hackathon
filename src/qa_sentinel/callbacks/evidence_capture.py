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


def capture_antigravity_handoff(tool, args, tool_context, tool_response):
    if tool.name != "dispatch_fix_to_antigravity":
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


def inject_repo_full_name(tool, args, tool_context):
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

    args["repo_full_name"] = repo_full_name
    args["branch_name"]    = branch_name
    return None


def inject_antigravity_ids(tool, args, tool_context):
    if tool.name != "verify_fix":
        return None

    environment_id = tool_context.state.get("antigravity.environment_id")
    interaction_id = tool_context.state.get("antigravity.previous_interaction_id")

    if not environment_id or not interaction_id:
        return {
            "status"     : "error",
            "output_text": (
                "No FixWriter environment/interaction found in state — cannot verify "
                "a fix that was never dispatched to Antigravity. Skipping verification."
            ),
        }

    args["environment_id"] = environment_id
    args["previous_interaction_id"] = interaction_id

    return None
