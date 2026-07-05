"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { RunLog } from "@prisma/client";

import { formatTime } from "@/lib/format";

function summarize(log: RunLog): string {
  const payload = log.payload as Record<string, unknown>;
  const short = JSON.stringify(payload).slice(0, 120);
  return `${log.source}: ${log.eventType} — ${short}`;
}

export function ActivityFeed({ logs, runId }: { logs: RunLog[]; runId: string }) {
  const router = useRouter();

  useEffect(() => {
    const interval = setInterval(() => router.refresh(), 4000);
    return () => clearInterval(interval);
  }, [router, runId]);

  if (logs.length === 0) {
    return <p className="text-sm text-white/40">No activity recorded yet.</p>;
  }

  return (
    <div className="flex max-h-80 flex-col gap-1 overflow-y-auto rounded-lg border border-white/10 bg-black/20 p-3 font-mono text-xs">
      {logs.map((log) => (
        <div key={log.id} className="text-white/70">
          <span className="text-white/30">{formatTime(new Date(log.createdAt))}</span>{" "}
          {summarize(log)}
        </div>
      ))}
    </div>
  );
}
