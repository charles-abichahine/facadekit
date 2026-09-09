/**
 * The API client. Submit-and-poll: generation takes tens of seconds, so
 * nothing here ever waits on a single blocking request.
 */

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "") || "/api";

export type JobStatus = "queued" | "running" | "done" | "error";

export interface Metrics {
  panels?: number;
  legalised?: number;
  legalised_fraction?: number;
  unique_parts?: number;
  mean_fit_error_mm?: number;
  max_fit_error_mm?: number;
  solve_time_s?: number;
  sheets?: number;
  waste_pct?: number;
  unplaced?: number;
}

export interface Job {
  id: string;
  brief: string;
  status: JobStatus;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  metrics: Metrics;
  method: string | null;
  catalogue: { system: string; parts: number } | null;
  generator: string | null;
  warnings: string[];
  panels: number | null;
  files: string[];
}

export interface CatalogueInfo {
  file: string;
  ok: boolean;
  system?: string;
  parts?: number;
  kinds?: string[];
  problems?: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export interface SubmitOptions {
  brief: string;
  catalogue?: string;
  mask?: string;
  legaliser?: string;
  seed?: number;
}

export const submitJob = (opts: SubmitOptions) =>
  request<Job>("/jobs", { method: "POST", body: JSON.stringify(opts) });

export const getJob = (id: string) => request<Job>(`/jobs/${id}`);

export const getCatalogues = () =>
  request<{ catalogues: CatalogueInfo[]; default: string }>("/catalogues");

export const getMasks = () => request<{ masks: string[] }>("/masks");

export const fileUrl = (jobId: string, name: string) => `${BASE}/jobs/${jobId}/files/${name}`;

/** Poll until the job finishes. Returns the terminal job. */
export async function pollJob(
  id: string,
  onUpdate: (job: Job) => void,
  { intervalMs = 800, timeoutMs = 180_000 } = {},
): Promise<Job> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const job = await getJob(id);
    onUpdate(job);
    if (job.status === "done" || job.status === "error") return job;
    if (Date.now() > deadline) throw new Error("timed out waiting for the job");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
