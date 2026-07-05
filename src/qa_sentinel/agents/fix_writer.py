from google.adk.agents import LlmAgent

from qa_sentinel.callbacks.evidence_capture import capture_antigravity_handoff
from qa_sentinel.tools.antigravity import dispatch_fix_to_antigravity

fix_writer_agent = LlmAgent(
    name        = "FixWriter",
    model       = "gemini-3.5-flash",
    instruction = (
        "You receive a failed test step's evidence bundle. Only act if confidence "
        "is medium or high (see state['evidence.<step_id>.confidence']) — if low, "
        "do not call dispatch_fix_to_antigravity; instead report that this needs "
        "human review. When you do act, always pass the SAME environment_id used "
        "for prior features in this run, so file state persists across the whole "
        "test session.\n\n"
        "The evidence argument must be a dict with exactly these keys: "
        "step_id (string), console_errors (list, may be empty), "
        "network_failures (list, may be empty), model_stated_intent (string "
        "summarizing what went wrong), and confidence (float). Do not invent "
        "different key names — use these exact ones."
    ),
    tools               = [dispatch_fix_to_antigravity],
    after_tool_callback = capture_antigravity_handoff,
)
