/**
 * contracts.ts — TypeScript interfaces mirroring the 4 backend JSON contracts.
 * NO `any`. Strict mode. (rules.md §4, architecture.md §6)
 * Must stay in lockstep with backend/app/schemas/*.py (rules.md §3.4).
 */

// ── pipeline_status.json ──────────────────────────────────────────────────
export type StageStatus = "pending" | "running" | "done" | "failed";

export interface StageInfo {
  name: string;
  status: StageStatus;
  progress_pct: number;
  detail: string;
}

export interface PipelineStatus {
  stages: StageInfo[];
}

// ── slick_polygon.json ────────────────────────────────────────────────────
export interface SlickPolygon {
  polygon: [number, number][]; // [[lat, lon], ...]
  detection_time: string; // ISO8601
  bbox: [number, number, number, number]; // [minLat, minLon, maxLat, maxLon]
  area_km2: number;
  elongation_ratio: number;
  age_estimate_hours: number;
  weathering_validity: boolean; // false if age > 72h
  fallback_used: boolean;
}

// ── shortlist.json ────────────────────────────────────────────────────────
export interface PositionAtEvent {
  lat: number;
  lon: number;
  time: string;
}

export interface AnomalyBreakdown {
  blackout: number;
  speed: number;
  route: number;
  draft: number;
}

export interface ReleasePoint {
  lat: number;
  lon: number;
  time: string;
}

export interface Candidate {
  mmsi: string;
  vessel_name: string;
  vessel_type: "tanker" | "cargo" | "bunkering" | string;
  operator: string;
  flag: string;
  destination: string;
  position_at_event: PositionAtEvent;
  anomaly_score: number;
  anomaly_breakdown: AnomalyBreakdown;
  candidate_release_points: ReleasePoint[];
}

export interface Shortlist {
  candidates: Candidate[];
}

// ── ranked_suspects.json ──────────────────────────────────────────────────
export interface RankedVessel {
  mmsi: string;
  vessel_name: string;
  match_score: number;
  iou: number;
  centroid_distance_km: number;
  orientation_match: number;
  rank: number;
}

export interface RankedSuspects {
  ranking: RankedVessel[];
}

export interface SimulatedFootprint {
  mmsi: string;
  vessel_name: string;
  simulated_polygon: [number, number][];
  fallback_used: boolean;
}

export interface SimulatedFootprints {
  simulations: SimulatedFootprint[];
}

// ── Dataset upload response (not a pipeline contract but typed here) ───────
export type DatasetType = "wind" | "current" | "sar" | "ais";
export type UploadStatus = "uploaded" | "invalid" | "not_uploaded";

// ── Prototype Tier 2 responses ─────────────────────────────────────────────
export interface DarkShipResult {
  prototype: boolean;
  label: string;
  detected_vessels: { lat: number; lon: number; confidence: number; note: string }[];
  method: string;
}

export interface OilTypeResult {
  prototype: boolean;
  label: string;
  classified_type: string;
  confidence: number;
  method: string;
  note: string;
}
export type ProvenanceTag = "real" | "synthetic" | "illustrative";

export interface DatasetUploadResponse {
  status: "uploaded" | "invalid";
  dataset_type: DatasetType;
  filename: string;
  run_id: string;
  reason?: string;
  bbox?: [number, number, number, number];
  date_range?: [string, string];
  provenance: ProvenanceTag;
}

export interface OriginEnvelope {
  polygon: [number, number][];
  bbox: [number, number, number, number];
  area_km2: number;
  time_window_hours: number;
  start_time: string;
  end_time: string;
  fallback_used: boolean;
}
