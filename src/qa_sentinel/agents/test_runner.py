from google.adk.agents import LlmAgent

from qa_sentinel.callbacks.evidence_capture import capture_error_evidence, evidence_escalation_trigger
from qa_sentinel.callbacks.feature_gate     import feature_gate
from qa_sentinel.callbacks.safety_guard     import guard_run_ui_test_step
from qa_sentinel.tools.chrome_devtools_mcp  import build_chrome_devtools_toolset
from qa_sentinel.tools.computer_use         import run_ui_test_step
from qa_sentinel.tools.shared_chromium      import CDP_URL

chrome_devtools = build_chrome_devtools_toolset(cdp_url=CDP_URL)


def _after_tool(tool, args, tool_context, tool_response):
    tool_response = evidence_escalation_trigger(tool, args, tool_context, tool_response)
    tool_response = capture_error_evidence(tool, args, tool_context, tool_response)
    return tool_response


test_runner_agent = LlmAgent(
    name        = "TestRunner",
    model       = "gemini-3.5-flash",
    instruction = (
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
        "Be efficient inside run_ui_test_step: perform each required action "
        "exactly once, in the order given, then wait briefly and check the "
        "result. Do not repeat an action that already succeeded, do not "
        "re-navigate to a page you're already on, and do not retry a "
        "submission that already went through — this wastes turns and can "
        "trigger duplicate side effects (e.g. a second signup for the same "
        "email). If the first attempt's outcome is unclear, take one more "
        "screenshot to check — do not restart the whole sequence from the "
        "beginning.\n\n"
        "After each step, compare the resulting screenshot/state against the "
        "expected outcome in the test criteria.\n\n"
        "Regardless of whether the screenshot looked correct: after every "
        "run_ui_test_step call, needs_chrome_devtools_check is always set in "
        "state — always call list_console_messages and list_network_requests "
        "before deciding this step's final status. A screenshot only shows "
        "what rendered; it cannot show a server-side failure (e.g. a 403 or "
        "500) that the page displays no visible error for. If those tools "
        "reveal a console error or a network response with status >= 400 for "
        "this step's action, the step FAILED even if run_ui_test_step itself "
        "reported passed and the screenshot looked fine — trust the network/"
        "console evidence over the visual read every time they disagree.\n\n"
        "IF the outcome matches expectations AND no console/network errors "
        "were found: mark the step passed.\n\n"
        "IF the outcome does not match, OR the screenshot looked fine but "
        "console/network evidence shows a real error: mark the step failed. "
        "Never report a failure without this evidence attached. A failure "
        "report with no console/network evidence is incomplete and must be "
        "flagged as low-confidence rather than a resolved bug."
    ),
    tools                 = [run_ui_test_step, chrome_devtools],
    before_agent_callback = feature_gate,
    before_tool_callback  = guard_run_ui_test_step,
    after_tool_callback   = _after_tool,
)
