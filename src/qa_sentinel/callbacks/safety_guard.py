ALLOWED_BASE_URL_PATTERNS = ["localhost", "127.0.0.1"]


def assert_safe_target(base_url: str) -> None:
    if not any(p in base_url for p in ALLOWED_BASE_URL_PATTERNS):
        raise ValueError(
            f"Refusing to run Computer Use against '{base_url}' — not an allowlisted "
            f"disposable target. See tasks/task_4.md §2.1."
        )


def guard_run_ui_test_step(tool, args, tool_context):
    """before_tool_callback enforced in code, not left to the LLM's judgment —
    this is the single check that prevents an agent from wandering off to a
    real website mid-run if a TestCriteria/base_url is ever malformed. Also
    blocks a second run_ui_test_step call for the same step: the model has
    been observed re-running the whole action with a different, simplified
    instruction after already getting a real result, double-counting side
    effects and confusing which run_ui_test_step result the console/network
    evidence actually belongs to."""
    if tool.name != "run_ui_test_step":
        return None

    assert_safe_target(args.get("url", ""))

    step_id = tool_context.state.get("current_step_id")
    already_ran = tool_context.state.get(f"step.{step_id}.run_ui_test_step_called")

    if already_ran:
        return {
            "status": "error",
            "message": (
                "Blocked: run_ui_test_step already ran once for this step. "
                "Use the result you already have — do not call it again with "
                "a different instruction. Proceed to list_pages/select_page/"
                "list_console_messages/list_network_requests using that "
                "existing result."
            ),
        }

    tool_context.state[f"step.{step_id}.run_ui_test_step_called"] = True
    return None
