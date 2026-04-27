"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, CheckCircle, HelpCircle, Loader2, Mic, Square, Volume2, VolumeX, XCircle } from "lucide-react";
import { getJob, postFactCheck } from "@/lib/api";
import { useJobStream } from "@/lib/useJobStream";
import type {
  FactCheckResult,
  FactItem,
  FactStatus,
  VerdictCode,
} from "@/types/factcheck";
import { cn } from "@/lib/utils";
import { ProgressPanel } from "./ProgressPanel";
import { ReferenceCard } from "./ReferenceCard";
import { SourceCitationChip } from "./SourceCitationChip";

const CLAIM_MIN = 3;
const CLAIM_MAX = 8000;

type SpeechRecognitionEvent = {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    0: { transcript: string };
  }>;
};

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type BrowserWindow = Window & {
  webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
  SpeechRecognition?: new () => BrowserSpeechRecognition;
};

function mergeRecognitionChunks(results: ArrayLike<{ 0: { transcript: string } }>): string {
  const pieces: string[] = [];
  for (let i = 0; i < results.length; i++) {
    const raw = results[i][0]?.transcript ?? "";
    const text = raw.replace(/\s+/g, " ").trim();
    if (!text) continue;
    const prev = pieces[pieces.length - 1];
    if (!prev) {
      pieces.push(text);
      continue;
    }
    // Some engines emit cumulative prefixes across slots; keep only the latest expanded phrase.
    if (text.startsWith(prev)) {
      pieces[pieces.length - 1] = text;
      continue;
    }
    if (prev.startsWith(text)) {
      continue;
    }
    pieces.push(text);
  }
  return pieces.join(" ").replace(/\s+/g, " ").trim();
}

function factVerdictStyles(status: FactStatus, role: "user_claim" | "evidence" | undefined) {
  /* "evidence" = reported in sources; neutral so it is not read as "proves your headline" */
  if (role === "evidence") {
    return "border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200";
  }
  switch (status) {
    case "supported":
      return "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-100";
    case "partially_supported":
      return "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100";
    case "contradicted":
      return "border-red-200 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-100";
    default:
      return "border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200";
  }
}

function verdictBannerStyles(v: VerdictCode) {
  switch (v) {
    case "supported":
      return "border-emerald-200 bg-emerald-50/90 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100";
    case "refuted":
      return "border-red-200 bg-red-50/90 text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100";
    case "partial":
      return "border-amber-200 bg-amber-50/90 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100";
    default:
      return "border-slate-200 bg-slate-50 text-slate-900 dark:border-slate-700 dark:bg-slate-900/80 dark:text-slate-100";
  }
}

function verdictIcon(v: VerdictCode) {
  const cl = "h-8 w-8 shrink-0";
  switch (v) {
    case "supported":
      return <CheckCircle className={cl + " text-emerald-600 dark:text-emerald-400"} aria-hidden />;
    case "refuted":
      return <XCircle className={cl + " text-red-600 dark:text-red-400"} aria-hidden />;
    case "partial":
      return <AlertCircle className={cl + " text-amber-600 dark:text-amber-400"} aria-hidden />;
    default:
      return <HelpCircle className={cl + " text-slate-500 dark:text-slate-400"} aria-hidden />;
  }
}

function confidenceRingClass(v: VerdictCode | undefined): string {
  switch (v) {
    case "refuted":
      return "text-red-600";
    case "supported":
      return "text-emerald-600";
    case "partial":
      return "text-amber-600";
    default:
      return "text-blue-600";
  }
}

function sortFactsForDisplay(facts: FactItem[]): FactItem[] {
  return [...facts].sort((a, b) => {
    if (a.role === "user_claim" && b.role !== "user_claim") return -1;
    if (b.role === "user_claim" && a.role !== "user_claim") return 1;
    return 0;
  });
}

export type FactCheckWorkspaceProps = {
  /** Active fact-check job; `null` = compose a new one. */
  jobId: string | null;
  onJobIdChange: (id: string | null) => void;
  /** Called after a new job is enqueued (for sidebar refresh). */
  onRunComplete?: (jobId: string) => void;
};

export function FactCheckWorkspace({ jobId, onJobIdChange, onRunComplete }: FactCheckWorkspaceProps) {
  const { getToken } = useAuth();
  /** Composer draft; cleared after a successful enqueue. */
  const [question, setQuestion] = useState("");
  /** Claim shown in the transcript bubble — from submit or loaded job, not the live draft. */
  const [claimText, setClaimText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { snapshot, error: streamError } = useJobStream(jobId);
  const [pollPayload, setPollPayload] = useState<FactCheckResult | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const sourceRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  /** Text in the composer when a dictation session started (avoid duplicate appends). */
  const voiceBaseRef = useRef("");
  /** Final transcript chunks for the current `start()`…`onend` session (resultIndex + isFinal only). */
  const voiceSessionFinalRef = useRef("");
  const questionRef = useRef(question);
  questionRef.current = question;

  const onTranscriptScroll = useCallback(() => {
    const el = transcriptRef.current;
    if (!el) return;
    const fromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = fromBottom < 140;
  }, []);

  const mergedReport = useMemo(() => {
    const raw = snapshot?.report_payload || pollPayload;
    if (!raw || typeof raw !== "object") return null;
    return raw as FactCheckResult;
  }, [snapshot?.report_payload, pollPayload]);

  const hasComposerText = question.trim().length > 0;

  const progress = snapshot?.progress ?? undefined;

  /** New chat and opened history both land at the top for easier reading. */
  useLayoutEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;
    stickToBottomRef.current = !jobId;
    el.scrollTo({ top: 0, behavior: "auto" });
  }, [jobId]);

  /** Stream updates: follow the thread when the user is already near the bottom. */
  useEffect(() => {
    if (!jobId) return;
    const el = transcriptRef.current;
    if (!el) return;
    if (!stickToBottomRef.current) return;
    const id = requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [jobId, mergedReport, snapshot?.status, snapshot?.error_message]);

  /** When switching jobs or starting new, load question + any stored report. */
  useEffect(() => {
    let cancelled = false;
    if (!jobId) {
      setPollPayload(null);
      setQuestion("");
      setClaimText("");
      return;
    }
    setQuestion("");
    (async () => {
      try {
        const token = await getToken();
        const j = (await getJob(token, jobId)) as {
          request_payload?: { question?: string };
          report_payload?: FactCheckResult | null;
        };
        if (cancelled) return;
        const q = j.request_payload?.question;
        if (typeof q === "string") setClaimText(q);
        if (j.report_payload && typeof j.report_payload === "object") {
          setPollPayload(j.report_payload as FactCheckResult);
        }
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId, getToken]);

  /** Lightweight poll backup (SSE auth / proxies). */
  useEffect(() => {
    if (!jobId) return;
    if (snapshot?.status === "completed" || snapshot?.status === "failed") return;

    const tick = async () => {
      try {
        const token = await getToken();
        const j = await getJob(token, jobId);
        if (j?.report_payload) setPollPayload(j.report_payload as FactCheckResult);
      } catch {
        /* ignore */
      }
    };
    const id = setInterval(tick, 3000);
    void tick();
    return () => clearInterval(id);
  }, [jobId, snapshot?.status, getToken]);

  const scrollToSource = useCallback((sid: string) => {
    setHighlightId(sid);
    sourceRefs.current[sid]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    window.setTimeout(() => setHighlightId(null), 2000);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  const speakText = useCallback(
    (text: string) => {
      if (typeof window === "undefined" || !window.speechSynthesis) return;
      const clean = text.trim();
      if (!clean) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.rate = 1;
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      setIsSpeaking(true);
      window.speechSynthesis.speak(utterance);
    },
    [],
  );

  const stopListening = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const browserWindow = window as BrowserWindow;
    const Recognition = browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setFormError("Voice input is not supported in this browser.");
      return;
    }
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    const recog = new Recognition();
    recognitionRef.current = recog;
    voiceBaseRef.current = questionRef.current;
    voiceSessionFinalRef.current = "";
    recog.lang = "en-US";
    recog.interimResults = true;
    recog.continuous = false;
    recog.maxAlternatives = 1;
    // Stream live interim text, but normalize/dedupe cumulative prefix artifacts.
    recog.onresult = (event: SpeechRecognitionEvent) => {
      const normalizedLatest = mergeRecognitionChunks(event.results);
      if (!normalizedLatest) return;
      voiceSessionFinalRef.current = normalizedLatest;
      const base = voiceBaseRef.current.trimEnd();
      const session = voiceSessionFinalRef.current.trim();
      const merged = [base, session].filter(Boolean).join(" ").replace(/\s+/g, " ");
      setQuestion(merged.slice(0, CLAIM_MAX));
      setFormError(null);
    };
    recog.onerror = (event) => {
      if (event.error === "aborted" || event.error === "no-speech") {
        return;
      }
      setFormError(`Voice input failed${event.error ? ` (${event.error})` : ""}.`);
      setIsListening(false);
    };
    recog.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };
    setIsListening(true);
    recog.start();
  }, []);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    stopListening();
    setFormError(null);
    const text = question.trim();
    if (text.length < CLAIM_MIN) {
      setFormError(`Enter at least ${CLAIM_MIN} characters.`);
      return;
    }
    if (text.length > CLAIM_MAX) {
      setFormError(`Keep your claim under ${CLAIM_MAX.toLocaleString()} characters.`);
      return;
    }
    setSubmitting(true);
    setPollPayload(null);
    try {
      const token = await getToken();
      const res = await postFactCheck(token, text);
      setClaimText(text);
      setQuestion("");
      onJobIdChange(res.job_id);
      onRunComplete?.(res.job_id);
    } catch (err: unknown) {
      setFormError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-slate-100/80 dark:bg-slate-950">
      <div
        ref={transcriptRef}
        onScroll={onTranscriptScroll}
        className="min-h-0 flex-1 touch-pan-y overflow-y-auto scroll-smooth"
      >
        <div className="mx-auto max-w-4xl px-3 pb-4 pt-4 sm:px-4 sm:pb-6 sm:pt-5 md:px-6 md:pt-6">
          {jobId ? (
            <div className="space-y-8">
              {claimText.trim() ? (
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-sm leading-relaxed text-white shadow-sm dark:bg-blue-500">
                    {claimText.trim()}
                  </div>
                </div>
              ) : null}

              <ProgressPanel key={jobId} progress={progress} />

              {snapshot?.status === "failed" ? (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
                  {snapshot.error_message || "Job failed"}
                </div>
              ) : null}

              {mergedReport ? (
                <section className="space-y-8">
                  {mergedReport.verdict_text?.trim() ? (
                    <div
                      className={cn(
                        "flex gap-4 rounded-2xl border p-4 shadow-sm sm:p-6",
                        verdictBannerStyles((mergedReport.verdict ?? "unclear") as VerdictCode),
                      )}
                    >
                      {verdictIcon((mergedReport.verdict ?? "unclear") as VerdictCode)}
                      <div className="min-w-0">
                        <h2 className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">Verdict</h2>
                        <p className="mt-1 text-lg font-semibold leading-snug text-slate-900 dark:text-slate-100">
                          {mergedReport.verdict_text.trim()}
                        </p>
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
                    <div className="flex items-start justify-between gap-3">
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Summary</h2>
                      <button
                        type="button"
                        onClick={() => {
                          if (isSpeaking) {
                            stopSpeaking();
                          } else {
                            speakText(mergedReport.summary);
                          }
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                      >
                        {isSpeaking ? <VolumeX className="h-3.5 w-3.5" aria-hidden /> : <Volume2 className="h-3.5 w-3.5" aria-hidden />}
                        {isSpeaking ? "Stop" : "Listen"}
                      </button>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                      {mergedReport.summary}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-blue-100 bg-blue-50/80 p-4 dark:border-blue-900/60 dark:bg-blue-950/30 sm:gap-6 sm:p-6">
                    <div
                      className="relative h-24 w-24 shrink-0"
                      role="img"
                      aria-label={`Support for your claim: ${mergedReport.confidence_percent} percent`}
                    >
                      <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
                        <path
                          className="text-slate-200 dark:text-slate-700"
                          stroke="currentColor"
                          strokeWidth="3"
                          fill="none"
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        />
                        <path
                          className={cn(confidenceRingClass(mergedReport.verdict as VerdictCode | undefined))}
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeDasharray={`${mergedReport.confidence_percent}, 100`}
                          strokeLinecap="round"
                          fill="none"
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-slate-900 dark:text-slate-100">
                        {mergedReport.confidence_percent}%
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Support for your claim</p>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                        {mergedReport.confidence_rationale}
                      </p>
                      <details className="mt-2 text-xs text-slate-500 dark:text-slate-500">
                        <summary className="cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-300">
                          Limitations
                        </summary>
                        <ul className="mt-2 list-inside list-disc space-y-1">
                          {mergedReport.limitations.map((l, i) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  </div>

                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Claims &amp; source checks</h2>
                    <ul className="mt-4 space-y-4">
                      {sortFactsForDisplay(mergedReport.facts).map((f, idx) => (
                        <li
                          key={idx}
                          className={cn(
                            "rounded-xl border p-4",
                            factVerdictStyles(
                              f.status,
                              f.role as "user_claim" | "evidence" | undefined,
                            ),
                          )}
                        >
                          {f.role === "evidence" ? (
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                              From sources
                            </p>
                          ) : f.role === "user_claim" ? (
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                              Your claim
                            </p>
                          ) : null}
                          <p className="mt-1 text-sm font-medium leading-relaxed">{f.claim}</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {f.source_ids.map((sid) => (
                              <SourceCitationChip
                                key={sid}
                                sourceId={sid}
                                sources={mergedReport.sources}
                                onActivate={scrollToSource}
                              />
                            ))}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">References</h2>
                    <div className="mt-4 grid gap-4 md:grid-cols-1">
                      {mergedReport.sources.map((s) => (
                        <ReferenceCard
                          key={s.id}
                          source={s}
                          highlight={highlightId === s.id}
                          idRef={(el) => {
                            sourceRefs.current[s.id] = el;
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </section>
              ) : snapshot?.status === "completed" && !mergedReport ? (
                <p className="text-sm text-slate-600 dark:text-slate-400">Loading results…</p>
              ) : null}
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-2 py-8 text-center sm:min-h-[min(60dvh,32rem)] sm:py-12">
              <h2 className="text-balance text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-xl">
                New fact-check
              </h2>
              <p className="mt-2 max-w-md text-balance text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Add a question or claim in the field below. We search open sources, extract evidence, and
                return a structured verdict with references.
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="relative z-20 shrink-0 border-t border-slate-200/60 bg-slate-100/80 dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto max-w-4xl px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-4 sm:pt-3.5 md:px-6">
          <form onSubmit={onSubmit} className="space-y-2">
            <label htmlFor="q" className="text-sm font-medium text-slate-800 dark:text-slate-200">
              Your question or claim
            </label>
            <textarea
              id="q"
              required
              rows={3}
              maxLength={CLAIM_MAX}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onFocus={() => {
                stickToBottomRef.current = true;
              }}
              placeholder="e.g. Does the WHO recommend a specific vaccine schedule for infants in 2025?"
              className="w-full max-h-48 resize-y rounded-xl border border-slate-200/90 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/25 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 sm:px-4 sm:py-3"
            />
            {formError ? <p className="text-sm text-red-600 dark:text-red-400">{formError}</p> : null}
            {streamError ? (
              <p className="text-xs text-amber-800 dark:text-amber-200/90">
                Live stream unavailable ({streamError}). Using periodic refresh.
              </p>
            ) : null}
            <div className="flex min-h-[2.75rem] justify-end pt-0.5">
              {hasComposerText ? (
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex h-11 w-full min-w-0 items-center justify-center gap-2 rounded-full bg-blue-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60 dark:bg-blue-500 dark:hover:bg-blue-400 sm:w-auto"
                >
                  {submitting ? <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden /> : null}
                  Run deep check
                </button>
              ) : (
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    if (isListening) {
                      stopListening();
                    } else {
                      void startListening();
                    }
                  }}
                  className={cn(
                    "inline-flex h-11 w-full min-w-[2.75rem] shrink-0 items-center justify-center rounded-full px-5 text-sm font-semibold shadow-sm transition disabled:opacity-60 sm:w-auto",
                    isListening
                      ? "bg-red-600 text-white hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-400"
                      : "bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-400",
                  )}
                  aria-label={isListening ? "Stop listening" : "Dictate question or claim"}
                >
                  {isListening ? <Square className="h-4 w-4 shrink-0" aria-hidden /> : <Mic className="h-4 w-4 shrink-0" aria-hidden />}
                </button>
              )}
            </div>
          </form>
          <p className="mt-3 text-balance text-center text-[11px] leading-relaxed text-slate-500 dark:text-slate-500 sm:text-left sm:text-xs">
            Verdicts and scores are model-assisted. Not legal or medical advice.
          </p>
        </div>
      </div>
    </div>
  );
}
