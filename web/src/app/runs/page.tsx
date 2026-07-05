import { AutoRefresh } from "@/components/AutoRefresh";
import { RunList } from "@/components/RunList";
import { db } from "@/lib/db";

export default async function RunsPage() {
  const runs = await db.run.findMany({
    orderBy: { createdAt: "desc" },
    include: { steps: { select: { status: true } } },
    take: 50,
  });

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <AutoRefresh />
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">QA Sentinel</p>
      <h1 className="mt-1 text-xl font-semibold tracking-tight">Pipeline runs</h1>
      <div className="mt-6">
        <RunList runs={runs} />
      </div>
    </main>
  );
}
