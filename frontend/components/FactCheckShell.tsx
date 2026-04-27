"use client";

import { useAuth, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import {
  Loader2,
  Menu,
  MessageSquarePlus,
  MoreVertical,
  Pencil,
  ScrollText,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { deleteJob, listJobs, patchJobDisplayTitle } from "@/lib/api";
import { formatRelativeTime } from "@/lib/formatRelativeTime";
import type { JobListEntry, VerdictCode } from "@/types/factcheck";
import { cn } from "@/lib/utils";
import { FactCheckWorkspace } from "./FactCheckWorkspace";
import { ThemeToggle } from "./ThemeToggle";

function truncate(s: string, max = 72) {
  const t = s.trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

function jobTitle(row: JobListEntry): string {
  const p = row.request_payload as { question?: string; display_title?: string } | undefined;
  if (p?.display_title?.trim()) return truncate(p.display_title.trim());
  const q = p && typeof p === "object" && "question" in p ? String(p.question || "") : "";
  return truncate(q.trim() || "Fact-check");
}

function fullTitleForEdit(row: JobListEntry): string {
  const p = row.request_payload as { question?: string; display_title?: string } | undefined;
  if (p?.display_title?.trim()) return p.display_title.trim();
  const q = p?.question?.trim() || "";
  return q || "Fact-check";
}

/** Sidebar dot: fact verdict when available; pipeline state only for in-flight / errored *runs* (not claim truth). */
function verdictIndicator(row: JobListEntry): { dotClass: string; label: string } {
  const st = row.status;
  if (st === "pending" || st === "running") {
    return { dotClass: "bg-sky-500", label: "In progress" };
  }
  if (st === "failed") {
    return { dotClass: "bg-slate-500", label: "Run failed" };
  }
  if (st === "completed" && row.report_payload && typeof row.report_payload === "object") {
    const v = (row.report_payload as { verdict?: VerdictCode }).verdict;
    switch (v) {
      case "supported":
        return { dotClass: "bg-emerald-500", label: "Claim supported" };
      case "refuted":
        return { dotClass: "bg-red-500", label: "Not supported" };
      case "partial":
        return { dotClass: "bg-amber-500", label: "Partially supported" };
      case "unclear":
        return { dotClass: "bg-slate-400", label: "Unclear" };
      default:
        break;
    }
  }
  if (st === "completed") {
    return { dotClass: "bg-slate-400", label: "Completed" };
  }
  return { dotClass: "bg-slate-400", label: st };
}

export function FactCheckShell() {
  const { getToken } = useAuth();
  const [jobId, setJobId] = useState<string | null>(null);
  const [items, setItems] = useState<JobListEntry[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [menuState, setMenuState] = useState<{
    jobId: string;
    top: number;
    right: number;
  } | null>(null);
  const menuRef = useRef<HTMLUListElement | null>(null);
  const lastMenuButtonRef = useRef<HTMLButtonElement | null>(null);
  const [renameRow, setRenameRow] = useState<JobListEntry | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const refreshList = useCallback(async () => {
    try {
      const token = await getToken();
      const rows = await listJobs(token);
      const onlyFactCheck = rows.filter(
        (r) => (r.job_type ?? "fact_check") === "fact_check",
      );
      setItems(onlyFactCheck as JobListEntry[]);
      setListError(null);
    } catch (e) {
      setListError((e as Error).message);
    } finally {
      setListLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const mq = window.matchMedia("(min-width: 768px)");
    const onMq = () => {
      if (mq.matches) {
        document.body.style.overflow = prev;
        setMobileNavOpen(false);
      }
    };
    mq.addEventListener("change", onMq);
    return () => {
      mq.removeEventListener("change", onMq);
      document.body.style.overflow = prev;
    };
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!menuState) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (menuRef.current?.contains(t)) return;
      if (lastMenuButtonRef.current?.contains(t)) return;
      setMenuState(null);
    };
    const onScroll = () => setMenuState(null);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [menuState]);

  const openRename = (row: JobListEntry) => {
    setMenuState(null);
    setRenameValue(fullTitleForEdit(row));
    setRenameRow(row);
    setActionError(null);
  };

  const saveRename = async () => {
    if (!renameRow) return;
    const t = renameValue.trim();
    if (!t) {
      setActionError("Enter a title.");
      return;
    }
    setRenameBusy(true);
    setActionError(null);
    try {
      const token = await getToken();
      await patchJobDisplayTitle(token, renameRow.id, t);
      setRenameRow(null);
      await refreshList();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setRenameBusy(false);
    }
  };

  const confirmDelete = async (row: JobListEntry) => {
    setMenuState(null);
    if (!window.confirm("Delete this fact-check from your history? This cannot be undone.")) {
      return;
    }
    setActionError(null);
    try {
      const token = await getToken();
      await deleteJob(token, row.id);
      if (jobId === row.id) setJobId(null);
      await refreshList();
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

  const pickJob = (id: string) => {
    setJobId(id);
    setMobileNavOpen(false);
  };

  const startNewCheck = () => {
    setJobId(null);
    setMobileNavOpen(false);
  };

  return (
    <div className="flex h-[100dvh] max-h-[100dvh] min-h-0 flex-col overflow-hidden bg-slate-100/80 dark:bg-slate-950">
      {mobileNavOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-slate-900/45 backdrop-blur-[1px] md:hidden"
          aria-label="Close history menu"
          onClick={() => setMobileNavOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed left-0 top-0 z-40 flex h-[100dvh] max-h-[100dvh] w-[min(20rem,calc(100vw-2.5rem))] flex-col border-r border-slate-200 bg-white shadow-2xl transition-transform duration-200 ease-out dark:border-slate-800 dark:bg-slate-900 md:w-72 md:max-w-[min(20rem,100%)] md:shadow-none",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="flex items-center justify-end border-b border-slate-100 px-3 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))] md:hidden">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            aria-label="Close menu"
            onClick={() => setMobileNavOpen(false)}
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <div className="border-b border-slate-100 px-4 py-4 dark:border-slate-800">
          <div className="flex items-start justify-between gap-3">
            <Link
              href="/"
              className="min-w-0 flex-1 rounded-lg outline-none ring-blue-500/0 transition hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:hover:bg-slate-800"
              onClick={() => setMobileNavOpen(false)}
            >
              <div className="flex items-center gap-2 pr-1">
                <ScrollText className="h-6 w-6 shrink-0 text-blue-600" aria-hidden />
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Emet</p>
                  <h1 className="text-lg font-bold leading-tight text-slate-900 dark:text-slate-100">Fact-check</h1>
                </div>
              </div>
            </Link>
            <div className="shrink-0 pt-0.5" title="Account">
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: "h-8 w-8",
                  },
                }}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={startNewCheck}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 py-2.5 text-sm font-semibold text-blue-800 transition hover:bg-blue-100/80 dark:border-blue-700 dark:bg-blue-950/50 dark:text-blue-100 dark:hover:bg-blue-900/60"
          >
            <MessageSquarePlus className="h-4 w-4" aria-hidden />
            New check
          </button>
        </div>

        <div className="px-2 pb-2 pt-1">
          {listError ? (
            <p className="px-2 py-2 text-xs text-red-600">{listError}</p>
          ) : null}
          {actionError ? (
            <p className="px-2 py-1 text-xs text-red-600">{actionError}</p>
          ) : null}
        </div>

        <nav className="min-h-0 flex-1 touch-pan-y overflow-y-auto px-2 pb-2" aria-label="Past fact-checks">
          {listLoading ? (
            <div className="flex justify-center py-8 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
            </div>
          ) : items.length === 0 ? (
            <p className="px-2 text-center text-sm text-slate-500 dark:text-slate-400">
              No checks yet. Run one on the right — it will show up here.
            </p>
          ) : (
            <ul className="space-y-1">
              {items.map((row) => {
                const active = jobId === row.id;
                const { dotClass, label: dotLabel } = verdictIndicator(row);
                return (
                  <li key={row.id} className="group">
                    <div
                      className={cn(
                        "flex min-w-0 items-start gap-0 rounded-lg pr-0.5 text-sm transition",
                        active
                          ? "bg-blue-100/90 font-medium text-blue-950 ring-1 ring-blue-200 dark:bg-blue-950/50 dark:text-blue-50 dark:ring-blue-800"
                          : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800/80",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => pickJob(row.id)}
                        className="flex min-w-0 flex-1 items-start gap-2 rounded-l-lg py-2.5 pl-3 pr-1 text-left"
                      >
                        <span
                          className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dotClass)}
                          title={dotLabel}
                          aria-hidden
                        />
                        <span className="min-w-0 flex-1">
                          <span className="line-clamp-2">{jobTitle(row)}</span>
                          <span className="mt-0.5 block text-xs font-normal text-slate-500 dark:text-slate-400">
                            {formatRelativeTime(row.created_at)}
                          </span>
                        </span>
                      </button>
                      <div
                        className={cn(
                          "flex shrink-0 items-start pt-1 opacity-100 md:opacity-0 md:transition-opacity",
                          "md:group-hover:opacity-100 md:group-focus-within:opacity-100",
                        )}
                      >
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-slate-500 outline-none ring-blue-500 hover:bg-slate-200/80 hover:text-slate-800 focus-visible:ring-2 dark:text-slate-400 dark:hover:bg-slate-700/80 dark:hover:text-slate-100"
                          aria-label="Conversation options"
                          aria-haspopup="menu"
                          aria-expanded={menuState?.jobId === row.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            const b = e.currentTarget;
                            const r = b.getBoundingClientRect();
                            setMenuState((prev) => {
                              if (prev?.jobId === row.id) {
                                return null;
                              }
                              lastMenuButtonRef.current = b;
                              return {
                                jobId: row.id,
                                top: r.bottom + 4,
                                right: window.innerWidth - r.right,
                              };
                            });
                          }}
                        >
                          <MoreVertical className="h-4 w-4" aria-hidden />
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </nav>

        <div className="border-t border-slate-100 px-3 py-3 dark:border-slate-800">
          <div className="flex justify-start">
            <ThemeToggle />
          </div>
        </div>
      </aside>

      <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col md:pl-72">
        <header className="sticky top-0 z-20 flex min-h-[calc(env(safe-area-inset-top)+3.25rem)] shrink-0 items-center gap-2 border-b border-slate-200 bg-white/95 px-3 pb-2.5 pt-[calc(env(safe-area-inset-top)+0.5rem)] backdrop-blur-sm supports-[backdrop-filter]:bg-white/80 dark:border-slate-800 dark:bg-slate-900/90 md:hidden">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
            aria-label="Open history"
            aria-expanded={mobileNavOpen}
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          <Link
            href="/"
            className="min-w-0 flex-1 truncate text-center text-sm font-bold text-slate-900 dark:text-slate-100"
          >
            Emet · Fact-check
          </Link>
          <ThemeToggle />
          <button
            type="button"
            onClick={startNewCheck}
            className="shrink-0 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800 hover:bg-blue-100/80 dark:border-blue-700 dark:bg-blue-950/50 dark:text-blue-100 dark:hover:bg-blue-900/60"
          >
            New
          </button>
        </header>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <FactCheckWorkspace
            jobId={jobId}
            onJobIdChange={setJobId}
            onRunComplete={() => void refreshList()}
          />
        </main>
      </div>

      {menuState && typeof document !== "undefined"
        ? createPortal(
            (() => {
              const row = items.find((x) => x.id === menuState.jobId);
              if (!row) return null;
              return (
                <ul
                  ref={menuRef}
                  role="menu"
                  className="fixed z-[100] w-40 rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-900"
                  style={{ top: menuState.top, right: menuState.right }}
                >
                  <li role="none">
                    <button
                      type="button"
                      role="menuitem"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                      onClick={() => openRename(row)}
                    >
                      <Pencil className="h-3.5 w-3.5 opacity-70" aria-hidden />
                      Rename
                    </button>
                  </li>
                  <li role="none">
                    <button
                      type="button"
                      role="menuitem"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-red-700 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/50"
                      onClick={() => void confirmDelete(row)}
                    >
                      <Trash2 className="h-3.5 w-3.5 opacity-70" aria-hidden />
                      Delete
                    </button>
                  </li>
                </ul>
              );
            })(),
            document.body,
          )
        : null}

      {renameRow ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="presentation"
          onClick={() => {
            if (!renameBusy) {
              setRenameRow(null);
              setActionError(null);
            }
          }}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rename-dialog-title"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Escape" && !renameBusy) setRenameRow(null);
            }}
          >
            <h2 id="rename-dialog-title" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Rename conversation
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Shown in the sidebar only; your original question is unchanged.
            </p>
            <label htmlFor="rename-title-input" className="sr-only">
              Title
            </label>
            <input
              id="rename-title-input"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              className="mt-4 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-inner focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100"
              maxLength={200}
              autoFocus
            />
            {actionError && renameRow ? (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{actionError}</p>
            ) : null}
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                disabled={renameBusy}
                onClick={() => {
                  setRenameRow(null);
                  setActionError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-400"
                disabled={renameBusy}
                onClick={() => void saveRename()}
              >
                {renameBusy ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
