-- AlterTable
ALTER TABLE "runs" ADD COLUMN     "install_command" TEXT,
ADD COLUMN     "port" INTEGER,
ADD COLUMN     "repo_ref" TEXT NOT NULL DEFAULT 'main',
ADD COLUMN     "start_command" TEXT;

-- Backfill existing (seed/dev) rows with placeholder values before enforcing NOT NULL.
UPDATE "runs" SET "port" = 3000, "start_command" = 'npm start' WHERE "port" IS NULL;

ALTER TABLE "runs" ALTER COLUMN "port" SET NOT NULL;
ALTER TABLE "runs" ALTER COLUMN "start_command" SET NOT NULL;
