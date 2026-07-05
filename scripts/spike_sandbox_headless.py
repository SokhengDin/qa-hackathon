
import time

from google import genai

from qa_sentinel.config.settings import settings


def main() -> None:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    interaction = client.interactions.create(
        agent       = settings.ANTIGRAVITY_AGENT_ID,
        input       = (
            "Install chromium and node.js tooling if not present. Then run "
            "`npx -y chrome-devtools-mcp@latest --headless --browserUrl "
            "http://127.0.0.1:9222 &` in the background. Confirm the process "
            "started and print its PID."
        ),
        environment = "remote",
        background  = True,
    )

    while interaction.status == "in_progress":
        time.sleep(5)
        interaction = client.interactions.get(id=interaction.id)

    print(f"Status: {interaction.status}")
    print(f"Environment ID: {interaction.environment_id}")
    print(interaction.output_text)
if __name__ == "__main__":
    main()
