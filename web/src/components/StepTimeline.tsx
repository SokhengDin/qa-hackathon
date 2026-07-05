import { EvidencePanel } from "@/components/EvidencePanel";
import { StatusBadge } from "@/components/StatusBadge";
import type { RunWithSteps } from "@/lib/types";

export function StepTimeline({ run }: { run: RunWithSteps }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">{run.appName}</h1>
          <span className="text-xs uppercase tracking-wide text-white/40">{run.status}</span>
        </div>
        <p className="text-sm text-white/50">{run.baseUrl ?? run.repoUrl}</p>
      </div>

      <div className="flex flex-col gap-4">
        {run.steps.map((step) => (
          <div key={step.id} className="flex flex-col gap-3 rounded-lg border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{step.stepId}</div>
                <div className="text-sm text-white/50">{step.instruction}</div>
              </div>
              <StatusBadge status={step.status} />
            </div>

            {step.dependsOn.length > 0 && (
              <div className="text-xs text-white/40">depends on: {step.dependsOn.join(", ")}</div>
            )}

            {(step.status === "failed" ||
              step.status === "blocked" ||
              step.status === "fixed_and_verified") && <EvidencePanel step={step} />}
          </div>
        ))}
      </div>
    </div>
  );
}
