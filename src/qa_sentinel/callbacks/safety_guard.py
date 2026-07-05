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
    blocks a second run_ui_test_step call within the SAME TestRunner pass: the
    model has been observed re-running the whole action with a different,
    simplified instruction after already getting a real result, double-
    counting side effects and confusing which run_ui_test_step result the
    console/network evidence actually belongs to. Keyed by fix_attempts, not
    just step_id, so a legitimate loop-back re-run (after FixerAgent pushes a
    fix) still gets exactly one fresh run_ui_test_step call of its own."""
    if tool.name != "run_ui_test_step":
        return None

    assert_safe_target(args.get("url", ""))

    step_id      = tool_context.state.get("current_step_id")
    fix_attempts = tool_context.state.get(f"step.{step_id}.fix_attempts", 0)
    call_key     = f"step.{step_id}.run_ui_test_step_called.{fix_attempts}"
    already_ran  = tool_context.state.get(call_key)

    if already_ran:
        return {
            "status": "error",
            "message": (
                "Blocked: run_ui_test_step already ran once for this attempt. "
                "Use the result you already have — do not call it again with "
                "a different instruction."
            ),
        }

    tool_context.state[call_key] = True
    return None
