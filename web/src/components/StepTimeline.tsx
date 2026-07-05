import { EvidencePanel } from "@/components/EvidencePanel";
import { StatusBadge } from "@/components/StatusBadge";
import type { RunWithSteps } from "@/lib/types";

export function StepTimeline({ run }: { run: RunWithSteps }) {
  const firstPendingIndex = run.steps.findIndex((s) => s.status === "pending");

  return (
    <div className="flex flex-col gap-3">
      {run.steps.map((step, i) => {
        const isRunning = run.status === "running" && i === firstPendingIndex;

        return (
          <div
            key={step.id}
            className={`flex flex-col gap-3 rounded-lg border p-4 transition-colors ${
              isRunning
                ? "border-accent/50 bg-accent-soft"
                : "border-border-soft bg-surface"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-mono text-sm font-medium">{step.stepId}</div>
                <div className="mt-0.5 text-sm text-ink-muted">{step.instruction}</div>
              </div>
              {isRunning ? (
                <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-accent">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                  Running
                </span>
              ) : (
                <div className="shrink-0">
                  <StatusBadge status={step.status} />
                </div>
              )}
            </div>

            {step.dependsOn.length > 0 && (
              <div className="font-mono text-xs text-ink-faint">
                depends on {step.dependsOn.join(", ")}
              </div>
            )}

            {(step.status === "failed" ||
              step.status === "blocked" ||
              step.status === "fixed_and_verified") && <EvidencePanel step={step} />}
          </div>
        );
      })}
    </div>
  );
}
