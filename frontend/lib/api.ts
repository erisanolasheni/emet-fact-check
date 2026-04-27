import type { FactCheckResult } from "@/types/factcheck";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function parseErrorDetail(text: string, parsed: unknown): string {
  if (parsed && typeof parsed === "object" && "detail" in parsed) {
    const d = (parsed as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : String(x))).join("; ");
  }
  return text || "Request failed";
}

export async function postFactCheck(token: string | null, question: string) {
  const res = await fetch(`${API_BASE}/api/fact-check`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.json() as Promise<{ job_id: string }>;
}

export async function getJob(token: string | null, jobId: string) {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listJobs(token: string | null, limit = 50) {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json() as Promise<
    Array<{
      id: string;
      job_type?: string;
      status: string;
      request_payload: { question?: string; display_title?: string } & Record<string, unknown>;
      report_payload?: FactCheckResult | null;
      created_at: string;
      updated_at: string | null;
    }>
  >;
}

export async function patchJobDisplayTitle(
  token: string | null,
  jobId: string,
  displayTitle: string,
) {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ display_title: displayTitle }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json() as Promise<{
    id: string;
    request_payload: Record<string, unknown>;
  }>;
}

export async function deleteJob(token: string | null, jobId: string) {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
}

export async function getSubscriptionStatus(token: string | null) {
  if (!token) {
    throw new ApiError(401, "No session token");
  }
  const res = await fetch(`${API_BASE}/api/subscription`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = null;
  }
  if (!res.ok) {
    throw new ApiError(res.status, parseErrorDetail(text, parsed));
  }
  return (parsed || {}) as { has_premium: boolean };
}
