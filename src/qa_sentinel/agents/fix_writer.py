from google.adk.agents import LlmAgent

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
        "test session."
    ),
    tools = [dispatch_fix_to_antigravity],
)
