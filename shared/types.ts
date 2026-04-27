/** Shared shapes for FactCheckResult / job API (mirror backend Pydantic). */

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

export type JobPhase =
  | "queued"
  | "planning"
  | "searching"
  | "synthesizing"
  | "finalizing";

export interface JobProgress {
  phase: JobPhase;
  message: string;
  percent?: number | null;
  steps?: Array<{
    id: string;
    label: string;
    status: "pending" | "active" | "done" | "error";
  }>;
  updated_at?: string | null;
}

export interface JobRecord {
  id: string;
  clerk_user_id: string;
  job_type: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: JobProgress | null;
  report_payload: FactCheckResult | null;
  request_payload: { question: string };
  error_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}
