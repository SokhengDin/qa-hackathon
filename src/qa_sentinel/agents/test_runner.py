from google.adk.agents import LlmAgent

from qa_sentinel.callbacks.evidence_capture import capture_error_evidence, evidence_escalation_trigger
from qa_sentinel.callbacks.feature_gate     import feature_gate
from qa_sentinel.callbacks.safety_guard     import guard_run_ui_test_step
from qa_sentinel.tools.chrome_devtools_mcp  import build_chrome_devtools_toolset
from qa_sentinel.tools.computer_use         import run_ui_test_step

chrome_devtools = build_chrome_devtools_toolset()


def _after_tool(tool, args, tool_context, tool_response):
    tool_response = evidence_escalation_trigger(tool, args, tool_context, tool_response)
    tool_response = capture_error_evidence(tool, args, tool_context, tool_response)
    return tool_response


test_runner_agent = LlmAgent(
    name        = "TestRunner",
    model       = "gemini-3.5-flash",
    instruction = (
        "You test web app features one at a time, in dependency order, using "
        "run_ui_test_step to act on the page.\n\n"
        "After each step, compare the resulting screenshot/state against the "
        "expected outcome in the test criteria.\n\n"
        "IF the outcome matches expectations: mark the step passed, move on. "
        "Do NOT call any chrome-devtools tools — there's nothing to diagnose.\n\n"
        "IF the outcome does NOT match (or is ambiguous), and "
        "needs_chrome_devtools_check is set in state: immediately call "
        "list_console_messages and list_network_requests to capture the "
        "technical cause. Never report a failure without this evidence attached. "
        "A failure report with no console/network evidence is incomplete and "
        "must be flagged as low-confidence rather than a resolved bug."
    ),
    tools                 = [run_ui_test_step, chrome_devtools],
    before_agent_callback = feature_gate,
    before_tool_callback  = guard_run_ui_test_step,
    after_tool_callback   = _after_tool,
)
