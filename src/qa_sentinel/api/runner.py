import logging
from uuid import UUID

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from qa_sentinel.agents.workflow import root_agent
from qa_sentinel.schemas.test_criteria import TestCriteria, TestStep
from qa_sentinel.state.session_store import SessionStore
from qa_sentinel.tools.github_pr import repo_full_name_from_url
from qa_sentinel.tools.sandbox_provision import provision_and_boot_app

logger = logging.getLogger("qa_sentinel.runner")

APP_NAME = "qa_sentinel_pipeline"


async def execute_run(store: SessionStore, run_id: UUID, claimed: dict) -> None:
    if claimed["local"]:
        logger.info("[run %s] local mode, skipping sandbox provisioning", run_id)
        await store.log_event(
            run_id, "test_runner", "status_change",
            {"status": "local_mode", "base_url": claimed["base_url"]},
        )
        base_url = claimed["base_url"]
    else:
        logger.info("[run %s] provisioning sandbox for repo_url=%s port=%s",
                    run_id, claimed["repo_url"], claimed["port"])
        await store.log_event(
            run_id, "test_runner", "status_change",
            {"repo_url": claimed["repo_url"], "port": claimed["port"], "status": "provisioning"},
        )

        try:
            provisioned = provision_and_boot_app(
                repo_url        = claimed["repo_url"],
                port            = claimed["port"],
                start_command   = claimed["start_command"],
                repo_ref        = claimed["repo_ref"],
                install_command = claimed["install_command"],
            )
        except Exception as exc:
            logger.exception("[run %s] provisioning raised", run_id)
            await store.log_event(run_id, "test_runner", "status_change", {"error": str(exc)})
            await store.set_run_status(run_id, "failed")
            return

        logger.info("[run %s] provisioning result: %s", run_id, provisioned["status"])

        if provisioned["status"] != "ready":
            await store.log_event(run_id, "test_runner", "status_change", provisioned)
            await store.set_run_status(run_id, "failed")
            return

        await store.set_run_environment(run_id, provisioned["environment_id"])
        logger.info("[run %s] environment ready: %s", run_id, provisioned["environment_id"])

        base_url = f"http://localhost:{claimed['port']}"

    criteria = TestCriteria(
        app_name = claimed["app_name"],
        base_url = base_url,
        steps    = [
            TestStep(
                step_id          = s["step_id"],
                instruction      = s["instruction"],
                depends_on       = s["depends_on"],
                expected_outcome = s["expected_outcome"],
            )
            for s in claimed["steps"]
        ],
    )

    session_service = InMemorySessionService()
    runner          = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    user_id         = f"run-{run_id}"
    session_id      = f"run-{run_id}"
    repo_full_name  = repo_full_name_from_url(claimed["repo_url"])

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={"repo_full_name": repo_full_name, "repo_url": claimed["repo_url"]},
    )

    step_status: dict[str, str] = {}

    try:
        for step in criteria.steps:
            logger.info("[run %s] step '%s' starting: %s", run_id, step.step_id, step.instruction)
            await store.log_event(
                run_id, "test_runner", "status_change",
                {"step_id": step.step_id, "status": "starting"},
                step_id=step.step_id,
            )

            prompt = (
                f"Test step '{step.step_id}' on {criteria.base_url}.\n"
                f"Instruction: {step.instruction}\n"
                f"Expected outcome: {step.expected_outcome}"
            )

            state_delta = {
                "current_step": step,
                **{f"step.{dep_id}.status": step_status.get(dep_id, "pending") for dep_id in step.depends_on},
            }

            final_status = "failed"
            async for event in runner.run_async(
                user_id       = user_id,
                session_id    = session_id,
                new_message   = types.Content(role="user", parts=[types.Part(text=prompt)]),
                state_delta   = state_delta,
            ):
                summary = _summarize_event(event)
                logger.info("[run %s][%s] %s", run_id, step.step_id, summary)

                await store.log_event(
                    run_id,
                    source     = getattr(event, "author", "test_runner") or "test_runner",
                    event_type = "model_output" if getattr(event, "content", None) else "tool_call",
                    payload    = {"summary": summary},
                    step_id    = step.step_id,
                )

                for fn_response in event.get_function_responses():
                    response = fn_response.response or {}

                    if fn_response.name == "run_ui_test_step" and response.get("status"):
                        final_status = response["status"]

                    if fn_response.name in ("list_console_messages", "list_network_requests", "take_snapshot"):
                        mcp_text  = _extract_mcp_text(response)
                        is_error  = bool(response.get("isError"))
                        has_hit   = _mcp_response_flags_issue(fn_response.name, mcp_text)
                        logger.info("[run %s][%s][chrome_devtools] %s isError=%s hit=%s",
                                    run_id, step.step_id, fn_response.name, is_error, has_hit)
                        await store.log_event(
                            run_id,
                            source     = "test_runner",
                            event_type = "mcp_tool_call",
                            payload    = {
                                "category": "mcp_tool_call",
                                "name"    : fn_response.name,
                                "isError" : is_error,
                                "hit"     : has_hit,
                                "text"    : mcp_text[:2000],
                            },
                            step_id    = step.step_id,
                        )

                    tool_log = response.get("log")
                    if not tool_log:
                        continue
                    for entry in tool_log:
                        logger.info("[run %s][%s][computer_use] %s: %s",
                                    run_id, step.step_id, entry.get("category"), entry)
                        await store.log_event(
                            run_id,
                            source     = "test_runner",
                            event_type = entry.get("category", "computer_use_event"),
                            payload    = entry,
                            step_id    = step.step_id,
                        )

                if getattr(event, "actions", None) and getattr(event.actions, "state_delta", None):
                    status = event.actions.state_delta.get(f"step.{step.step_id}.status")
                    if status:
                        final_status = status

            step_status[step.step_id] = final_status
            logger.info("[run %s] step '%s' finished: %s", run_id, step.step_id, final_status)
            await store.set_step_status(run_id, step.step_id, final_status)

        logger.info("[run %s] completed", run_id)
        await store.set_run_status(run_id, "completed")

    except Exception as exc:
        logger.exception("[run %s] failed", run_id)
        await store.log_event(run_id, "test_runner", "status_change", {"error": str(exc)})
        await store.set_run_status(run_id, "failed")


def _extract_mcp_text(response: dict) -> str:
    parts = []
    for block in response.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def _mcp_response_flags_issue(tool_name: str, text: str) -> bool:
    lowered = text.lower()
    if tool_name == "list_console_messages":
        return "error" in lowered
    if tool_name == "list_network_requests":
        return any(f" {code} " in f" {lowered} " for code in ("400", "401", "403", "404", "500", "502", "503"))
    return False


def _summarize_event(event) -> str:
    author = getattr(event, "author", None) or "agent"
    parts  = []

    for fc in event.get_function_calls():
        args_preview = {k: v for k, v in (fc.args or {}).items() if k not in ("data",)}
        parts.append(f"calls {fc.name}({args_preview})")

    for fr in event.get_function_responses():
        response = fr.response or {}
        status   = response.get("status")
        parts.append(f"{fr.name} -> status={status}" if status else f"{fr.name} returned")

    content = getattr(event, "content", None)
    if content and content.parts:
        texts = [p.text for p in content.parts if getattr(p, "text", None)]
        if texts:
            parts.append(f'says: "{" ".join(texts)[:200]}"')

    if not parts:
        return f"{author}: (no content/function call)"

    return f"{author}: " + "; ".join(parts)
