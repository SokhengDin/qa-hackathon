-- CreateTable
CREATE TABLE "runs" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "app_type" TEXT NOT NULL,
    "app_name" TEXT NOT NULL,
    "base_url" TEXT,
    "repo_url" TEXT NOT NULL,
    "environment_id" UUID,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),

    CONSTRAINT "runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "environments" (
    "id" UUID NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "source_repo_url" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_active_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "environments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "steps" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "run_id" UUID NOT NULL,
    "step_id" TEXT NOT NULL,
    "instruction" TEXT NOT NULL,
    "depends_on" TEXT[],
    "expected_outcome" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "pr_url" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "steps_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "evidence_bundles" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "step_id" UUID NOT NULL,
    "screenshot_path" TEXT NOT NULL,
    "console_errors" JSONB NOT NULL,
    "network_failures" JSONB NOT NULL,
    "model_stated_intent" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "evidence_bundles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "review_decisions" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "step_id" UUID NOT NULL,
    "decision" TEXT NOT NULL,
    "reviewer_note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "review_decisions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "run_logs" (
    "id" UUID NOT NULL DEFAULT uuid_generate_v4(),
    "run_id" UUID NOT NULL,
    "step_id" TEXT,
    "source" TEXT NOT NULL,
    "event_type" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "run_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "steps_run_id_step_id_key" ON "steps"("run_id", "step_id");

-- CreateIndex
CREATE UNIQUE INDEX "evidence_bundles_step_id_key" ON "evidence_bundles"("step_id");

-- CreateIndex
CREATE UNIQUE INDEX "review_decisions_step_id_key" ON "review_decisions"("step_id");

-- CreateIndex
CREATE INDEX "run_logs_run_id_created_at_idx" ON "run_logs"("run_id", "created_at");

-- AddForeignKey
ALTER TABLE "runs" ADD CONSTRAINT "runs_environment_id_fkey" FOREIGN KEY ("environment_id") REFERENCES "environments"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "steps" ADD CONSTRAINT "steps_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "runs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "evidence_bundles" ADD CONSTRAINT "evidence_bundles_step_id_fkey" FOREIGN KEY ("step_id") REFERENCES "steps"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "review_decisions" ADD CONSTRAINT "review_decisions_step_id_fkey" FOREIGN KEY ("step_id") REFERENCES "steps"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "run_logs" ADD CONSTRAINT "run_logs_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "runs"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
