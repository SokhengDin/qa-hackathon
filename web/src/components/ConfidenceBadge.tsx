type Confidence = "high" | "medium" | "low";

function bucket(score: number): Confidence {
  if (score >= 0.8) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

const LABEL: Record<Confidence, string> = {
  high  : "High confidence — auto-fixed",
  medium: "Medium confidence — partial evidence",
  low   : "Low confidence — needs human review",
};

const DOT_CLASS: Record<Confidence, string> = {
  high  : "bg-status-passed",
  medium: "bg-status-blocked",
  low   : "bg-status-failed",
};

const TEXT_CLASS: Record<Confidence, string> = {
  high  : "text-status-passed",
  medium: "text-status-blocked",
  low   : "text-status-failed",
};

export function ConfidenceBadge({ score }: { score: number }) {
  const level = bucket(score);
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5
                  px-3 py-1 text-sm font-medium ${TEXT_CLASS[level]}`}
    >
      <span className={`h-2 w-2 rounded-full ${DOT_CLASS[level]}`} />
      {LABEL[level]}
    </span>
  );
}
