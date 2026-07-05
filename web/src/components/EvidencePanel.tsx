import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { PRLink } from "@/components/PRLink";
import { ReviewForm } from "@/components/ReviewForm";
import type { ConsoleError, NetworkFailure, StepWithEvidence } from "@/lib/types";

export function EvidencePanel({ step }: { step: StepWithEvidence }) {
  const evidence = step.evidence;

  if (!evidence) {
    return <p className="text-sm text-ink-faint">No evidence recorded for this step.</p>;
  }

  const consoleErrors    = evidence.consoleErrors as unknown as ConsoleError[];
  const networkFailures  = evidence.networkFailures as unknown as NetworkFailure[];
  const needsReview      = evidence.confidence < 0.4 && !step.reviewDecision;

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border-soft bg-bg/40 p-4">
      <div className="flex items-center justify-between">
        <ConfidenceBadge score={evidence.confidence} />
        {step.prUrl && <PRLink url={step.prUrl} />}
      </div>

      <div>
        <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">
          Model&rsquo;s stated intent
        </div>
        <p className="mt-1 text-sm">{evidence.modelStatedIntent}</p>
      </div>

      {consoleErrors.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">
            Console errors
          </div>
          <pre className="mt-1 overflow-x-auto rounded border border-border-soft bg-surface p-3 font-mono text-xs text-status-failed">
            {consoleErrors.map((e) => e.text).join("\n")}
          </pre>
        </div>
      )}

      {networkFailures.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">
            Network failures
          </div>
          <pre className="mt-1 overflow-x-auto rounded border border-border-soft bg-surface p-3 font-mono text-xs text-status-failed">
            {networkFailures.map((r) => `${r.method ?? "GET"} ${r.url} -> ${r.status}`).join("\n")}
          </pre>
        </div>
      )}

      <div>
        <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">Screenshot</div>
        <p className="mt-1 font-mono text-xs text-ink-muted">{evidence.screenshotPath}</p>
      </div>

      {needsReview && <ReviewForm stepId={step.id} />}
      {step.reviewDecision && (
        <p className="text-sm text-ink-muted">
          Review decision: <span className="font-medium text-ink">{step.reviewDecision.decision}</span>
          {step.reviewDecision.reviewerNote ? ` — ${step.reviewDecision.reviewerNote}` : ""}
        </p>
      )}
    </div>
  );
}
