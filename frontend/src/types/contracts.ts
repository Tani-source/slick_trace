export interface SlickPolygon {
  polygon: [number, number][]; // [lat, lon]
  detection_time: string; // ISO8601
  bbox: [number, number, number, number]; // [minLat, minLon, maxLat, maxLon]
  area_km2: number;
  elongation_ratio: number;
  age_estimate_hours: number;
}

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

export interface CandidateReleasePoint {
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
  candidate_release_points: CandidateReleasePoint[];
}

export interface Shortlist {
  candidates: Candidate[];
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
  ranking: RankedSuspect[];
}

export interface StageStatus {
  name: string;
  status: "pending" | "running" | "done" | "failed";
  progress_pct: number;
  detail: string;
}

export interface PipelineStatus {
  stages: StageStatus[];
}
