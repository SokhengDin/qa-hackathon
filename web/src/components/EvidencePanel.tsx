import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { PRLink } from "@/components/PRLink";
import { ReviewForm } from "@/components/ReviewForm";
import type { ConsoleError, NetworkFailure, StepWithEvidence } from "@/lib/types";

export function EvidencePanel({ step }: { step: StepWithEvidence }) {
  const evidence = step.evidence;

  if (!evidence) {
    return <p className="text-sm text-white/40">No evidence recorded for this step.</p>;
  }

  const consoleErrors    = evidence.consoleErrors as unknown as ConsoleError[];
  const networkFailures  = evidence.networkFailures as unknown as NetworkFailure[];
  const needsReview      = evidence.confidence < 0.4 && !step.reviewDecision;

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-white/10 bg-black/20 p-4">
      <div className="flex items-center justify-between">
        <ConfidenceBadge score={evidence.confidence} />
        {step.prUrl && <PRLink url={step.prUrl} />}
      </div>

      <div>
        <div className="text-xs uppercase tracking-wide text-white/40">Model's stated intent</div>
        <p className="mt-1 text-sm">{evidence.modelStatedIntent}</p>
      </div>

      {consoleErrors.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-white/40">Console errors</div>
          <pre className="mt-1 overflow-x-auto rounded bg-black/40 p-3 text-xs text-status-failed">
            {consoleErrors.map((e) => e.text).join("\n")}
          </pre>
        </div>
      )}

      {networkFailures.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-white/40">Network failures</div>
          <pre className="mt-1 overflow-x-auto rounded bg-black/40 p-3 text-xs text-status-failed">
            {networkFailures.map((r) => `${r.method ?? "GET"} ${r.url} -> ${r.status}`).join("\n")}
          </pre>
        </div>
      )}

      <div>
        <div className="text-xs uppercase tracking-wide text-white/40">Screenshot</div>
        <p className="mt-1 text-xs text-white/50">{evidence.screenshotPath}</p>
      </div>

      {needsReview && <ReviewForm stepId={step.id} />}
      {step.reviewDecision && (
        <p className="text-sm text-white/60">
          Review decision: <span className="font-medium">{step.reviewDecision.decision}</span>
          {step.reviewDecision.reviewerNote ? ` — ${step.reviewDecision.reviewerNote}` : ""}
        </p>
      )}
    </div>
  );
}
