# PRD.md — SlickTrace
**Oil Spill Source Attribution System — SIH26143 (NTRO)**

---

## 1. What This Is

SlickTrace is an automated pipeline + dashboard that takes a detected oil slick from satellite imagery, works backward to find where and when it likely originated, cross-references AIS vessel-traffic data for that window, and ranks the vessels most likely responsible — with every intermediate score visible, not a black-box verdict.

This document is the **what and why**. It does not prescribe implementation — see `architecture.md`, `rules.md`, `phases.md`, and `design.md` for that.

---

## 2. Problem Statement (from PS 26143)

Marine oil spills damage ecosystems and are frequently un-attributable to the responsible vessel. Given SAR/EO satellite imagery and AIS vessel-tracking data, build an automated pipeline that:

- **(a)** Detects and characterizes an oil spill — geometry, area, age.
- **(b)** Traces the slick backward to origin point/time using ocean current + wind data, and predicts forward drift.
- **(c)** Attributes the spill to a vessel by reconstructing AIS traffic around the origin window, filtering irrelevant traffic, and scoring suspects on proximity, trajectory, and behavioral anomalies.

Plus a visual interface to operate and present all of the above.

Issuing organization: **NTRO**. Theme: **Disaster Management**.

---

## 3. Targeted Users

| User | What they need from SlickTrace |
|---|---|
| **Coast Guard / maritime enforcement analyst** (primary persona for the product framing) | A ranked, evidence-backed shortlist of suspect vessels for a detected slick, with transparent sub-scores they can defend in a report — not a single opaque probability. |
| **NTRO / investigative body** | A tool that turns raw satellite + AIS feeds into a decision-support artifact — explicitly *not* claimed as courtroom-ready legal evidence. |
| **SIH judges (immediate audience)** | A working, demoable pipeline that visibly executes every stage of the PS's own (a)/(b)/(c) structure, with clear "live vs. prototype" labeling and no overclaiming. |
| **Future operator (roadmap persona)** | A standing monitoring tool reusable across any coastline, not a one-off hackathon analysis. |

For the hackathon build, **design and prioritize for the SIH judges' path**: upload 4 datasets → watch pipeline run → get a ranked, explainable suspect list → be able to compare simulated vs. observed slick visually.

---

## 4. Goals

1. Build a working, non-mocked pipeline for every Tier 1 stage (Stage 0 through Stage 6, per `approach_3_-_oil_spill.pdf`).
2. Make every stage's output visible and inspectable in the dashboard — no stage is a black box.
3. Ship the dashboard skeleton exactly as specified in the dashboard build spec (4-tab sidebar, map, right-edge tools, bottom panel) — see `design.md` / `architecture.md`.
4. Keep Tier 2 (dark-ship detection, oil-type fingerprinting) clearly labeled as **prototype/roadmap**, backed by a pre-computed example — never presented as live inference.
5. Keep compute bounded: physics simulation (Stage 1, Stage 5) only ever runs on the Stage 2–4 shortlist, never on the full AIS traffic pool.
6. Have a prepared, honest answer for every item in the PS's own "Known Gaps" table (real-case validation, legal-evidentiary framing, weathering physics, synthetic AIS, scalability, team domain-skill gap).

## 5. Non-Goals (for this build)

- No user authentication or multi-user accounts.
- No support for more than one active "case" at a time in the UI.
- No production infra / scaling concerns — local or lightweight cloud hosting is sufficient for the demo.
- No claim of legal/courtroom-grade evidence output.
- No live inference for Tier 2 features — prototype/cached only.

---

## 4. Goals

1. Build a working, non-mocked pipeline for every Tier 1 stage (Stage 0 through Stage 6: Perception, Backward Drift, AIS Ingestion, Candidate Filtering, Anomaly Scoring, Forward Drift Simulation, Verification & Matching).
2. Provide a 1-click evaluation pathway (`POST /api/datasets/load-demo` via "⚡ Load Demo Scenario" in the UI) allowing judges and operators to immediately run the complete attribution workflow without manual multi-file uploads.
3. Make every stage's output visible and inspectable in the dashboard — no stage is a black box.
4. Ship the dashboard skeleton as specified (4-tab sidebar: Verdict, Datasets, Pipeline, Shortlist; persistent map; right-edge floating tools; bottom telemetry panel).
5. Keep Tier 2 (dark-ship detection, oil-type fingerprinting) clearly labeled as **prototype/roadmap**, backed by a pre-computed example — never presented as live inference.
6. Keep compute bounded and cloud-safe: physics simulation only runs on the shortlisted candidates, with memory-aware advection fallback ensuring zero crashes even in memory-constrained cloud environments (Render 512MB).
7. Have a prepared, honest answer for every item in the PS's own "Known Gaps" table (real-case validation, legal-evidentiary framing, weathering physics, synthetic AIS, scalability, team domain-skill gap).

## 5. Non-Goals (for this build)

- No user authentication or multi-user accounts.
- No support for more than one active "case" at a time in the UI.
- No claim of courtroom-grade legal evidence output (decision support only).
- No live deep-learning inference for Tier 2 prototype features (cached benchmark responses only).

---

## 6. Core Features (Functional Requirements)

Features are grouped by pipeline stage (backend) and by dashboard tab (frontend), since the two map directly onto each other.

### 6.1 Tier 1 — Must Be Live and Working

**F1 — Slick Detection & Characterization (Stage 0: Perception)**
- Input: Sentinel-1 SAR (GeoTIFF/PNG) with automatic CRS/transform extraction via Rasterio/PIL.
- U-Net segmentation → binary oil mask → geospatial polygon with area (km²), elongation ratio, and age estimate.
- Look-alike rejection using wind-speed thresholding (1.5–10 m/s valid window) and texture heuristics.
- Output: `slick_polygon.json` with `weathering_validity` flag (age > 72h flags downstream low-confidence tag).

**F2 — Backward Drift Trace (Stage 1: Backward Drift)**
- Seed particles across the slick polygon; run reverse advection using ocean current and wind forcing fields, bounded by estimated slick age.
- Output: `origin_envelope` GeoJSON polygon + probable release time window.
- Cloud resilience: Uses OpenDrift (`OpenOil`) in standard environments, falling back gracefully to NumPy vector advection on memory-constrained tiers (`RENDER=true`), marking `fallback_used: true`.

**F3 — AIS Spatiotemporal Ingestion (Stage 2: AIS Ingestion)**
- Ingests maritime AIS vessel traffic within the spatial bounding box and time window calculated by Stage 1.
- Output: Raw candidate vessel track pool.

**F4 — Candidate Vessel Filtering (Stage 3: Candidate Filtering)**
- Filters candidate vessels by physical discharge plausibility: vessel type codes (tanker, cargo/bulk, bunkering), draft characteristics, and spatiotemporal corridor proximity.
- Output: Filtered candidate vessel subset.

**F5 — AIS Behavioral Anomaly Scoring (Stage 4: Anomaly Scoring)**
- Multi-factor anomaly scoring: AIS blackout duration (weighted highest), speed deviation during transit, route corridor DTW departure, and reported draft alterations.
- Weighted sum → `AnomalyScore [0,1]`, generating the top-N (5–10) shortlist.
- Output: `shortlist.json` with per-factor breakdown (`blackout`, `speed`, `route`, `draft`).

**F6 — Forward Drift Trajectory Simulation (Stage 5: Drift Simulation)**
- Forward-simulate candidate release points to the satellite detection timestamp using ocean current and wind forcing (**strictly executed on top-N shortlist**, never the full vessel pool).
- Output: `simulated_footprints` polygons for each shortlisted vessel.

**F7 — Geometric Verification & Ranking (Stage 6: Verification / Matching)**
- Computes geometric intersection-over-union (IoU), centroid proximity distance (km), and principal orientation alignment between simulated drift footprints and observed SAR slick polygon.
- Weighted match score → `MatchScore [0,1]` and final suspect ranking.
- Output: `ranked_suspects.json`.

**F8 — Dashboard: 4-Tab Sidebar**
- **Tab 1: Verdict (`output`)**: Post-simulation ranked suspects, `MatchScore` badge, carried-over `AnomalyScore` breakdown, split comparison trigger, and export zip download.
- **Tab 2: Datasets (`input`)**: 4 upload cards (Wind, Current, SAR Image, AIS) + ⚡ **"Load Demo Scenario"** 1-click benchmark evaluation trigger + "Run Pipeline" button.
- **Tab 3: Pipeline (`pipeline`)**: 7-stage live execution stepper with progress %, detail messages, and `.st-stage.failed` alert cards showing exact backend error strings on failure.
- **Tab 4: Shortlist (`suspects`)**: Pre-simulation candidate list from Stage 4 with multi-factor anomaly chips and candidate release points.

**F9 — Map Canvas**
- Always-visible Leaflet base map with toggleable layers:
  1. Observed slick polygon (`SlickLayer`)
  2. Hindcast origin envelope (`OriginEnvelopeLayer`)
  3. AIS vessel tracks (`AISTrackLayer`, colored by anomaly score)
  4. Candidate release points (`ReleasePointLayer`)
  5. Simulated drift footprints (`SimulatedDriftLayer`)
  6. Dark-ship detections (`DarkShipLayer`, Tier 2 prototype)
- Split comparison mode: Side-by-side verification of observed slick vs. simulated drift footprints.

**F10 — Bottom Telemetry Panel**
- Live pipeline metrics (slick area, origin time window, candidates screened, top suspect MMSI) and interactive "Run Simulation" trigger.

**F11 — Floating Tools Stack**
- Zoom in/out, reset view, maximize map canvas, annotate, screenshot export.

### 6.2 Tier 2 — Prototype Toggle Only (Bonus Features)

**F12 — Dark-Ship Detection (Stage 2b Prototype)**
- CFAR point-target detector on SAR imagery; targets without active AIS within the spill envelope are flagged.
- UI toggle with persistent **"Prototype — architecture below"** labeling, backed by pre-computed response.

**F13 — Oil-Type Fingerprinting (Stage 5b Prototype)**
- Spectral classification from Sentinel-2 bands (crude vs. bunker fuel vs. refined) matched against top suspect cargo declarations.
- UI toggle, same prototype labeling as F12.

---

## 7. Data Contracts (Summary — full shapes in `architecture.md`)

- `slick_polygon.json` — feeds map's observed slick layer + Datasets tab SAR status.
- `origin_envelope` — feeds map's origin envelope layer (Stage 1 output).
- `shortlist.json` — feeds Shortlist tab and candidate release point layer (Stage 4 output).
- `simulated_footprints` — feeds forward-simulated footprints on map (Stage 5 output).
- `ranked_suspects.json` — feeds Verdict tab rankings and match scores (Stage 6 output).
- `pipeline_status.json` — feeds Pipeline tab 7-stage stepper and bottom panel live numbers.

---

## 8. Success Criteria (Hackathon Context)

- **1-Click Evaluation**: A judge or evaluator can click "⚡ Load Demo Scenario", run the pipeline, and view complete suspect attribution in under 60 seconds without manual configuration.
- **Transparency**: Every Tier 1 stage runs end-to-end with visible progress and inspectable intermediate artifacts.
- **Explainability**: Suspect ranking displays both `MatchScore` (drift physics) and `AnomalyScore` (behavioral AIS) separately — never merged into an opaque composite.
- **Zero-Crash Resilience**: Container restarts, network disconnections, and cloud memory limits (512MB RAM) are handled gracefully with auto-recovery and clear UI feedback.
- **Honesty Framing**: Prototype features and synthetic test data are explicitly labeled in the UI.

---

## 9. Key Constraints & Deployment Topologies

- **Deployment Model**: Zero-cost hosting supported across Hugging Face Spaces (16GB RAM Docker for full OpenDrift), Render (512MB RAM with memory-safe advection engine), and Vercel edge CDN for decoupled frontend.
- **Compute Bounded**: Physics simulation runs exclusively on the top-N shortlist (rules.md §3.8).
- **Advection Adaptation**: In <1GB RAM cloud environments, vectorized NumPy advection is used to prevent kernel OOM kills, setting `fallback_used: true`.

---

## 10. Resolved Design Decisions

- **Dashboard Stack**: React 18 + Vite + TypeScript + Leaflet selected and built over Streamlit to achieve persistent icon-rail navigation, multi-layer map rendering, and split-view comparison.
- **Demo Benchmark Scenario**: Pre-packaged synthetic benchmark dataset in `backend/data/synthetic/` covering the Southern California coastal corridor (Santa Barbara Channel), with synthetic SAR GeoTIFF, AIS tracks CSV, ERA5 wind NetCDF, and CMEMS current NetCDF.

