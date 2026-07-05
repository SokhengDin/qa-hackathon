from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from qa_sentinel.callbacks.evidence_capture import evidence_escalation_trigger
from qa_sentinel.callbacks.feature_gate     import feature_gate
from qa_sentinel.callbacks.safety_guard     import guard_run_ui_test_step
from qa_sentinel.callbacks.step_verdict     import compute_step_verdict
from qa_sentinel.tools.computer_use         import run_ui_test_step

BASE_INSTRUCTION = (
    "You test web app features one at a time, in dependency order, using "
    "run_ui_test_step to act on the page. The target is always your own "
    "disposable local test application running on localhost — never a "
    "real third-party site or a real account. When you call "
    "run_ui_test_step, always state this plainly in the instruction text, "
    "e.g. 'This is my own local test app running at http://localhost:PORT. "
    "...' — do not phrase steps in ways that could read as accessing "
    "someone else's account, bypassing verification, or handling real "
    "payment details; frame verification/checkout steps as testing your "
    "own app's fake, simulated flow.\n\n"
    "When a step is just reading/checking page content (not clicking or "
    "typing), phrase it as plain task-oriented reading, e.g. 'Read the "
    "visible text on the page and report whether it shows X.' Avoid the "
    "combination of the words 'observe' or 'confirm' together with a "
    "localhost URL that has query parameters — that phrasing pattern has "
    "been misread as a local security probe and blocked outright. Never "
    "repeat the raw URL back in the instruction text; just describe what "
    "the current page is and what to check for.\n\n"
    "Call run_ui_test_step EXACTLY ONCE per step, no matter what. Never "
    "call it a second time to 'double check' or verify with a simpler "
    "instruction — a second call will be blocked and wastes turns. "
    "Inside run_ui_test_step, perform each required action exactly once, "
    "in the order given, then wait briefly and check the result. Do not "
    "repeat an action that already succeeded, do not re-navigate to a "
    "page you're already on, and do not retry a submission that already "
    "went through.\n\n"
    "run_ui_test_step automatically captures real console errors and "
    "failed (status >= 400) network responses while it drives the page — "
    "you do not need to call any other tool to check for these; they are "
    "already recorded. After run_ui_test_step returns, just summarize "
    "what happened: compare the final screenshot/state against the "
    "expected outcome in the test criteria, and state clearly whether it "
    "matched. A screenshot only shows what rendered; it cannot show a "
    "server-side failure the page displays no visible error for — if you "
    "have any doubt, say so plainly rather than guessing."
)


def build_test_runner_instruction(ctx: ReadonlyContext) -> str:
    """Dynamic instruction (evaluated fresh every turn) so a loop-back
    re-test after FixerAgent pushes a fix gets an explicit reminder of the
    EXACT original step instruction to re-run — TestRunner has been observed
    instead re-entering with only a trivial "is the page accessible" check
    of its own invention, consuming its one allowed run_ui_test_step call on
    the wrong thing and never actually re-testing the original failing
    action at all."""
    step = ctx.state.get("current_step")
    step_id = ctx.state.get("current_step_id")
    fix_attempts = ctx.state.get(f"step.{step_id}.fix_attempts", 0) if step_id else 0

    if not step or fix_attempts == 0:
        return BASE_INSTRUCTION

    return (
        f"{BASE_INSTRUCTION}\n\n"
        f"IMPORTANT — this is a re-test after FixerAgent just pushed a fix "
        f"for this exact step. Call run_ui_test_step with the ORIGINAL "
        f"instruction below, verbatim — do not substitute a simpler or "
        f"different check (e.g. just loading the homepage). The whole point "
        f"of this pass is to confirm the SAME action that failed before now "
        f"succeeds:\n\n"
        f"Original instruction: {step.instruction}\n"
        f"Original expected outcome: {step.expected_outcome}"
    )


test_runner_agent = LlmAgent(
    name        = "TestRunner",
    model       = "gemini-3.5-flash",
    instruction = build_test_runner_instruction,
    tools                 = [run_ui_test_step],
    before_agent_callback = feature_gate,
    before_tool_callback  = guard_run_ui_test_step,
    after_tool_callback   = evidence_escalation_trigger,
    after_agent_callback  = compute_step_verdict,
)
