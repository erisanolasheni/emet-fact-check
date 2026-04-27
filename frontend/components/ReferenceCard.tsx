"use client";

import { ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import type { SourceRef } from "@/types/factcheck";
import { faviconUrl } from "@/lib/favicon";
import { withTextFragmentDirective } from "@/lib/textFragmentUrl";
import { cn } from "@/lib/utils";

export function ReferenceCard({
  source,
  highlight,
  idRef,
}: {
  source: SourceRef;
  highlight?: boolean;
  idRef?: (el: HTMLDivElement | null) => void;
}) {
  const host = useMemo(() => {
    if (source.hostname) return source.hostname;
    try {
      return new URL(source.url).hostname;
    } catch {
      return "";
    }
  }, [source.hostname, source.url]);

  const initials = useMemo(() => {
    const p = host.split(".")[0];
    return p?.slice(0, 2).toUpperCase() || "?";
  }, [host]);

  /** `#:~:text=…` so opening the tab scrolls to the quoted passage (Chromium / Safari). */
  const openUrl = useMemo(
    () => withTextFragmentDirective(source.url, source.snippet),
    [source.url, source.snippet],
  );

  const [iconOk, setIconOk] = useState(true);

  return (
    <div
      ref={idRef}
      id={`source-${source.id}`}
      className={cn(
        "scroll-mt-24 rounded-xl border bg-white p-4 shadow-sm transition-shadow dark:bg-slate-900",
        highlight
          ? "ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-slate-950"
          : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600",
      )}
    >
      <div className="flex gap-3">
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
          {iconOk ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={faviconUrl(host)}
              alt=""
              className="h-full w-full object-contain p-1"
              onError={() => setIconOk(false)}
            />
          ) : (
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">{initials}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900 dark:text-slate-100" title={source.title}>
            {source.title}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{host}</p>
          {source.snippet ? (
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Open page and jump to this passage in the browser"
              className="mt-2 block line-clamp-3 text-left text-sm leading-relaxed text-slate-600 underline decoration-slate-300 decoration-dotted underline-offset-2 transition hover:text-blue-700 hover:decoration-blue-500/80 dark:text-slate-400 dark:decoration-slate-600 dark:hover:text-blue-300"
            >
              {source.snippet}
            </a>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {source.tier}
            </span>
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Opens in a new tab and scrolls to the quoted text when supported"
              className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
            >
              Open source
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}