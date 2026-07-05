import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, UploadFile

from qa_sentinel.api.runner import execute_run
from qa_sentinel.api.test_criteria_md import parse_test_criteria_md
from qa_sentinel.config.settings import settings
from qa_sentinel.state.session_store import SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logging.getLogger("qa_sentinel").setLevel(logging.INFO)

os.environ.setdefault("GOOGLE_API_KEY", settings.GEMINI_API_KEY)
os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)

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
    local            : bool = Form(False),
) -> dict:
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
        local           = local,
    )

    claimed = await store.claim_run(run_id)
    if claimed is None:
        raise HTTPException(status_code=500, detail="failed_to_claim_freshly_created_run")

    background_tasks.add_task(execute_run, store, run_id, claimed)

    return {"run_id": str(run_id), "status": "running"}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
