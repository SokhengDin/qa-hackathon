import re


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
        tool_context.state["current_step_final_url"] = tool_response.get("final_url", "")

        step_id = tool_context.state.get("current_step_id")
        tool_context.state[f"evidence.{step_id}.run_status"] = tool_response.get("status", "failed")
        tool_context.state[f"evidence.{step_id}.intent"]     = tool_response.get("final_text", "")

    return tool_response


def _find_page_id(list_pages_text: str, url: str) -> int | None:
    best_match: int | None = None
    for line in list_pages_text.splitlines():
        match = re.match(r"(\d+):\s*(.*)", line.strip())
        if match and url in match.group(2):
            best_match = int(match.group(1))
    return best_match


def resolve_target_page(tool, args, tool_context):
    """Deterministic before_tool_callback: chrome-devtools-mcp reports
    console/network data for whichever page is currently [selected] in its
    own list_pages output — which defaults to a stale blank tab, NOT the page
    Computer Use just acted on, and the LLM has repeatedly guessed the wrong
    pageId when asked to pick it itself (confirmed live). Never trust the
    LLM's own pageId choice: when it calls select_page, silently overwrite
    the argument with the ID matching the exact URL run_ui_test_step just
    reported, computed here in code. Block list_console_messages/
    list_network_requests entirely until a page has actually been selected
    this step."""
    if tool.name == "select_page":
        target_url = tool_context.state.get("current_step_final_url", "")
        list_pages_text = tool_context.state.get("last_list_pages_text", "")
        resolved_id = _find_page_id(list_pages_text, target_url) if target_url else None

        if resolved_id is not None:
            args["pageId"] = resolved_id
        tool_context.state["chrome_devtools_page_selected"] = True
        return None

    if tool.name in ("list_console_messages", "list_network_requests"):
        if not tool_context.state.get("chrome_devtools_page_selected"):
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        "Blocked: call list_pages and select_page before calling this "
                        "tool. Otherwise this returns empty results for a stale, "
                        "unselected page instead of the page under test."
                    ),
                }],
                "isError": True,
            }

    return None


def capture_list_pages(tool, args, tool_context, tool_response):
    if tool.name != "list_pages":
        return tool_response

    parts = []
    for block in tool_response.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    tool_context.state["last_list_pages_text"] = "\n".join(parts)

    return tool_response


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
