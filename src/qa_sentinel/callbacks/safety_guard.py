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
    real website mid-run if a TestCriteria/base_url is ever malformed."""
    if tool.name == "run_ui_test_step":
        assert_safe_target(args.get("url", ""))
    return None
