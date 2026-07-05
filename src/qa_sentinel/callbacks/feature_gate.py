from google.genai import types


def feature_gate(callback_context) -> types.Content | None:
    step = callback_context.state["current_step"]
    callback_context.state["current_step_id"] = step.step_id

    for dep_id in step.depends_on:
        dep_status = callback_context.state.get(f"step.{dep_id}.status")
        if dep_status not in ("passed", "fixed_and_verified"):
            return types.Content(
                role="model",
                parts=[types.Part(text=f"Blocked: dependency '{dep_id}' has status '{dep_status}'.")],
            )
    return None
