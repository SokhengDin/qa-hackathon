"use client";

import { useEffect, useRef } from "react";

import type { RunLog } from "@prisma/client";

import { formatTime } from "@/lib/format";

const CATEGORY_COLOR: Record<string, string> = {
  prompt          : "text-status-fixed",
  screenshot      : "text-ink-faint",
  function_call   : "text-ink",
  executed_action : "text-status-passed",
  safety_response : "text-status-blocked",
  status_change   : "text-ink-muted",
  tool_call       : "text-ink-muted",
  model_output    : "text-ink",
};

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

export function ActivityFeed({ logs }: { logs: RunLog[]; runId: string }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [logs.length]);

  if (logs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-border-soft bg-surface">
        <p className="text-sm text-ink-faint">No activity recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-1 overflow-y-auto rounded-lg border border-border-soft bg-surface p-3 font-mono text-xs">
      {logs.map((log) => {
        const payload = log.payload as Record<string, unknown>;
        const category = (payload.category as string) ?? log.eventType;
        const colorClass = CATEGORY_COLOR[category] ?? "text-ink-muted";

        return (
          <div key={log.id} className="flex gap-2 leading-relaxed">
            <span className="shrink-0 text-ink-faint">{formatTime(new Date(log.createdAt))}</span>
            <span className="shrink-0 text-ink-faint">[{log.source}]</span>
            <span className={`shrink-0 uppercase tracking-wide ${colorClass}`}>{category}</span>
            <span className={`${colorClass} break-all`}>{summarize(log)}</span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
