"use client";

import { useState, useTransition } from "react";

import { submitReviewDecision } from "@/app/actions/review";
import type { ReviewDecisionValue } from "@/lib/types";

export function ReviewForm({ stepId }: { stepId: string }) {
  const [note, setNote]         = useState("");
  const [decided, setDecided]   = useState<ReviewDecisionValue | null>(null);
  const [isPending, startTransition] = useTransition();

  function decide(decision: ReviewDecisionValue) {
    startTransition(async () => {
      await submitReviewDecision(stepId, decision, note || null);
      setDecided(decision);
    });
  }

  if (decided) {
    return <p className="text-sm text-ink-muted">Recorded: {decided}</p>;
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-status-blocked/30 bg-status-blocked/[0.06] p-4">
      <p className="text-sm font-medium text-status-blocked">
        Low confidence — this step needs human review.
      </p>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note"
        className="rounded border border-border-soft bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        rows={2}
      />
      <div className="flex gap-2">
        <button
          disabled={isPending}
          onClick={() => decide("approved")}
          className="rounded bg-status-passed/15 px-3 py-1.5 text-sm font-medium text-status-passed transition-colors hover:bg-status-passed/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-passed disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={isPending}
          onClick={() => decide("rejected")}
          className="rounded bg-status-failed/15 px-3 py-1.5 text-sm font-medium text-status-failed transition-colors hover:bg-status-failed/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-failed disabled:opacity-50"
        >
          Reject
        </button>
        <button
          disabled={isPending}
          onClick={() => decide("false_positive")}
          className="rounded bg-surface-raised px-3 py-1.5 text-sm font-medium text-ink-muted transition-colors hover:bg-border-soft hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
        >
          False positive
        </button>
      </div>
    </div>
  );
}
