# architecture.md — SlickTrace

**App flow, folder/file structure, tech stack, and deployment topologies.**
Read `prd.md` first — this document implements it, doesn't redefine it.

---

## 1. Stack & Architecture Decisions (and why)

**Frontend: React 18 (Vite + TypeScript) + Leaflet, not Streamlit.**

The dashboard spec requires: a collapsible icon-rail sidebar with 4 independently-stateful panels, an always-visible map underneath whichever panel is open, floating circular tool buttons pinned to a fixed screen position, a split/overlay compare mode between observed and simulated slicks, and an interactive timeline scrubber. Streamlit's layout model (top-to-bottom reruns, no persistent floating elements, no real split-pane map compare) fights all of that. React provides real component state, a real map library, and an operational dark-ocean HUD.

**Backend: Python FastAPI (Python 3.11+).** Every ML/geospatial library in the PS's tech stack (OpenDrift, U-Net via PyTorch, GeoPandas, Shapely, Rasterio) is Python-only — the backend is not an arbitrary choice, it is a constraint. FastAPI over Flask provides async endpoints, typed Pydantic validation, OpenAPI documentation, and standard `BackgroundTasks` execution.

**Communication: REST + Continuous Polling, not WebSockets.** `pipeline_status.json` is compact and stages execute over seconds to minutes. Continuous client polling (1.0s interval) in `pipelineStore.ts` provides resilient progress tracking, stage-by-stage auto tab-switching, and graceful recovery if cloud containers restart.

**Map Library: Leaflet + react-leaflet.** No external API key/token dependency to manage during live evaluation; lightweight and reliable for polygon, track, and marker layers.

**Compute & Memory Adaptation (Cloud Free-Tier Resilience):**
Full OpenDrift (`OpenOil`) loads the global GSHHG shoreline basemap and the NOAA ADIOS oil database (>780k records), consuming ~1.6 GB of RAM. On memory-constrained cloud free tiers (e.g. Render 512 MB RAM), this causes immediate kernel OOM `SIGKILL` (502 Bad Gateway). SlickTrace implements an environment-aware advection engine in `drift_engine.py`:
- In high-memory environments (local machine, Hugging Face Spaces with 16 GB RAM), full OpenDrift advection runs.
- When `RENDER=true` or `DISABLE_OPENDRIFT=true`, the engine seamlessly engages a vectorized NumPy advection fallback, setting `"fallback_used": true` in the output contract (transparently disclosed in the UI).
- CPU-bound pipeline executions in FastAPI use synchronous worker threads (`def`, not `async def`) to avoid blocking the main asyncio event loop.

---

## 2. App Flow

### 2.1 High-Level Execution Sequence

```
1. User opens dashboard → Input ("Datasets") tab active by default, map empty with dark basemap.
2. User provides datasets via either:
   a) Manual upload: Wind (.nc/.csv), Ocean Current (.nc/.csv), SAR Image (.tif/.png), AIS (.csv)
      → POST /api/datasets/{type} validates magic bytes/headers, returns status + inferred bbox/date range.
   b) 1-Click Evaluation: User clicks "⚡ Load Demo Scenario"
      → POST /api/datasets/load-demo provisions all 4 synthetic benchmark datasets simultaneously.
3. All 4 datasets uploaded → "Run Pipeline" button activates.
4. User clicks "Run Pipeline" → POST /api/pipeline/run
   → Backend starts Stages 0–4 as a background task, returns run_id immediately.
   → Frontend automatically switches to the Pipeline tab.
5. Frontend polls GET /api/pipeline/status?run_id=... every 1.0s:
   → Stage 0 (Perception): U-Net / threshold segmentation → slick polygon rendered on map.
   → Stage 1 (Backward Drift): Reversed advection → origin envelope rendered on map.
   → Stage 2 (AIS Ingestion): Ingests AIS traffic within the origin spatiotemporal envelope.
   → Stage 3 (Candidate Filtering): Filters candidates by corridor, vessel type, and draft.
   → Stage 4 (Anomaly Scoring): Multi-factor scoring (blackout, speed, route DTW, draft) → shortlist generated.
   → On Stage 4 completion, frontend automatically switches to the Shortlist tab.
6. Shortlist ready → Verdict ("Results") tab enables the "Run Simulation" button.
7. User clicks "Run Simulation" → POST /api/pipeline/simulate
   → Backend runs Stage 5 (Forward Drift Simulation for top-N shortlist) and Stage 6 (Verification & Matching).
   → Frontend switches to Pipeline tab and polls status.
8. On completion of Stage 6:
   → Frontend automatically switches to the Verdict tab.
   → GET /api/results/{run_id} populates ranked suspects with MatchScore and AnomalyScore breakdown.
9. User toggles "Compare Mode" → side-by-side split map comparing observed slick vs. simulated drift footprint.
10. User clicks "Export Package" → GET /api/results/{run_id}/export downloads full GeoJSON/JSON zip bundle.
```

### 2.2 Tier 2 (Prototype) Flow — Deliberately Isolated

Dark-ship detection and oil-type fingerprinting are **not** mixed into the live pipeline. They are toggles in the UI that call `GET /api/prototype/dark-ship` and `GET /api/prototype/oil-type`, returning pre-computed benchmark responses. These endpoints do not accept a `run_id` and have zero access to the live pipeline store, guaranteeing that prototype features cannot contaminate live Tier 1 attribution numbers.

### 2.3 State Ownership & Concurrency

- **Backend owns**: Pipeline run lifecycle, stage outputs, uploaded datasets, computed anomaly and match scores. State is stored on disk under `data/runs/{run_id}/` and `data/uploads/{run_id}/`.
- **In-flight Deduplication**: `_active_runs` with a thread-safe `threading.Lock()` prevents re-submitting duplicate runs for the same `run_id` (returns HTTP 409).
- **Frontend owns**: Active sidebar tab, layer visibility toggles, compare-view toggle, highlighted vessel selection, timeline scrubber position, and sidebar collapse state.
- **Stale-Run Recovery**: If the backend restarts or a `run_id` is evicted (HTTP 404), the frontend resets stale run state and displays an actionable banner prompting the user to reload the demo scenario or re-upload datasets.

---

## 3. Folder / File Structure

```
slicktrace/
├── Dockerfile                          # Multi-stage production container (Node 20 Vite build + Python 3.11 FastAPI)
├── DEPLOYMENT_GUIDE.md                 # Complete guide for Hugging Face, Render, Vercel, and Cloudflare Tunnel
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, CORS, static SPA mount (/), /api/health
│   │   ├── config.py                   # Paths, thresholds (72h age, top-N, upload limits)
│   │   ├── api/
│   │   │   ├── datasets.py             # POST /datasets/{type}, POST /datasets/load-demo, validation
│   │   │   ├── pipeline.py             # POST /pipeline/run, POST /pipeline/simulate
│   │   │   ├── status.py               # GET /pipeline/status, /pipeline/slick, /pipeline/shortlist
│   │   │   ├── results.py              # GET /results/{run_id}, GET /results/{run_id}/export
│   │   │   └── prototype.py            # GET /prototype/dark-ship, GET /prototype/oil-type
│   │   ├── pipeline/
│   │   │   ├── orchestrator.py         # 7-stage coordinator, error catching, background task wrappers
│   │   │   ├── stage0_perception.py    # SAR GeoTIFF/PNG → U-Net/threshold segmentation → slick polygon
│   │   │   ├── stage1_backward_drift.py# Reverse advection hindcast → origin spatiotemporal envelope
│   │   │   ├── stage2b_dark_ship.py    # Tier 2 prototype: point-target detection
│   │   │   ├── stage5_forward_drift.py # Forward advection simulation for shortlisted vessels
│   │   │   ├── stage5b_oil_type.py     # Tier 2 prototype: spectral oil-type classifier
│   │   │   └── stage6_matching.py      # IoU, centroid distance, orientation similarity → MatchScore
│   │   ├── models/
│   │   │   ├── unet.py                 # PyTorch U-Net architecture definition
│   │   │   ├── unet_weights.pt         # Pretrained model weights
│   │   │   └── anomaly_weights.py      # Multi-factor anomaly scoring (blackout, speed, route DTW, draft)
│   │   ├── schemas/
│   │   │   ├── pipeline_status.py      # 7-stage status schema (StageName, STAGE_NAMES, PipelineStatus)
│   │   │   ├── slick_polygon.py        # SlickPolygon schema
│   │   │   ├── shortlist.py            # Shortlist, Candidate, PositionAtEvent schemas
│   │   │   └── ranked_suspects.py      # RankedSuspects, RankedVessel schemas
│   │   └── services/
│   │       ├── ais_loader.py           # AIS CSV ingestion, bounding box filter, corridor/vessel filtering
│   │       ├── drift_engine.py         # OpenDrift wrapper with memory-aware NumPy advection fallback
│   │       └── run_store.py            # Filesystem persistence keyed by run_id
│   ├── data/
│   │   ├── synthetic/                  # Pre-packaged benchmark fixtures (SAR, AIS, wind, current, scenario.json)
│   │   ├── uploads/{run_id}/           # Raw uploaded datasets per run
│   │   └── runs/{run_id}/              # Generated artifacts per stage (slick_polygon, shortlist, etc.)
│   ├── tests/
│   │   ├── test_api.py                 # API endpoint tests
│   │   ├── test_drift_engine.py        # Advection engine tests
│   │   ├── test_orchestrator.py        # End-to-end pipeline execution tests
│   │   ├── test_stage0_perception.py   # Segmentation tests
│   │   ├── test_stage4_anomaly.py      # Anomaly scoring tests
│   │   └── test_stage6_matching.py     # Footprint verification tests
│   └── requirements.txt                # Pinned backend dependencies
│
├── frontend/
│   ├── vercel.json                     # Vercel SPA routing and proxy config for decoupled deployment
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx                    # React DOM root
│   │   ├── App.tsx                     # Main layout shell, connection health banner, tab viewports
│   │   ├── api/
│   │   │   └── client.ts               # Typed fetch client for all backend endpoints
│   │   ├── state/
│   │   │   ├── pipelineStore.ts        # Zustand store: uploads, continuous polling, tab switching, recovery
│   │   │   └── uiStore.ts              # Zustand store: active tab, layer toggles, split view, collapse
│   │   ├── types/
│   │   │   └── contracts.ts            # TypeScript interfaces matching backend Pydantic schemas
│   │   └── components/
│   │       ├── sidebar/
│   │       │   └── Sidebar.tsx         # Collapsible icon-rail navigation (Verdict, Datasets, Pipeline, Shortlist)
│   │       ├── layout/
│   │       │   ├── TopBar.tsx          # Status indicators, case metadata, quick actions
│   │       │   └── BottomPanel.tsx     # Live pipeline metrics, suspect counter, simulate trigger button
│   │       ├── tabs/
│   │       │   ├── InputTab.tsx        # Upload cards + "⚡ Load Demo Scenario" benchmark button
│   │       │   ├── PipelineTab.tsx     # 7-stage vertical stepper, progress %, failure error alerts
│   │       │   ├── SuspectsTab.tsx     # Pre-simulation shortlist cards with AnomalyScore breakdown
│   │       │   └── OutputTab.tsx       # Post-simulation ranked suspects, MatchScore badges, export
│   │       └── map/
│   │           ├── MapCanvas.tsx       # Leaflet map container with auto-fit bounds
│   │           └── layers/
│   │               ├── SlickLayer.tsx          # Observed slick polygon layer
│   │               ├── OriginEnvelopeLayer.tsx # Reverse drift origin envelope layer
│   │               ├── AISTrackLayer.tsx       # AIS vessel trajectory tracks
│   │               ├── ReleasePointLayer.tsx   # Candidate release points
│   │               ├── SimulatedDriftLayer.tsx # Forward simulated drift footprints
│   │               └── DarkShipLayer.tsx       # Tier 2 dark-ship detection overlay
│
└── docs/
    ├── architecture.md
    ├── design.md
    ├── phases.md
    ├── prd.md
    └── rules.md
```

---

## 4. Tech Stack (Full)

| Layer | Technology | Purpose & Notes |
|---|---|---|
| SAR/EO Imagery | Sentinel-1 (SAR) GeoTIFF/PNG | Primary input for slick detection |
| Segmentation Engine | PyTorch U-Net + PIL / Rasterio | Deep learning mask extraction with threshold-based fallback |
| Reverse Drift (Hindcast) | OpenDrift (`OpenOil`) / NumPy Engine | Reverse advection to compute probable origin envelope |
| AIS Processing | Pandas, GeoPandas, Shapely | Spatiotemporal corridor filtering and track extraction |
| Anomaly Scoring | Custom multi-factor rule model | Computes `AnomalyScore [0,1]` (blackout, speed, route, draft) |
| Forward Drift (Forecast) | OpenDrift (`OpenOil`) / NumPy Engine | Forward advection of candidate release points to observation time |
| Spatial Verification | Shapely, SciPy (ConvexHull) | IoU, centroid distance, orientation match → `MatchScore` |
| Dark-Ship Detection (Tier 2) | CFAR / point detector (cached) | Pre-computed benchmark demonstration |
| Oil Fingerprinting (Tier 2) | Spectral classifier (cached) | Pre-computed benchmark demonstration |
| Backend Framework | FastAPI (Python 3.11+) | Async REST API, synchronous BackgroundTasks, OpenAPI |
| Frontend Framework | React 18 + Vite + TypeScript | High-performance SPA with strict typing |
| Mapping Engine | Leaflet + react-leaflet | Vector polygons, polylines, circle markers, bounding box fitting |
| State Management | Zustand | Dual stores: `pipelineStore.ts` (data/polling) & `uiStore.ts` (UI) |
| Styling & Theme | Vanilla CSS + Tailwind Tokens | Custom dark-ocean HUD styling (`st-*` component classes) |
| Production Container | Multi-stage Dockerfile | `node:20-slim` builds frontend; Python 3.11 serves SPA & API |
| Cloud Hosting Options | Hugging Face Spaces (16GB RAM), Render (512MB RAM), Vercel | Zero-cost deployment pathways documented in `DEPLOYMENT_GUIDE.md` |

---

## 5. API Surface

| Method | Path | Description / Query Parameters |
|---|---|---|
| `GET` | `/api/health` | Service health check; returns `{"status": "ok"}` |
| `POST` | `/api/datasets/{type}` | Upload `wind`, `current`, `sar`, or `ais`. Returns status, bbox, date_range |
| `POST` | `/api/datasets/load-demo` | Loads all 4 pre-packaged synthetic benchmark datasets into a new `run_id` |
| `POST` | `/api/pipeline/run` | Body: `{"run_id": "..."}`. Executes Stages 0–4 asynchronously |
| `GET` | `/api/pipeline/status?run_id=` | Returns 7-stage execution status (`PipelineStatus` schema) |
| `GET` | `/api/pipeline/slick?run_id=` | Returns detected slick polygon GeoJSON/JSON (`SlickPolygon` schema) |
| `GET` | `/api/pipeline/origin-envelope?run_id=` | Returns Stage 1 reverse drift envelope polygon and time window |
| `GET` | `/api/pipeline/shortlist?run_id=` | Returns Stage 4 shortlist candidates (`Shortlist` schema) |
| `POST` | `/api/pipeline/simulate` | Body: `{"run_id": "..."}`. Executes Stages 5–6 asynchronously |
| `GET` | `/api/pipeline/simulated-footprints?run_id=` | Returns forward simulated polygons for shortlisted candidates |
| `GET` | `/api/results/{run_id}` | Returns final suspect ranking (`RankedSuspects` schema) |
| `GET` | `/api/results/{run_id}/export` | Downloads `.zip` archive containing GeoJSON slick and all stage JSONs |
| `GET` | `/api/prototype/dark-ship` | Returns cached Tier 2 dark-ship detection response |
| `GET` | `/api/prototype/oil-type` | Returns cached Tier 2 spectral oil-type fingerprint response |

---

## 6. Data Contracts (Source of Truth)

These schemas match between `backend/app/schemas/*.py` and `frontend/src/types/contracts.ts`:

### 6.1 `pipeline_status.json` (7 Stages)
```json
{
  "run_id": "string",
  "stages": [
    {"name": "perception", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "backward_drift", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "ais_ingestion", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "candidate_filtering", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "anomaly_scoring", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "drift_simulation", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "verification_matching", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"}
  ]
}
```

### 6.2 `slick_polygon.json`
```json
{
  "polygon": [[lat, lon], ...],
  "detection_time": "2024-09-14T18:00:00Z",
  "bbox": [minLat, minLon, maxLat, maxLon],
  "area_km2": 4.12,
  "elongation_ratio": 2.45,
  "age_estimate_hours": 12.0,
  "weathering_validity": true,
  "fallback_used": false
}
```

### 6.3 `shortlist.json`
```json
{
  "candidates": [
    {
      "mmsi": "367123450",
      "vessel_name": "PACIFIC TITAN",
      "vessel_type": "tanker",
      "operator": "Pacific Maritime",
      "flag": "US",
      "destination": "LOS ANGELES",
      "position_at_event": {"lat": 33.72, "lon": -118.25, "time": "2024-09-14T10:30:00Z"},
      "anomaly_score": 0.82,
      "anomaly_breakdown": {"blackout": 0.40, "speed": 0.22, "route": 0.15, "draft": 0.05},
      "candidate_release_points": [{"lat": 33.72, "lon": -118.25, "time": "2024-09-14T10:30:00Z"}]
    }
  ]
}
```

### 6.4 `ranked_suspects.json`
```json
{
  "ranking": [
    {
      "mmsi": "367123450",
      "vessel_name": "PACIFIC TITAN",
      "match_score": 0.88,
      "iou": 0.74,
      "centroid_distance_km": 0.42,
      "orientation_match": 0.91,
      "rank": 1
    }
  ]
}
```

---

*Any change to these contracts must be applied to both backend schemas and frontend types simultaneously.*

