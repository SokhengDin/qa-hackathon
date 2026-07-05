from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, UploadFile

from qa_sentinel.api.runner import execute_run
from qa_sentinel.api.test_criteria_md import parse_test_criteria_md
from qa_sentinel.config.settings import settings
from qa_sentinel.state.session_store import SessionStore

store = SessionStore(settings.DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.connect()
    yield
    await store.close()


app = FastAPI(title="QA Sentinel Runner", lifespan=lifespan)


@app.post("/api/agent/runs", status_code=202)
async def create_and_start_run(
    background_tasks: BackgroundTasks,
    test_criteria    : UploadFile,
    repo_url         : str = Form(...),
    start_command    : str = Form(...),
    port             : int = Form(...),
    repo_ref         : str = Form("main"),
    install_command  : str | None = Form(None),
    otel_endpoint    : str | None = Form(None),
    app_type         : Literal["webapp"] = Form("webapp"),
    environment_id   : str | None = Form(None),
) -> dict:
    """The single write path for kicking off a pipeline run — owned entirely
    by the Python side. web/ (the dashboard) is read-only plus the single
    review-decision action; it never creates Run/Step rows itself. Called via
    curl/CI/a script, not a dashboard button, per tasks/task_1.md §0.

    Any public repo_url + a test_criteria.md is enough to test any app — this
    endpoint is not tied to a fixed demo app. sandbox_provision.py (called from
    runner.py once this run is claimed) clones repo_url, boots it with
    start_command on port, and Computer Use tests it from inside that same
    sandbox. See tasks/task_3.md.

    test_criteria is an uploaded .md file (see configs/test_criteria/example_app.md);
    its own frontmatter supplies app_name and base_url, so those aren't passed
    as separate form fields. start_command/port are required, not inferred —
    per tasks/task_3.md §2, guessing how an arbitrary repo boots itself is a
    real source of provisioning hangs."""
    raw = await test_criteria.read()
    try:
        criteria = parse_test_criteria_md(raw.decode("utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid test_criteria .md: {exc}") from exc

    run_id = await store.create_run(
        app_type        = app_type,
        app_name        = criteria.app_name,
        base_url        = criteria.base_url,
        repo_url        = repo_url,
        repo_ref        = repo_ref,
        install_command = install_command,
        start_command   = start_command,
        port            = port,
        otel_endpoint   = otel_endpoint,
        steps           = [s.model_dump() for s in criteria.steps],
        environment_id  = environment_id,
    )

    claimed = await store.claim_run(run_id)
    if claimed is None:
        raise HTTPException(status_code=500, detail="failed_to_claim_freshly_created_run")

    background_tasks.add_task(execute_run, store, run_id, claimed)

    return {"run_id": str(run_id), "status": "running"}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
