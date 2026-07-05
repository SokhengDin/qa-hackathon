def feature_gate(callback_context) -> dict | None:
    """Literal implementation of 'feature 2 cannot begin until feature 1 is resolved.'
    Enforced in code, not left to the LLM's judgment — the LLM decides *what* to
    test; this decides *whether it's allowed to test it yet*."""
    step = callback_context.state["current_step"]
    for dep_id in step.depends_on:
        dep_status = callback_context.state.get(f"step.{dep_id}.status")
        if dep_status not in ("passed", "fixed_and_verified"):
            return {"skip": True, "reason": f"blocked on {dep_id}={dep_status}"}
    return None
