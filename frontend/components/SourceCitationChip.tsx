"use client";

import { ExternalLink, Link2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { SourceRef } from "@/types/factcheck";
import { faviconUrl } from "@/lib/favicon";
import { withTextFragmentDirective } from "@/lib/textFragmentUrl";
import { cn } from "@/lib/utils";

function hostFromSource(s: SourceRef): string {
  if (s.hostname) return s.hostname;
  try {
    return new URL(s.url).hostname;
  } catch {
    return "";
  }
}

export function SourceCitationChip({
  sourceId,
  sources,
  onActivate,
}: {
  sourceId: string;
  sources: SourceRef[];
  onActivate: (sourceId: string) => void;
}) {
  const source = useMemo(() => sources.find((x) => x.id === sourceId), [sources, sourceId]);
  const [iconOk, setIconOk] = useState(true);

  const openWithExcerpt = useMemo(
    () => (source?.url ? withTextFragmentDirective(source.url, source.snippet) : ""),
    [source?.url, source?.snippet],
  );

  const host = source ? hostFromSource(source) : "";
  const label = (source?.title || "").trim() || host || sourceId;
  const initials = (() => {
    const p = host.split(".")[0] || sourceId;
    return p.replace(/[^a-z0-9]/gi, "").slice(0, 2).toUpperCase() || "?";
  })();

  return (
    <span
      className={cn(
        "inline-flex max-w-full min-w-0 items-center gap-0.5 rounded-full border py-1 pl-1 pr-1 shadow-sm transition",
        source
          ? "border-slate-200/90 bg-white text-slate-900 dark:border-slate-600 dark:bg-slate-800/90 dark:text-slate-100"
          : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-100",
      )}
    >
      <button
        type="button"
        onClick={() => onActivate(sourceId)}
        className={cn(
          "inline-flex min-w-0 flex-1 items-center gap-2 rounded-full py-0 pl-1 pr-2 text-left transition",
          source
            ? "hover:border-blue-300 hover:bg-blue-50/60 dark:hover:border-blue-500 dark:hover:bg-blue-950/40"
            : "hover:bg-amber-100/80 dark:hover:bg-amber-900/40",
        )}
        title={label + (source?.url ? ` — ${source.url}` : "")}
      >
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/80 dark:bg-slate-700 dark:ring-slate-600"
          aria-hidden
        >
          {source && host && iconOk ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={faviconUrl(host)}
              alt=""
              className="h-full w-full object-contain p-0.5"
              onError={() => setIconOk(false)}
            />
          ) : source && host && !iconOk ? (
            <span className="text-[10px] font-bold text-slate-600">{initials}</span>
          ) : (
            <Link2 className="h-3.5 w-3.5 text-slate-500" />
          )}
        </span>
        <span className="min-w-0 truncate text-xs font-medium leading-tight">{label}</span>
      </button>
      {source?.url && openWithExcerpt ? (
        <a
          href={openWithExcerpt}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded-full p-1.5 text-slate-500 transition hover:bg-slate-200/80 hover:text-blue-600 dark:hover:bg-slate-600 dark:hover:text-blue-300"
          title="Open source in new tab and jump to quoted passage"
          aria-label="Open source and scroll to quoted text"
          onClick={(e) => e.stopPropagation()}
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden />
        </a>
      ) : null}
    </span>
  );
}
