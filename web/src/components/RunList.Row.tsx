import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/format";
import type { RunListItem } from "@/lib/types";

export function RunListRow({ run }: { run: RunListItem }) {
  return (
    <Link
      href={`/runs/${run.id}`}
      className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-4 py-3 hover:bg-white/10"
    >
      <div>
        <div className="font-medium">{run.appName}</div>
        <div className="text-sm text-white/50">{run.baseUrl ?? run.repoUrl}</div>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex gap-3">
          {run.steps.map((step, i) => (
            <StatusBadge key={i} status={step.status} />
          ))}
        </div>
        <div className="text-xs uppercase tracking-wide text-white/40">{run.status}</div>
        <div className="text-sm text-white/40">{formatDateTime(new Date(run.createdAt))}</div>
      </div>
    </Link>
  );
}
