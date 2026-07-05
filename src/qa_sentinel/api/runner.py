import logging
from uuid import UUID

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from qa_sentinel.agents.workflow import root_agent
from qa_sentinel.schemas.test_criteria import TestCriteria, TestStep
from qa_sentinel.state.session_store import SessionStore
from qa_sentinel.tools.sandbox_provision import provision_and_boot_app

logger = logging.getLogger("qa_sentinel.runner")

APP_NAME = "qa_sentinel_pipeline"


async def execute_run(store: SessionStore, run_id: UUID, claimed: dict) -> None:
    """Provisions a fresh Antigravity sandbox for this run (clone + boot,
    tasks/task_3.md §3), then drives root_agent one TestStep at a time in
    dependency order against the app now running inside that sandbox. Writes
    Step/Evidence/RunLog rows back to Postgres as it goes, per tasks/task_2.md
    §6 step 5. Runs as a FastAPI background task — the HTTP request that
    triggered this has already returned 202."""
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
        # A provisioning-time exception (e.g. a transient 5xx from the
        # Antigravity API that exhausted sandbox_provision.py's own retries)
        # must still resolve this run's status — otherwise it's stuck at
        # "running" forever with no error visible anywhere, per the crash
        # this comment is fixing.
        logger.exception("Provisioning raised for run %s", run_id)
        await store.log_event(run_id, "test_runner", "status_change", {"error": str(exc)})
        await store.set_run_status(run_id, "failed")
        return

    if provisioned["status"] != "ready":
        await store.log_event(run_id, "test_runner", "status_change", provisioned)
        await store.set_run_status(run_id, "failed")
        return

    # Written onto the Run row immediately (tasks/task_3.md §7), before any
    # test step runs, so the dashboard can show which environment backs this
    # run even if a later step fails.
    await store.set_run_environment(run_id, provisioned["environment_id"])

    # The app only becomes reachable once provisioning finishes — base_url is
    # derived here, not taken from the uploaded test_criteria.md, since the
    # app doesn't exist anywhere until the sandbox clones and boots it.
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

    await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

    step_status: dict[str, str] = {}

    try:
        for step in criteria.steps:
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
                await store.log_event(
                    run_id,
                    source     = getattr(event, "author", "test_runner") or "test_runner",
                    event_type = "model_output" if getattr(event, "content", None) else "tool_call",
                    payload    = {"event": str(event)[:2000]},
                    step_id    = step.step_id,
                )

                # run_ui_test_step returns a structured `log` list covering all
                # five categories docs/computer_use.md asks clients to log
                # (prompt, screenshot, function_call, safety response, executed
                # action) — tasks/task_4.md §2.5. Unpack it into its own
                # RunLog rows rather than relying on the generic event summary
                # above, which only captures a truncated string repr.
                for fn_response in event.get_function_responses():
                    tool_log = (fn_response.response or {}).get("log")
                    if not tool_log:
                        continue
                    for entry in tool_log:
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
            await store.set_step_status(run_id, step.step_id, final_status)

        await store.set_run_status(run_id, "completed")

    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        await store.log_event(run_id, "test_runner", "status_change", {"error": str(exc)})
        await store.set_run_status(run_id, "failed")
