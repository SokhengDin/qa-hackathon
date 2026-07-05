import type { StepStatus } from "@/lib/types";

const LABEL: Record<StepStatus, string> = {
  pending            : "Pending",
  passed             : "Passed",
  failed             : "Failed",
  blocked            : "Blocked",
  fixed_and_verified : "Fixed & verified",
};

const DOT_CLASS: Record<StepStatus, string> = {
  pending            : "bg-ink-faint",
  passed             : "bg-status-passed",
  failed             : "bg-status-failed",
  blocked            : "bg-status-blocked",
  fixed_and_verified : "bg-status-fixed",
};

const TEXT_CLASS: Record<StepStatus, string> = {
  pending            : "text-ink-muted",
  passed             : "text-status-passed",
  failed             : "text-status-failed",
  blocked            : "text-status-blocked",
  fixed_and_verified : "text-status-fixed",
};

export function StatusBadge({ status }: { status: string }) {
  const key = (status in LABEL ? status : "pending") as StepStatus;
  return (
    <span className={`inline-flex items-center gap-2 text-sm font-medium ${TEXT_CLASS[key]}`}>
      <span className={`h-2 w-2 rounded-full ${DOT_CLASS[key]}`} />
      {LABEL[key]}
    </span>
  );
}
