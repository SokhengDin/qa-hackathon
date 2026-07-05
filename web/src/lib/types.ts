import type { Environment, Evidence, ReviewDecision, Run, RunLog, Step } from "@prisma/client";

export type StepStatus = "pending" | "passed" | "failed" | "blocked" | "fixed_and_verified";
export type RunStatus = "queued" | "running" | "completed" | "failed";
export type ReviewDecisionValue = "approved" | "rejected" | "false_positive";

export type ConsoleError = {
  level : string;
  text  : string;
  url?  : string;
};

export type NetworkFailure = {
  url    : string;
  status : number;
  method?: string;
};

export type StepWithEvidence = Step & {
  evidence      : Evidence | null;
  reviewDecision: ReviewDecision | null;
};

export type RunWithSteps = Run & {
  steps: StepWithEvidence[];
  logs : RunLog[];
};

export type RunListItem = Run & {
  steps: Pick<Step, "status">[];
};

export type { Environment };
