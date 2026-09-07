/**
 * client.ts — Typed fetch wrappers for every backend endpoint.
 * Every call handles both success and failure branches (rules.md §2 frontend).
 * Uses native fetch — no axios (rules.md §1 frontend allow-list).
 */

import type {
  DatasetType,
  DatasetUploadResponse,
  PipelineStatus,
  SlickPolygon,
  Shortlist,
  RankedSuspects,
  DarkShipResult,
  OilTypeResult,
} from "../types/contracts";

const BASE = "/api";

// ── Generic helpers ────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJSON<T>(
  input: RequestInfo,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = await response.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await response.text().catch(() => undefined);
    }
    throw new ApiError(response.status, `HTTP ${response.status}`, detail);
  }
  return response.json() as Promise<T>;
}

// ── Dataset upload ─────────────────────────────────────────────────────────

export async function uploadDataset(
  type: DatasetType,
  file: File,
  runId?: string
): Promise<DatasetUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const url =
    `${BASE}/datasets/${type}` + (runId ? `?run_id=${runId}` : "");
  return fetchJSON<DatasetUploadResponse>(url, { method: "POST", body: form });
}

// ── Pipeline control ───────────────────────────────────────────────────────

export async function runPipeline(runId: string): Promise<{ run_id: string; message: string }> {
  return fetchJSON(`${BASE}/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function runSimulate(runId: string): Promise<{ run_id: string; message: string }> {
  return fetchJSON(`${BASE}/pipeline/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
}

// ── Polling ────────────────────────────────────────────────────────────────

export async function getPipelineStatus(runId: string): Promise<PipelineStatus> {
  return fetchJSON<PipelineStatus>(`${BASE}/pipeline/status?run_id=${runId}`);
}

export async function getSlickPolygon(runId: string): Promise<SlickPolygon> {
  return fetchJSON<SlickPolygon>(`${BASE}/pipeline/slick?run_id=${runId}`);
}

export async function getOriginEnvelope(runId: string): Promise<any> {
  return fetchJSON<any>(`${BASE}/pipeline/origin-envelope?run_id=${runId}`);
}

export async function getResults(runId: string): Promise<RankedSuspects> {
  return fetchJSON<RankedSuspects>(`${BASE}/pipeline/results?run_id=${runId}`);
}

export async function simulatePipeline(runId: string): Promise<any> {
  return fetchJSON<any>(`${BASE}/pipeline/simulate`, {
    method: "POST",
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function getSimulatedFootprints(runId: string): Promise<any> {
  return fetchJSON<any>(`${BASE}/pipeline/simulated-footprints?run_id=${runId}`);
}

export async function getShortlist(runId: string): Promise<Shortlist> {
  return fetchJSON<Shortlist>(`${BASE}/pipeline/shortlist?run_id=${runId}`);
}

// ── Results ────────────────────────────────────────────────────────────────

export function getExportUrl(runId: string): string {
  return `${BASE}/pipeline/results/${runId}/export`;
}

// ── Prototype ─────────────────────────────────────────────────────────────

// ── Prototype (Tier 2) — never use run_id here (architecture.md §2.2) ──────

export async function getPrototypeDarkShip(): Promise<DarkShipResult> {
  return fetchJSON<DarkShipResult>(`${BASE}/prototype/dark-ship`);
}

export async function getPrototypeOilType(): Promise<OilTypeResult> {
  return fetchJSON<OilTypeResult>(`${BASE}/prototype/oil-type`);
}

// ── Health ─────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<{ status: string }> {
  return fetchJSON<{ status: string }>(`${BASE}/health`);
}
