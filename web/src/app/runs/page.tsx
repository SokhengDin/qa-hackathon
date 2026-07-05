import { RunList } from "@/components/RunList";
import { db } from "@/lib/db";

export default async function RunsPage() {
  const runs = await db.run.findMany({
    orderBy: { createdAt: "desc" },
    include: { steps: { select: { status: true } } },
    take: 50,
  });

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="mb-6 text-2xl font-semibold">QA Sentinel — Pipeline Runs</h1>
      <RunList runs={runs} />
    </main>
  );
}
