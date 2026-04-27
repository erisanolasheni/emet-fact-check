"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import type { JobProgress } from "@/types/factcheck";
import { cn } from "@/lib/utils";

export function ProgressPanel({ progress }: { progress: JobProgress | null | undefined }) {
  if (!progress) {
    return (
      <div className="animate-pulse rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="h-4 w-1/3 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="mt-4 h-3 w-full rounded bg-slate-100 dark:bg-slate-800" />
      </div>
    );
  }

  const pct = progress.percent ?? 0;
  const steps = progress.steps || [];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 transition-colors duration-200 dark:text-blue-400">
            {progress.phase}
          </p>
          <p className="mt-1 text-sm font-medium text-slate-900 transition-[color,opacity] duration-200 dark:text-slate-100">
            {progress.message}
          </p>
          {progress.updated_at ? (
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              Updated {new Date(progress.updated_at).toLocaleTimeString()}
            </p>
          ) : null}
        </div>
        <span className="text-2xl font-semibold tabular-nums text-slate-700 transition-colors duration-300 dark:text-slate-200">
          {pct}%
        </span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className="h-full rounded-full bg-blue-600 motion-safe:transition-[width] motion-safe:duration-700 motion-safe:ease-out"
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>
      {steps.length > 0 ? (
        <ul className="mt-6 space-y-3">
          {steps.map((s) => (
            <li key={s.id} className="flex items-center gap-3 text-sm">
              {s.status === "done" ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" aria-hidden />
              ) : s.status === "active" ? (
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-blue-600" aria-hidden />
              ) : (
                <Circle className="h-5 w-5 shrink-0 text-slate-300 dark:text-slate-600" aria-hidden />
              )}
              <span
                className={cn(
                  s.status === "active" && "font-medium text-slate-900 dark:text-slate-100",
                  s.status === "pending" && "text-slate-400 dark:text-slate-500",
                  s.status === "done" && "text-slate-600 dark:text-slate-400",
                )}
              >
                {s.label}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
