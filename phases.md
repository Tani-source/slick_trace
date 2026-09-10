# phases.md — SlickTrace

**Build phases, sequencing, and what ships when.**
Reads on top of `prd.md` (what/why), `architecture.md` (what/where), and `rules.md` (how/how-not-to). This file answers: *in what order, and what's the minimum that has to be true at each checkpoint to keep the demo alive if time runs out.*

A note on the phrase "dashboard, login, and all": there is no login phase. Authentication is an explicit non-goal (PRD §5) — it is never scheduled, never partially built, and never added even if a task seems to imply it (rules.md §3.5). Every phase below ships the full 4-tab dashboard skeleton progressively wired to real data; "and all" means the dashboard, not auth.

---

## 0. Sequencing Principle

Backend pipeline stages and frontend tabs are built **in lockstep, stage-by-stage**, not backend-first-then-frontend or vice versa. Each phase below pairs one (or two) pipeline stage(s) with the dashboard surface that displays their output, because:

- `architecture.md` §2.3 makes the frontend a pure renderer of backend state — there's nothing to build on the frontend side until a stage produces a real shape.
- `rules.md` §4 commits to "one stage or one tab per commit" — phases are just that principle at a coarser grain.
- A stage is not "done" until it's both tested (`rules.md` §4, fixtures required) *and* visible in the UI (`rules.md` §2, no silent failures) — pairing them prevents a phase from silently sliding into "backend works, nobody can see it."

Each phase has: **Goal**, **Backend**, **Frontend**, **Exit criteria** (what must be true to call the phase closed), and **If time is short** (what's safe to defer without breaking the demo's honesty framing).

---

## Phase Status Summary

| Phase | Description | Status | Key Deliverables & Pivots |
|---|---|---|---|
| **Phase 0** | Scaffolding & Contracts | **COMPLETED** | FastAPI backend, Vite React SPA, 4 JSON schemas & TS contracts synchronized. |
| **Phase 1** | Stage 0 (Perception) + Datasets Tab + Slick Layer | **COMPLETED** | U-Net segmentation, GeoTIFF CRS/transform extraction with PIL fallback, file validators. |
| **Phase 2** | Stage 1 (Backward Drift) + Origin Envelope Layer | **COMPLETED** | Reverse advection hindcast, origin spatiotemporal envelope, memory-aware fallback advection. |
| **Phase 3** | Stage 2/3 (AIS Filter) + Stage 4 (Anomaly) + Shortlist Tab | **COMPLETED** | AIS spatiotemporal corridor query, multi-factor anomaly scoring (blackout, speed, route, draft). |
| **Phase 4** | Stage 5 (Forward Drift) + Stage 6 (Matching) + Verdict Tab | **COMPLETED** | Forward advection on top-N shortlist, IoU/centroid/orientation similarity matching, ranked suspects. |
| **Phase 5** | Tier 2 Prototypes (Dark-Ship & Oil-Type) | **COMPLETED** | Pre-computed benchmark demonstration endpoints isolated from live pipeline run state. |
| **Phase 6** | Polish, Error Boundaries, 1-Click Demo & Polling | **COMPLETED** | 7-stage polling loop in `pipelineStore.ts`, auto-tab switching, `.st-stage.failed` alert, `POST /api/datasets/load-demo`. |
| **Phase 7** | Production Cloud Deployment & Topologies | **COMPLETED** | Multi-stage Dockerfile, Hugging Face Spaces (16GB RAM), Render 512MB memory-safe engine, Vercel CDN (`vercel.json`). |
| **Phase 8** | Demo Rehearsal & Verification | **OPERATIONAL** | Automated tests passing (24 tests), instant 1-click evaluation pathway ready. |

---

## Phase 0 — Scaffolding & Contracts [COMPLETED]

**Goal:** A running application with synchronized contracts.
- **Backend:** Repo layout created; FastAPI app mounted with CORS; schemas defined in `app/schemas/` (`slick_polygon.py`, `shortlist.py`, `ranked_suspects.py`, `pipeline_status.py`).
- **Frontend:** React 18 + Vite + TypeScript scaffold, Zustand stores (`pipelineStore.ts`, `uiStore.ts`), strictly typed `src/types/contracts.ts`, base shell layout.
- **Exit Verification:** Backend booted, contracts confirmed identical across Python and TypeScript.

---

## Phase 1 — Stage 0 (Perception) + Datasets Tab + Slick Layer [COMPLETED]

**Goal:** Real satellite image segmentation and polygon rendering.
- **Backend:** `stage0_perception.py` loads SAR GeoTIFF/PNG imagery, runs PyTorch U-Net inference with heuristic fallback, computes slick area and elongation ratio, applies age estimate. GeoTIFF georeferencing extracted via `rasterio` with fallback to PIL.
- **Dataset Validation:** `POST /api/datasets/{type}` validates magic bytes for GeoTIFF, PNG, NetCDF, and CSV headers.
- **Frontend:** Datasets (`input`) tab with 4 upload cards, validation badges, and `SlickLayer.tsx` rendering on the Leaflet map.

---

## Phase 2 — Stage 1 (Backward Drift) + Origin Envelope Layer [COMPLETED]

**Goal:** Reverse trajectory advection to identify probable spill origin spatiotemporal envelope.
- **Backend:** `stage1_backward_drift.py` and `drift_engine.py` execute reverse advection using current and wind forcing fields.
- **Architectural Pivot (Cloud Memory Safety):** Full OpenDrift allocates ~1.6 GB RAM due to NOAA ADIOS database and GSHHG basemaps, causing kernel OOM kills on 512MB tiers (Render). Added environment-aware advection fallback (`_disable_opendrift` when `RENDER=true` or `DISABLE_OPENDRIFT=true`), setting `"fallback_used": true` in the output contract.
- **Frontend:** `OriginEnvelopeLayer.tsx` displays dashed amber origin region polygon.

---

## Phase 3 — Stage 2/3 (AIS Filter) + Stage 4 (Anomaly Scoring) + Shortlist Tab [COMPLETED]

**Goal:** AIS ingestion within origin envelope and behavioral anomaly shortlisting.
- **Backend:** `ais_loader.py` ingests vessel tracks, filters candidates within the spatiotemporal bounding box, and excludes non-discharge vessel types. `anomaly_weights.py` computes multi-factor anomaly scores (AIS blackout duration, speed variation, route DTW deviation, draft changes) to produce top-N shortlist.
- **Frontend:** Shortlist (`suspects`) tab populates with candidate cards, anomaly score breakdown chips, and candidate release points. `AISTrackLayer.tsx` renders vessel tracks colored by anomaly score.

---

## Phase 4 — Stage 5 (Forward Drift) + Stage 6 (Matching) + Verdict Tab [COMPLETED]

**Goal:** Forward drift trajectory simulation on shortlisted vessels and geometric verification.
- **Backend:** `stage5_forward_drift.py` simulates forward drift from candidate release points to the observation timestamp (**strictly on top-N shortlist**, enforcing rules.md §3.8). `stage6_matching.py` calculates IoU overlap, centroid distance, and orientation similarity to generate `MatchScore` and suspect ranking.
- **Frontend:** Verdict (`output`) tab displays ranked suspects, distinct `MatchScore` and `AnomalyScore` badges, split comparison view (`CompareView.tsx`), and zip export (`GET /api/results/{run_id}/export`).

---

## Phase 5 — Tier 2 Prototypes (Dark-Ship & Oil-Type) [COMPLETED]

**Goal:** Pre-computed demonstration channels for dark ships and oil spectral classification.
- **Backend:** `GET /api/prototype/dark-ship` and `GET /api/prototype/oil-type` provide cached benchmark data without accepting `run_id`, preventing any contamination of the live pipeline.
- **Frontend:** Toggles with explicit "Prototype — architecture below" labeling, rendering `DarkShipLayer.tsx` on the map.

---

## Phase 6 — Polish, Error Boundaries, 1-Click Evaluation & Polling Loop [COMPLETED]

**Goal:** Resilient error handling, non-blocking execution, and seamless judge evaluation.
- **Architectural Pivot (FastAPI Threading):** Converted background task worker from `async def` to synchronous `def _run_and_release()` so CPU-bound pipeline stages execute on FastAPI's threadpool without starving the async event loop.
- **1-Click Evaluation:** Added `POST /api/datasets/load-demo` and the **"⚡ Load Demo Scenario"** button in `InputTab.tsx`, allowing evaluators to load all 4 pre-packaged benchmark datasets simultaneously without manual file picking.
- **Client Polling & Recovery:** `pipelineStore.ts` implements a continuous 1.0s polling loop with automatic tab switching (Input → Pipeline → Shortlist → Pipeline → Verdict), stage failure rendering (`.st-stage.failed`), and 404 stale-run auto-recovery.
- **Connection Health:** Periodic `/api/health` polling with an auto-dismissing banner when the server restarts.

---

## Phase 7 — Production Cloud Deployment & Topologies [COMPLETED]

**Goal:** Robust, zero-cost production hosting options documented in `DEPLOYMENT_GUIDE.md`.
- **Unified Container (Docker):** Multi-stage `Dockerfile` (Node 20 Vite build + Python 3.11 FastAPI serving SPA assets at `/` and API at `/api`).
- **Hugging Face Spaces (16 GB RAM):** Free Docker deployment accommodating full OpenDrift and PyTorch workloads without memory throttling.
- **Render Web Service (512 MB RAM):** Supported via memory-aware NumPy advection fallback (`_disable_opendrift`).
- **Decoupled Vercel CDN:** `frontend/vercel.json` deploys frontend to Vercel edge CDN, communicating with cloud backend via `VITE_API_URL`.
- **Cloudflare Tunnel:** Instant local-to-cloud secure tunnel for live hackathon evaluations.

---

## Phase 8 — Operational Readiness & Demo Verification [OPERATIONAL]

- Comprehensive test suite passing: `pytest backend/tests` (24 passed unit/integration tests).
- Clean frontend production build: `npm run build` in `frontend/` (zero warnings, strict TypeScript compliance).
- 1-click evaluation pathway tested end-to-end: Datasets → Run Pipeline → Shortlist → Run Simulation → Verdict → Export.

---

## Cross-Cutting Rules (Enforced in All Phases)

1. **Honesty Framing:** Synthetic data is always clearly tagged as "Synthetic" or "Illustrative".
2. **Prototype Isolation:** Tier 2 endpoints never touch live pipeline state.
3. **Dual Scores:** `AnomalyScore` and `MatchScore` are always presented as distinct badges, never merged into an opaque composite percentage.
4. **Contract Synchronization:** Schema modifications touch `backend/app/schemas/*.py` and `frontend/src/types/contracts.ts` simultaneously.

