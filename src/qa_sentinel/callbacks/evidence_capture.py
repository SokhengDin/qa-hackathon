def evidence_escalation_trigger(tool, args, tool_context, tool_response):
    """Deterministic after_tool_callback on the Computer Use tool's own result —
    do not rely on the LLM deciding "should I check console logs now?"."""
    if tool.name == "run_ui_test_step" and tool_response.get("status") != "passed":
        tool_context.state["needs_chrome_devtools_check"] = True
    return tool_response


def capture_error_evidence(tool, args, tool_context, tool_response):
    """Turns raw chrome-devtools-mcp output into state, keyed by the current step."""
    step_id = tool_context.state.get("current_step_id")

    if tool.name == "list_console_messages":
        errors = [m for m in tool_response.get("messages", []) if m.get("level") == "error"]
        if errors:
            tool_context.state[f"evidence.{step_id}.console"] = errors

    if tool.name == "list_network_requests":
        failed = [r for r in tool_response.get("requests", []) if r.get("status", 200) >= 400]
        if failed:
            tool_context.state[f"evidence.{step_id}.network"] = failed

    return tool_response
