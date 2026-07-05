import { notFound } from "next/navigation";

import { ActivityFeed } from "@/components/ActivityFeed";
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
    <main className="mx-auto max-w-3xl px-6 py-10">
      <StepTimeline run={run} />
      <div className="mt-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-white/40">
          Activity feed
        </h2>
        <ActivityFeed logs={run.logs} runId={run.id} />
      </div>
    </main>
  );
}
