export type StageName =
  | "perception"
  | "ais_ingestion"
  | "candidate_filtering"
  | "anomaly_scoring"
  | "drift_simulation"
  | "verification_matching";

export type StageStatus = "pending" | "running" | "done" | "failed";

export interface PipelineStage {
  name: StageName;
  status: StageStatus;
  progress_pct: number;
  detail: string;
}

export interface PipelineStatus {
  run_id: string;
  stages: PipelineStage[];
}

export interface SlickPolygon {
  polygon: [number, number][];
  detection_time: string;
  bbox: [number, number, number, number];
  area_km2: number;
  elongation_ratio: number;
  age_estimate_hours: number | null;
  weathering_validity: boolean;
  age_confidence: "high" | "low";
}

export interface AnomalyBreakdown {
  blackout: number;
  speed: number;
  route: number;
  draft: number;
}

export interface ShortlistCandidate {
  mmsi: string;
  vessel_name: string;
  vessel_type: "tanker" | "cargo" | "bunkering";
  operator: string;
  flag: string;
  destination: string;
  position_at_event: { lat: number; lon: number; time: string };
  anomaly_score: number;
  anomaly_breakdown: AnomalyBreakdown;
  candidate_release_points: { lat: number; lon: number; time: string }[];
}

export interface Shortlist {
  run_id: string;
  candidates: ShortlistCandidate[];
}

export interface RankedSuspect {
  mmsi: string;
  vessel_name: string;
  match_score: number;
  iou: number;
  centroid_distance_km: number;
  orientation_match: number;
  rank: number;
}

export interface RankedSuspects {
  run_id: string;
  ranking: RankedSuspect[];
}

export type DatasetType = "wind" | "current" | "sar" | "ais";

export interface DatasetUploadResult {
  run_id: string;
  type: DatasetType;
  status: "uploaded" | "invalid";
  reason?: string;
  provenance: string;
  file_name: string;
  size_bytes: number;
  bbox?: [number, number, number, number] | null;
  date_range?: [string, string] | null;
  detail?: string;
}

export interface RunResponse {
  run_id: string;
  status: "started";
}

export type TabId = "results" | "input" | "pipeline" | "shortlist";

export interface DatasetInfo {
  status: "not_uploaded" | "uploaded" | "invalid";
  reason?: string;
  provenance?: string;
  file_name?: string;
  size_bytes?: number;
  bbox?: [number, number, number, number] | null;
  date_range?: [string, string] | null;
}

export const STAGE_LABELS: Record<StageName, string> = {
  perception: "Perception",
  ais_ingestion: "AIS Ingestion",
  candidate_filtering: "Candidate Filtering",
  anomaly_scoring: "Anomaly Scoring",
  drift_simulation: "Drift Simulation",
  verification_matching: "Verification & Matching",
};

export const STAGE_DESCRIPTIONS: Record<StageName, string> = {
  perception:
    "U-Net segmentation on SAR imagery → binary mask → oil slick polygon with area, shape descriptors, and age estimate.",
  ais_ingestion:
    "Ingest AIS vessel-tracking data; parse positions, timestamps, and vessel metadata for spatiotemporal filtering.",
  candidate_filtering:
    "Filter AIS traffic by spatiotemporal overlap with the origin envelope and vessel discharge capability.",
  anomaly_scoring:
    "Score candidates on blackout gaps, speed anomalies, route deviations, and draft inconsistencies → AnomalyScore [0,1].",
  drift_simulation:
    "Forward drift simulation from candidate release points to the detection timestamp using OpenDrift/OilDrift.",
  verification_matching:
    "Match simulated footprint against observed slick via IoU, centroid distance, and orientation → ranked suspect list.",
};

export const STAGE_ICONS: Record<StageName, string> = {
  perception: "👁️",
  ais_ingestion: "📡",
  candidate_filtering: "🔍",
  anomaly_scoring: "⚠️",
  drift_simulation: "🌊",
  verification_matching: "✅",
};

export type ProvenanceTag = "real" | "synthetic" | "illustrative";
