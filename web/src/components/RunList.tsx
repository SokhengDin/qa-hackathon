import { RunListRow } from "@/components/RunList.Row";
import type { RunListItem } from "@/lib/types";

export function RunList({ runs }: { runs: RunListItem[] }) {
  if (runs.length === 0) {
    return <p className="text-ink-muted">No pipeline runs yet.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {runs.map((run) => (
        <RunListRow key={run.id} run={run} />
      ))}
    </div>
  );
}
