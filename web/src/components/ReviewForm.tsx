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
    return <p className="text-sm text-white/60">Recorded: {decided}</p>;
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-white/10 bg-white/5 p-4">
      <p className="text-sm font-medium text-status-blocked">
        Low confidence — this step needs human review.
      </p>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note"
        className="rounded border border-white/10 bg-black/20 px-3 py-2 text-sm"
        rows={2}
      />
      <div className="flex gap-2">
        <button
          disabled={isPending}
          onClick={() => decide("approved")}
          className="rounded bg-status-passed/20 px-3 py-1.5 text-sm font-medium text-status-passed hover:bg-status-passed/30 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          disabled={isPending}
          onClick={() => decide("rejected")}
          className="rounded bg-status-failed/20 px-3 py-1.5 text-sm font-medium text-status-failed hover:bg-status-failed/30 disabled:opacity-50"
        >
          Reject
        </button>
        <button
          disabled={isPending}
          onClick={() => decide("false_positive")}
          className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white/70 hover:bg-white/20 disabled:opacity-50"
        >
          False positive
        </button>
      </div>
    </div>
  );
}
