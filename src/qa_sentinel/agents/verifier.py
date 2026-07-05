from google import genai
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from qa_sentinel.config.settings import settings

AGENT = "antigravity-preview-05-2026"


def verify_fix(environment_id: str, previous_interaction_id: str, page_url: str) -> dict:
    """Re-runs the app in its fixed state and checks the console for the original
    error via chrome-devtools-mcp, registered as a remote MCP tool on this call."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    interaction = client.interactions.create(
        agent                   = AGENT,
        environment             = environment_id,
        previous_interaction_id = previous_interaction_id,
        input                   = (
            f"Start the app and navigate to {page_url}. Use the chrome_devtools "
            "tools to check the console for errors. Report whether the "
            "originally-reported error is still present."
        ),
        tools = [{
            "type": "mcp_server",
            "name": "chrome_devtools",              # must be lowercase, ^[a-z0-9_-]+$
            "url" : "http://127.0.0.1:9222",        # streamable HTTP only, no SSE
        }],
    )

    return {
        "status"     : "resolved" if "no error" in interaction.output_text.lower() else "still_failing",
        "output_text": interaction.output_text,
    }


verifier_agent = LlmAgent(
    name        = "Verifier",
    model       = "gemini-3.5-flash",
    instruction = (
        "Given a fix that was just applied, call verify_fix to confirm the "
        "original console/network error is actually gone before marking this "
        "feature 'fixed_and_verified'. Never trust FixWriter's own claim without "
        "this independent re-check."
    ),
    tools = [FunctionTool(func=verify_fix)],
)
