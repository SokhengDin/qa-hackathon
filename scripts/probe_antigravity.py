from google import genai
from google.genai._gaos.lib.compat_errors import BadRequestError

from qa_sentinel.config.settings import settings

AGENT = "antigravity-preview-05-2026"


def main() -> None:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    environment = {
        "type": "remote",
        "sources": [{
            "type": "repository",
            "source": "https://github.com/active-loop/demo-target-app",
            "target": "/workspace/app",
        }],
    }

    prompt = "A UI test failed. Diagnose and describe a fix in one paragraph."

    kwargs = {
        "agent": AGENT,
        "input": prompt,
        "environment": environment,
        "background": True,
    }

    print("--- request kwargs ---")
    print(kwargs)

    try:
        interaction = client.interactions.create(**kwargs)
        print("--- SUCCESS ---")
        print(interaction)
    except BadRequestError as exc:
        print("--- BadRequestError ---")
        print("status_code:", exc.status_code)
        print("body:", exc.body)
        try:
            print("response text:", exc.response.text)
        except Exception as e:
            print("could not read response.text:", e)
    except Exception as exc:
        print("--- OTHER EXCEPTION ---")
        print(type(exc), exc)


if __name__ == "__main__":
    main()
