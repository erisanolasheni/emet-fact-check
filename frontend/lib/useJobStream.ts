"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import type { FactCheckResult, JobProgress } from "@/types/factcheck";

export interface StreamSnapshot {
  status: string;
  progress: JobProgress | null;
  report_payload: FactCheckResult | null;
  error_message: string | null;
}

/** fetch() + ReadableStream SSE parser — supports Authorization header (unlike EventSource). */
export function useJobStream(jobId: string | null) {
  const { getToken } = useAuth();
  const [snapshot, setSnapshot] = useState<StreamSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    if (!jobId) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setError(null);

    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/api/jobs/${jobId}/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`Stream failed: ${res.status}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const block of parts) {
          const lines = block.split("\n");
          let dataLine = "";
          for (const line of lines) {
            if (line.startsWith("data:")) {
              dataLine += line.slice(5).trim();
            }
          }
          if (!dataLine) continue;
          try {
            const j = JSON.parse(dataLine) as StreamSnapshot;
            setSnapshot(j);
          } catch {
            /* ignore */
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    }
  }, [getToken, jobId]);

  useEffect(() => {
    if (!jobId) {
      setSnapshot(null);
      return () => {
        abortRef.current?.abort();
      };
    }
    void start();
    return () => abortRef.current?.abort();
  }, [jobId, start]);

  return { snapshot, error, reconnect: start };
}
