import json
from uuid import UUID

import asyncpg

from qa_sentinel.schemas.evidence_bundle import EvidenceBundle
from qa_sentinel.schemas.review_decision import ReviewDecision

# Table shape owned by web/prisma/schema.prisma — Python never runs its own
# migrations against these tables, only reads/writes rows. See tasks/task_2.md.


class SessionStore:
    def __init__(self, database_url: str):
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._database_url)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def create_run(
        self,
        app_type       : str,
        app_name       : str,
        base_url       : str | None,
        repo_url       : str,
        start_command  : str,
        port           : int,
        steps          : list[dict],
        repo_ref       : str = "main",
        install_command: str | None = None,
        otel_endpoint  : str | None = None,
        environment_id : str | None = None,
        local          : bool = False,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                run_id = await conn.fetchval(
                    """
                    INSERT INTO runs
                        (app_type, app_name, base_url, repo_url, repo_ref, install_command,
                         start_command, port, otel_endpoint, environment_id, local, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'queued')
                    RETURNING id
                    """,
                    app_type,
                    app_name,
                    base_url,
                    repo_url,
                    repo_ref,
                    install_command,
                    start_command,
                    port,
                    otel_endpoint,
                    environment_id,
                    local,
                )

                for step in steps:
                    await conn.execute(
                        """
                        INSERT INTO steps
                            (run_id, step_id, instruction, depends_on, expected_outcome, status)
                        VALUES ($1, $2, $3, $4, $5, 'pending')
                        """,
                        run_id,
                        step["step_id"],
                        step["instruction"],
                        step["depends_on"],
                        step["expected_outcome"],
                    )

        return run_id

    async def claim_next_queued_run(self) -> dict | None:
        return await self._claim(
            "SELECT id, app_type, app_name, base_url, repo_url, repo_ref, install_command, "
            "start_command, port, otel_endpoint, environment_id, local "
            "FROM runs WHERE status = 'queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
        )

    async def claim_run(self, run_id: UUID) -> dict | None:
        return await self._claim(
            "SELECT id, app_type, app_name, base_url, repo_url, repo_ref, install_command, "
            "start_command, port, otel_endpoint, environment_id, local "
            "FROM runs WHERE id = $1 AND status = 'queued' FOR UPDATE SKIP LOCKED",
            run_id,
        )

    async def _claim(self, query: str, *params) -> dict | None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(query, *params)
                if row is None:
                    return None

                await conn.execute("UPDATE runs SET status = 'running' WHERE id = $1", row["id"])

                steps = await conn.fetch(
                    """
                    SELECT step_id, instruction, depends_on, expected_outcome, status
                    FROM steps
                    WHERE run_id = $1
                    ORDER BY created_at
                    """,
                    row["id"],
                )

        return {
            "run_id"         : row["id"],
            "app_type"       : row["app_type"],
            "app_name"       : row["app_name"],
            "base_url"       : row["base_url"],
            "repo_url"       : row["repo_url"],
            "repo_ref"       : row["repo_ref"],
            "install_command": row["install_command"],
            "start_command"  : row["start_command"],
            "port"           : row["port"],
            "otel_endpoint"  : row["otel_endpoint"],
            "environment_id" : row["environment_id"],
            "local"          : row["local"],
            "steps"          : [dict(s) for s in steps],
        }

    async def set_run_status(self, run_id: UUID, status: str) -> None:
        async with self._pool.acquire() as conn:
            if status in ("completed", "failed"):
                await conn.execute(
                    "UPDATE runs SET status = $2, completed_at = now() WHERE id = $1",
                    run_id,
                    status,
                )
            else:
                await conn.execute("UPDATE runs SET status = $2 WHERE id = $1", run_id, status)

    async def set_run_environment(self, run_id: UUID, environment_id: str) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO environments (id, status, source_repo_url)
                    VALUES ($1, 'active', NULL)
                    ON CONFLICT (id) DO UPDATE SET
                        status         = 'active',
                        last_active_at = now()
                    """,
                    environment_id,
                )
                await conn.execute(
                    "UPDATE runs SET environment_id = $2 WHERE id = $1",
                    run_id,
                    environment_id,
                )

    async def set_environment_status(self, environment_id: str, status: str) -> None:
        """Mirrors the Antigravity environment lifecycle (docs/environment.md):
        active -> idle -> offline -> deleted. The pipeline updates this row
        whenever it observes a status change, so the dashboard never has to
        query Google's API just to render a page."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE environments SET status = $2, last_active_at = now() WHERE id = $1",
                environment_id,
                status,
            )

    async def set_step_status(self, run_id: UUID, step_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE steps SET status = $3 WHERE run_id = $1 AND step_id = $2",
                run_id,
                step_id,
                status,
            )

    async def set_step_pr_url(self, run_id: UUID, step_id: str, pr_url: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE steps SET pr_url = $3 WHERE run_id = $1 AND step_id = $2",
                run_id,
                step_id,
                pr_url,
            )

    async def _get_step_row_id(self, run_id: UUID, step_id: str) -> UUID:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT id FROM steps WHERE run_id = $1 AND step_id = $2",
                run_id,
                step_id,
            )

    async def save_evidence_bundle(self, run_id: UUID, bundle: EvidenceBundle) -> None:
        step_row_id = await self._get_step_row_id(run_id, bundle.step_id)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO evidence_bundles
                    (step_id, screenshot_path, console_errors, network_failures,
                     model_stated_intent, confidence, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (step_id) DO UPDATE SET
                    screenshot_path     = EXCLUDED.screenshot_path,
                    console_errors      = EXCLUDED.console_errors,
                    network_failures    = EXCLUDED.network_failures,
                    model_stated_intent = EXCLUDED.model_stated_intent,
                    confidence          = EXCLUDED.confidence,
                    timestamp           = EXCLUDED.timestamp
                """,
                step_row_id,
                bundle.screenshot_path,
                json.dumps(bundle.console_errors),
                json.dumps(bundle.network_failures),
                bundle.model_stated_intent,
                bundle.confidence,
                bundle.timestamp,
            )

    async def save_review_decision(self, run_id: UUID, decision: ReviewDecision) -> None:
        step_row_id = await self._get_step_row_id(run_id, decision.step_id)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO review_decisions (step_id, decision, reviewer_note)
                VALUES ($1, $2, $3)
                ON CONFLICT (step_id) DO UPDATE SET
                    decision      = EXCLUDED.decision,
                    reviewer_note = EXCLUDED.reviewer_note
                """,
                step_row_id,
                decision.decision,
                decision.reviewer_note,
            )

    async def log_event(
        self,
        run_id    : UUID,
        source    : str,
        event_type: str,
        payload   : dict,
        step_id   : str | None = None,
    ) -> None:
        """Raw, complete agent trace — every tool call, every intent, every
        function_result. Distinct from EvidenceBundle, which is the curated,
        judged artifact. See tasks/task_2.md §4."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO run_logs (run_id, step_id, source, event_type, payload)
                VALUES ($1, $2, $3, $4, $5)
                """,
                run_id,
                step_id,
                source,
                event_type,
                json.dumps(payload),
            )
