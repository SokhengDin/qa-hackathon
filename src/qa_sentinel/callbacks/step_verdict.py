from qa_sentinel.callbacks.confidence_scoring import score_confidence

MAX_FIX_ATTEMPTS = 2


def compute_step_verdict(callback_context) -> None:
    step_id = callback_context.state.get("current_step_id")
    if not step_id:
        return

    console_errors   = callback_context.state.get(f"evidence.{step_id}.console", [])
    network_failures = callback_context.state.get(f"evidence.{step_id}.network", [])
    run_status       = callback_context.state.get(f"evidence.{step_id}.run_status", "failed")
    intent           = callback_context.state.get(f"evidence.{step_id}.intent", "")
    fix_attempts     = callback_context.state.get(f"step.{step_id}.fix_attempts", 0)

    has_console      = len(console_errors) > 0
    has_network      = len(network_failures) > 0
    intent_explains  = bool(intent) and run_status != "passed"

    confidence = score_confidence(has_console, has_network, intent_explains)
    is_clean   = run_status == "passed" and not has_console and not has_network

    if is_clean:
        # A pass after at least one fix attempt is the loop-back succeeding —
        # mark it fixed_and_verified so Verifier/PRAgent know a real fix
        # landed, not just an originally-passing step.
        status = "fixed_and_verified" if fix_attempts > 0 else "passed"
        route  = "fix_confirmed" if fix_attempts > 0 else None
    elif fix_attempts >= MAX_FIX_ATTEMPTS:
        status = "failed"
        route  = "needs_human_review"
    else:
        status = "failed"
        route  = "needs_fix" if confidence >= 0.4 else "needs_human_review"

    callback_context.state[f"step.{step_id}.status"]     = status
    callback_context.state[f"step.{step_id}.confidence"] = confidence

    if route is not None:
        callback_context.actions.route = route
