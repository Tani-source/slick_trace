import type {
  DatasetType,
  DatasetUploadResult,
  PipelineStatus,
  RankedSuspects,
  RunResponse,
  Shortlist,
  SlickPolygon,
} from "../types/contracts";

const BASE = "/api";

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg =
      (body as Record<string, unknown>).detail ??
      (body as Record<string, unknown>).reason ??
      `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json() as Promise<T>;
}

export async function uploadDataset(
  type: DatasetType,
  file: File,
  provenance: string = "illustrative",
  windSpeedMs?: number | null,
): Promise<DatasetUploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("provenance", provenance);
  if (windSpeedMs != null) {
    form.append("wind_speed_ms", String(windSpeedMs));
  }
  return apiFetch<DatasetUploadResult>(`/datasets/${type}`, {
    method: "POST",
    body: form,
  });
}

export async function runPipeline(runId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>("/pipeline/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function simulatePipeline(runId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>("/pipeline/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function getPipelineStatus(runId: string): Promise<PipelineStatus> {
  return apiFetch<PipelineStatus>(`/pipeline/status?run_id=${encodeURIComponent(runId)}`);
}

export async function getSlick(runId: string): Promise<SlickPolygon> {
  return apiFetch<SlickPolygon>(`/pipeline/slick?run_id=${encodeURIComponent(runId)}`);
}

export async function getShortlist(runId: string): Promise<Shortlist> {
  return apiFetch<Shortlist>(`/pipeline/shortlist?run_id=${encodeURIComponent(runId)}`);
}

export async function getResults(runId: string): Promise<RankedSuspects> {
  return apiFetch<RankedSuspects>(`/results/${encodeURIComponent(runId)}`);
}

export async function downloadExport(runId: string): Promise<void> {
  const res = await fetch(`${BASE}/results/${encodeURIComponent(runId)}/export`);
  if (!res.ok) {
    throw new Error(`Export failed: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `slicktrace-results-${runId}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getPrototypeDarkShip(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/prototype/dark-ship");
}

export async function getPrototypeOilType(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/prototype/oil-type");
}

export async function health(): Promise<{ status: string; service: string }> {
  return apiFetch<{ status: string; service: string }>("/health");
}
