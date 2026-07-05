import { notFound } from "next/navigation";

import { ActivityFeed } from "@/components/ActivityFeed";
import { AutoRefresh } from "@/components/AutoRefresh";
import { RunHeader } from "@/components/RunHeader";
import { StepTimeline } from "@/components/StepTimeline";
import { db } from "@/lib/db";

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  const run = await db.run.findUnique({
    where: { id: runId },
    include: {
      steps: {
        include: { evidence: true, reviewDecision: true },
        orderBy: { createdAt: "asc" },
      },
      logs: {
        orderBy: { createdAt: "asc" },
        take: 200,
      },
    },
  });

  if (!run) notFound();

  return (
    <main className="mx-auto flex h-dvh max-w-6xl flex-col px-6 py-8">
      {run.status === "running" && <AutoRefresh intervalMs={2000} />}

      <RunHeader run={run} />

      <div className="mt-6 grid min-h-0 flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="flex min-h-0 flex-col gap-3 overflow-y-auto pr-1">
          <h2 className="text-xs font-medium uppercase tracking-wide text-ink-faint">
            Steps
          </h2>
          <StepTimeline run={run} />
        </section>

        <section className="flex min-h-0 flex-col gap-3">
          <h2 className="text-xs font-medium uppercase tracking-wide text-ink-faint">
            Activity
          </h2>
          <div className="min-h-0 flex-1">
            <ActivityFeed logs={run.logs} runId={run.id} />
          </div>
        </section>
      </div>
    </main>
  );
}
