import Link from "next/link";

import { formatDateTime } from "@/lib/format";
import type { RunListItem } from "@/lib/types";

const DOT_CLASS: Record<string, string> = {
  pending            : "bg-ink-faint",
  passed             : "bg-status-passed",
  failed             : "bg-status-failed",
  blocked            : "bg-status-blocked",
  fixed_and_verified : "bg-status-fixed",
};

export function RunListRow({ run }: { run: RunListItem }) {
  return (
    <Link
      href={`/runs/${run.id}`}
      className="flex items-center justify-between gap-4 rounded-lg border border-border-soft bg-surface px-4 py-3 transition-colors hover:border-border hover:bg-surface-raised"
    >
      <div className="min-w-0">
        <div className="font-medium">{run.appName}</div>
        <div className="truncate font-mono text-xs text-ink-faint">
          {run.baseUrl ?? run.repoUrl}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <div className="flex gap-1.5" title={run.steps.map((s) => s.status).join(", ")}>
          {run.steps.map((step, i) => (
            <span
              key={i}
              className={`h-2 w-2 rounded-full ${DOT_CLASS[step.status] ?? "bg-ink-faint"}`}
            />
          ))}
        </div>
        <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-ink-faint">
          {run.status === "running" && (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          )}
          {run.status}
        </div>
        <div className="font-mono text-xs text-ink-faint">
          {formatDateTime(new Date(run.createdAt))}
        </div>
      </div>
    </Link>
  );
}
