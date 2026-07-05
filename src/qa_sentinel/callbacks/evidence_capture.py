def evidence_escalation_trigger(tool, args, tool_context, tool_response):
    """Deterministic after_tool_callback on the Computer Use tool's own result —
    do not rely on the LLM deciding "should I check console logs now?". Always
    escalate, even when run_ui_test_step self-reports "passed": that status is
    itself a visual judgment call by Computer Use, and a silent server-side
    failure (e.g. a 403 the page never displays) looks identical to success
    on screen. chrome-devtools-mcp is cheap to call and is the only path that
    can catch what a screenshot cannot."""
    if tool.name == "run_ui_test_step":
        tool_context.state["needs_chrome_devtools_check"] = True
        tool_context.state["chrome_devtools_page_selected"] = False

        step_id = tool_context.state.get("current_step_id")
        tool_context.state[f"evidence.{step_id}.run_status"] = tool_response.get("status", "failed")
        tool_context.state[f"evidence.{step_id}.intent"]     = tool_response.get("final_text", "")

    return tool_response


def require_page_selected_first(tool, args, tool_context):
    """Deterministic before_tool_callback: chrome-devtools-mcp reports
    console/network data for whichever page is currently [selected] in its
    own list_pages output — which defaults to a stale blank tab, NOT the page
    Computer Use just acted on. Calling list_console_messages/
    list_network_requests before select_page silently returns empty results
    even when real errors exist (confirmed live via scripts/
    probe_chrome_devtools_mcp.py). Block those two calls until select_page
    has actually succeeded for this step, rather than trusting the LLM to
    remember the required ordering every time."""
    if tool.name == "select_page":
        tool_context.state["chrome_devtools_page_selected"] = True
        return None

    if tool.name in ("list_console_messages", "list_network_requests"):
        if not tool_context.state.get("chrome_devtools_page_selected"):
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        "Blocked: call list_pages and select_page (matching the URL "
                        "run_ui_test_step just acted on) before calling this tool. "
                        "Otherwise this returns empty results for a stale, unselected "
                        "page instead of the page under test."
                    ),
                }],
                "isError": True,
            }

    return None


def _extract_text(tool_response: dict) -> str:
    """chrome-devtools-mcp's MCP tools return {"content": [{"type": "text",
    "text": "..."}], "isError": bool} — a markdown text blob, not a
    structured {"messages": [...]} / {"requests": [...]} shape."""
    parts = []
    for block in tool_response.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def capture_error_evidence(tool, args, tool_context, tool_response):
    """Turns raw chrome-devtools-mcp output into state, keyed by the current step."""
    step_id = tool_context.state.get("current_step_id")
    text    = _extract_text(tool_response)

    if tool.name == "list_console_messages":
        error_lines = [line for line in text.splitlines() if "error" in line.lower()]
        if error_lines:
            tool_context.state[f"evidence.{step_id}.console"] = error_lines

    if tool.name == "list_network_requests":
        failure_lines = [
            line for line in text.splitlines()
            if any(f" {code} " in f" {line} " for code in ("400", "401", "403", "404", "500", "502", "503"))
        ]
        if failure_lines:
            tool_context.state[f"evidence.{step_id}.network"] = failure_lines

    if tool.name == "take_snapshot" and text:
        tool_context.state[f"evidence.{step_id}.snapshot"] = text

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
