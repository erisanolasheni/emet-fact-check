export type FactStatus =
  | "supported"
  | "partially_supported"
  | "contradicted"
  | "unknown";

export type VerdictCode = "supported" | "refuted" | "partial" | "unclear";

export type FactRole = "user_claim" | "evidence";

export interface SourceRef {
  id: string;
  url: string;
  title: string;
  snippet: string;
  tier: string;
  hostname: string;
  published_at?: string | null;
}

export interface FactItem {
  claim: string;
  status: FactStatus;
  source_ids: string[];
  role?: FactRole;
}

export interface FactCheckResult {
  verdict?: VerdictCode;
  verdict_text?: string;
  summary: string;
  facts: FactItem[];
  sources: SourceRef[];
  confidence_percent: number;
  confidence_rationale: string;
  limitations: string[];
}

/** Row from `GET /api/jobs` — enough for the conversation sidebar. */
export interface JobListEntry {
  id: string;
  job_type?: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  request_payload: { question: string; display_title?: string } | Record<string, unknown>;
  /** Present when the job finished; used for sidebar verdict dot colors. */
  report_payload?: FactCheckResult | null;
  created_at: string;
  updated_at: string | null;
}

export interface JobProgress {
  phase: string;
  message: string;
  percent?: number | null;
  steps?: Array<{
    id: string;
    label: string;
    status: "pending" | "active" | "done" | "error";
  }>;
  updated_at?: string | null;
}
