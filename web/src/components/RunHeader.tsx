import type { RunWithSteps } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  queued   : "Queued",
  running  : "Running",
  completed: "Completed",
  failed   : "Failed",
};

export function RunHeader({ run }: { run: RunWithSteps }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border-soft pb-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{run.appName}</h1>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-border-soft px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide ${
              run.status === "running" ? "text-accent" : "text-ink-muted"
            }`}
          >
            {run.status === "running" && (
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            )}
            {STATUS_LABEL[run.status] ?? run.status}
          </span>
        </div>
        <p className="mt-1 font-mono text-xs text-ink-faint">{run.baseUrl ?? run.repoUrl}</p>
      </div>
      <p className="shrink-0 font-mono text-xs text-ink-faint">
        {new Date(run.createdAt).toLocaleString("en-US", { timeZone: "UTC" })}
      </p>
    </div>
  );
}
