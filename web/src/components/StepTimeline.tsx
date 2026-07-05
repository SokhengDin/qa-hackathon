"use client";

import { useState } from "react";

import { EvidencePanel } from "@/components/EvidencePanel";
import { StatusBadge } from "@/components/StatusBadge";
import { formatTime } from "@/lib/format";
import type { RunLog } from "@prisma/client";
import type { RunWithSteps } from "@/lib/types";

const CATEGORY_COLOR: Record<string, string> = {
  prompt          : "text-status-fixed",
  screenshot      : "text-ink-faint",
  function_call   : "text-ink",
  executed_action : "text-status-passed",
  safety_response : "text-status-blocked",
  status_change   : "text-ink-muted",
  tool_call       : "text-ink-muted",
  model_output    : "text-ink",
  mcp_tool_call   : "text-accent",
};

function colorForLog(log: RunLog): string {
  const payload = log.payload as Record<string, unknown>;
  const category = (payload.category as string) ?? log.eventType;

  if (category === "mcp_tool_call") {
    if (payload.isError) return "text-status-failed";
    if (payload.hit)     return "text-status-blocked";
    return "text-status-passed";
  }

  return CATEGORY_COLOR[category] ?? "text-ink-muted";
}

function summarize(log: RunLog): string {
  const payload = log.payload as Record<string, unknown>;
  const category = (payload.category as string) ?? log.eventType;

  switch (category) {
    case "prompt":
      return `prompt: ${payload.instruction ?? ""}`;
    case "screenshot":
      return `screenshot @ turn ${payload.turn ?? "?"} — ${payload.url ?? ""}`;
    case "function_call": {
      const args = payload.args as Record<string, unknown> | undefined;
      const intent = args?.intent ? ` (${args.intent})` : "";
      return `calls ${payload.name}${intent}`;
    }
    case "executed_action": {
      const result = payload.result as Record<string, unknown> | undefined;
      const err = result?.error ? ` — error: ${result.error}` : "";
      return `executed ${payload.name}${err}`;
    }
    case "safety_response":
      return `safety: ${payload.decision} — ${payload.explanation ?? ""}`;
    case "mcp_tool_call": {
      const text = (payload.text as string) ?? "";
      const preview = text.trim().length > 0 ? text.trim().split("\n")[0] : "(empty response)";
      if (payload.isError) return `chrome-devtools: ${payload.name} errored — ${preview}`;
      if (payload.hit)     return `chrome-devtools: ${payload.name} found an issue — ${preview}`;
      return `chrome-devtools: ${payload.name} clean — ${preview}`;
    }
    case "status_change": {
      const rest = Object.entries(payload)
        .filter(([k]) => k !== "category")
        .map(([k, v]) => `${k}=${v}`)
        .join(" ");
      return `status change — ${rest}`;
    }
    default: {
      const summary = (payload.summary as string) ?? JSON.stringify(payload);
      return summary.length > 160 ? `${summary.slice(0, 160)}…` : summary;
    }
  }
}

function StepLog({ logs }: { logs: RunLog[] }) {
  if (logs.length === 0) {
    return (
      <p className="rounded-lg border border-border-soft bg-bg/40 p-3 text-sm text-ink-faint">
        No activity recorded yet for this step.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border-soft bg-bg/40 p-3 font-mono text-xs">
      {logs.map((log) => {
        const colorClass = colorForLog(log);
        const payload = log.payload as Record<string, unknown>;
        const category = (payload.category as string) ?? log.eventType;

        return (
          <div key={log.id} className="flex gap-2 leading-relaxed">
            <span className="shrink-0 text-ink-faint">{formatTime(new Date(log.createdAt))}</span>
            <span className="shrink-0 text-ink-faint">[{log.source}]</span>
            <span className={`shrink-0 uppercase tracking-wide ${colorClass}`}>{category}</span>
            <span className={`${colorClass} break-all`}>{summarize(log)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function StepTimeline({ run }: { run: RunWithSteps }) {
  const firstPendingIndex = run.steps.findIndex((s) => s.status === "pending");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-3">
      {run.steps.map((step, i) => {
        const isRunning = run.status === "running" && i === firstPendingIndex;
        const isExpanded = expandedId === step.id;
        const stepLogs = run.logs.filter((log) => log.stepId === step.stepId);

        return (
          <div
            key={step.id}
            className={`flex flex-col gap-3 rounded-lg border p-4 transition-colors ${
              isRunning
                ? "border-accent/50 bg-accent-soft"
                : "border-border-soft bg-surface"
            }`}
          >
            <button
              type="button"
              onClick={() => setExpandedId(isExpanded ? null : step.id)}
              className="flex w-full items-start justify-between gap-3 text-left"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 font-mono text-sm font-medium">
                  <svg
                    className={`h-3.5 w-3.5 shrink-0 text-ink-faint transition-transform ${isExpanded ? "rotate-90" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  {step.stepId}
                </div>
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
            </button>

            {step.dependsOn.length > 0 && (
              <div className="font-mono text-xs text-ink-faint">
                depends on {step.dependsOn.join(", ")}
              </div>
            )}

            {isExpanded && (
              <div className="flex flex-col gap-3">
                <StepLog logs={stepLogs} />
                {(step.status === "failed" ||
                  step.status === "blocked" ||
                  step.status === "fixed_and_verified") && <EvidencePanel step={step} />}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
