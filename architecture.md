# architecture.md — SlickTrace

**App flow, folder/file structure, tech stack.**
Read `prd.md` first — this document implements it, doesn't redefine it.

---

## 1. Stack Decision (and why)

**Frontend: React (Vite + TypeScript) + Leaflet, not Streamlit.**

The dashboard spec requires: a collapsible icon-rail sidebar with 4 independently-stateful panels, an always-visible map underneath whichever panel is open, floating circular tool buttons pinned to a fixed screen position, a split/overlay compare mode between two map layers, and a scrubbable timeline with play/pause. Streamlit's layout model (top-to-bottom reruns, no persistent floating elements, no real split-pane map compare) fights all of that. React gets you real component state, a real map library, and a UI that will actually resemble the reference screenshot. This costs more setup time than Streamlit — budget for it explicitly in `phases.md`.

**Backend: Python FastAPI.** Every ML/geospatial library in the PS's tech stack (OpenDrift, U-Net via PyTorch, geopandas, shapely) is Python-only — the backend is not a language choice, it's a constraint. FastAPI over Flask because you need async endpoints for long-running stages (drift simulation) plus a clean OpenAPI contract the frontend can codegen against if time allows.

**Communication: REST + polling, not WebSockets, for the hackathon build.** `pipeline_status.json` is small and stages are long-running (seconds to low minutes each) — polling every 1–2s is simpler to demo reliably than a WebSocket connection that can silently drop mid-presentation. Note this as a stated tradeoff, not an oversight, if judges ask.

**Map library: Leaflet, not Mapbox GL.** No API key/token dependency to manage live during a demo; sufficient for polygon/track/marker layers at the zoom levels this tool needs. Swap to Mapbox GL only if the team wants the reference screenshot's exact visual polish and has time to spare.

---

## 2. App Flow

### 2.1 High-level sequence (single case, no auth, matches PRD non-goals)

```
1. User opens dashboard → Input tab active by default, map empty with basemap only.
2. User uploads/attaches: wind data, ocean current data, SAR image (+polygon), AIS data.
   → Each upload hits POST /api/datasets/{type}, backend validates format,
     returns status (uploaded/invalid) + inferred bbox/date range.
3. All 4 present → "Run pipeline" button enables.
4. User clicks "Run pipeline" → POST /api/pipeline/run
   → Backend kicks off Stages 0–4 as a background task, returns a run_id immediately.
5. Frontend polls GET /api/pipeline/status?run_id=... every ~1.5s
   → Updates Pipeline tab (per-stage progress) + bottom panel (live numbers)
   → Updates map as each stage's output becomes available:
       Stage 0 done → slick polygon layer appears
       Stage 1 done → origin envelope layer appears
       Stage 2-3 done → AIS candidate tracks appear
       Stage 4 done → Shortlist tab populates, tracks color-coded by anomaly score
6. Shortlist ready → Results tab's "Simulate" button enables (was disabled w/ tooltip).
7. User clicks "Simulate" → POST /api/pipeline/simulate
   → Backend runs Stage 5 (forward sim, top-N only) + Stage 6 (matching/ranking)
     as a background task tied to the same run_id.
8. Frontend polls same status endpoint → stages 5-6 animate → on completion,
   GET /api/results/{run_id} → Results tab populates with ranked_suspects.json shape.
9. User can toggle "View simulated map" → split/overlay compare view
   (observed slick layer vs. simulated footprint layer, same map instance).
10. Download action → GET /api/results/{run_id}/export → GeoJSON/CSV bundle.
```

### 2.2 Tier 2 (prototype) flow — deliberately separate

Dark-ship detection and oil-type fingerprinting are **not** part of the sequence above. They are toggles in the UI that, when switched on, call `GET /api/prototype/dark-ship` and `GET /api/prototype/oil-type`, which return a **pre-computed, cached JSON response** for the demo dataset — no live model runs. This is a hard architectural boundary, not just a labeling choice: keeping them on separate endpoints that never touch the live pipeline run_id means there's no risk of a prototype path silently affecting the "live" Tier 1 numbers.

### 2.3 State ownership

- **Backend owns**: pipeline run state, all stage outputs, uploaded files, computed scores. Source of truth is the filesystem/DB keyed by `run_id`, not frontend memory.
- **Frontend owns**: which sidebar tab is active, which map layers are toggled on, split-view state, timeline scrubber position, sidebar collapsed/expanded. Purely presentational state — never re-derives pipeline results, only fetches and renders them.

---

## 3. Folder / File Structure

```
slicktrace/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint, CORS, router mounting
│   │   ├── api/
│   │   │   ├── datasets.py             # POST /datasets/{type}, upload + validation
│   │   │   ├── pipeline.py             # POST /pipeline/run, /pipeline/simulate
│   │   │   ├── status.py               # GET /pipeline/status
│   │   │   ├── results.py              # GET /results/{run_id}, /results/{run_id}/export
│   │   │   └── prototype.py            # GET /prototype/dark-ship, /prototype/oil-type
│   │   ├── pipeline/
│   │   │   ├── stage0_perception.py    # SAR/EO → U-Net → slick polygon
│   │   │   ├── stage1_backward_drift.py# OpenDrift reversed
│   │   │   ├── stage2_3_filter.py      # AIS spatiotemporal + vessel-type filter
│   │   │   ├── stage4_anomaly.py       # blackout/speed/route/draft scoring
│   │   │   ├── stage5_forward_drift.py # OpenDrift forward, per shortlisted vessel
│   │   │   ├── stage6_matching.py      # IoU/centroid/orientation → MatchScore, ranking
│   │   │   ├── stage2b_dark_ship.py    # prototype: CFAR/CNN point detector
│   │   │   ├── stage5b_oil_type.py     # prototype: spectral oil-type classifier
│   │   │   └── orchestrator.py         # sequences stages, updates run status, background tasks
│   │   ├── models/
│   │   │   ├── unet.py                 # segmentation model def + weights loader
│   │   │   └── anomaly_weights.py      # hand-tuned weight constants, documented
│   │   ├── schemas/
│   │   │   ├── slick_polygon.py        # pydantic model mirroring slick_polygon.json
│   │   │   ├── shortlist.py            # pydantic model mirroring shortlist.json
│   │   │   ├── ranked_suspects.py      # pydantic model mirroring ranked_suspects.json
│   │   │   └── pipeline_status.py      # pydantic model mirroring pipeline_status.json
│   │   ├── services/
│   │   │   ├── ais_loader.py           # MarineCadastre / synthetic AIS ingestion
│   │   │   ├── drift_engine.py         # thin wrapper around OpenDrift/OilDrift config
│   │   │   └── run_store.py            # filesystem/DB persistence keyed by run_id
│   │   └── config.py                   # paths, thresholds (72h age, 1.5-10 m/s wind window, top-N)
│   ├── data/
│   │   ├── uploads/{run_id}/           # raw uploaded datasets
│   │   ├── cache/prototype/            # pre-computed Tier 2 demo outputs
│   │   └── runs/{run_id}/              # per-stage output JSON, matches the 4 contracts
│   ├── tests/
│   │   ├── test_stage0_perception.py
│   │   ├── test_stage4_anomaly.py
│   │   ├── test_stage6_matching.py
│   │   └── fixtures/                   # small sample SAR crop, sample AIS csv
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                     # layout shell: sidebar + map + bottom panel + right tools
│   │   ├── api/
│   │   │   └── client.ts               # typed fetch wrappers for every backend endpoint
│   │   ├── state/
│   │   │   ├── pipelineStore.ts        # run_id, stage statuses, polling logic (zustand)
│   │   │   └── uiStore.ts              # active tab, layer toggles, split-view, sidebar collapsed
│   │   ├── components/
│   │   │   ├── sidebar/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── TabResults.tsx      # Tab 1
│   │   │   │   ├── TabInput.tsx        # Tab 2
│   │   │   │   ├── TabPipeline.tsx     # Tab 3
│   │   │   │   └── TabShortlist.tsx    # Tab 4
│   │   │   ├── map/
│   │   │   │   ├── MapCanvas.tsx       # Leaflet instance + layer composition
│   │   │   │   ├── layers/
│   │   │   │   │   ├── SlickLayer.tsx
│   │   │   │   │   ├── AISTrackLayer.tsx
│   │   │   │   │   ├── ReleasePointLayer.tsx
│   │   │   │   │   └── SimulatedDriftLayer.tsx
│   │   │   │   └── CompareView.tsx     # split/overlay-slider observed vs. simulated
│   │   │   ├── bottompanel/
│   │   │   │   ├── StatsStrip.tsx
│   │   │   │   └── TimelineScrubber.tsx
│   │   │   └── righttools/
│   │   │       └── FloatingToolStack.tsx  # zoom, reset, maximize, annotate, screenshot
│   │   ├── types/
│   │   │   └── contracts.ts            # TS interfaces mirroring the 4 JSON contracts
│   │   └── styles/                     # see design.md for tokens
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
│
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── rules.md
│   ├── phases.md
│   └── design.md
│
└── README.md
```

---

## 4. Tech Stack (full)

| Layer | Tool / Library | Notes |
|---|---|---|
| SAR/EO imagery | Sentinel-1 (SAR), Sentinel-2 (EO) via Copernicus Open Access Hub / Google Earth Engine | Free, primary data source |
| Slick segmentation | U-Net (PyTorch) | Train on Zenodo Sentinel-1 SAR Oil Spill Dataset |
| Dark-ship detector (prototype) | CFAR (classical) or lightweight CNN | Run once, cache result for demo |
| AIS data | MarineCadastre (accessais) real archives, or synthetic generator | Prefer real data; pick demo region for coverage |
| Ocean currents | Copernicus Marine Service (CMEMS) or HYCOM reanalysis | Feeds Stage 1 and Stage 5 |
| Wind data | ECMWF ERA5 reanalysis | Same |
| Wave/Stokes drift | ERA5 wave fields | Optional refinement |
| Drift/transport simulation | OpenDrift (OilDrift/OpenOil module) | Reversed for Stage 1, forward for Stage 5 |
| Oil-type classifier (prototype) | sklearn or small CNN on Sentinel-2 bands | Run once, cache result for demo |
| Backend framework | FastAPI (Python 3.11+) | Async endpoints, background tasks for long stages |
| Geo/data processing | pandas, geopandas, shapely | Polygon ops, AIS track handling |
| Anomaly scoring | Hand-weighted rule-based sum (Python) | Documented as stand-in for future logistic regression/GBM |
| Frontend framework | React 18 + Vite + TypeScript | |
| Styling | Tailwind CSS | Tokens defined in `design.md` |
| Map | Leaflet + react-leaflet | No API key dependency for the demo |
| State management | Zustand | Lightweight, no boilerplate for a single-case app |
| Charts (mini stat rows) | Recharts | Sub-score bars, confidence badges |
| Dev/hosting | Local or lightweight cloud (Render/Vercel) | No production infra needed for a hackathon demo |

---

## 5. API Surface (contract between frontend and backend)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/datasets/{type}` | Upload one of `wind` \| `current` \| `sar` \| `ais`; returns status + inferred bbox/date range |
| `POST` | `/api/pipeline/run` | Kick off Stages 0–4 (requires all 4 datasets); returns `run_id` |
| `GET` | `/api/pipeline/status?run_id=` | Returns `pipeline_status.json` shape; poll target |
| `GET` | `/api/pipeline/slick?run_id=` | Returns `slick_polygon.json` once Stage 0 done |
| `GET` | `/api/pipeline/shortlist?run_id=` | Returns `shortlist.json` once Stage 4 done |
| `POST` | `/api/pipeline/simulate` | Kick off Stages 5–6 for an existing `run_id` |
| `GET` | `/api/results/{run_id}` | Returns `ranked_suspects.json` once Stage 6 done |
| `GET` | `/api/results/{run_id}/export` | GeoJSON/CSV download bundle |
| `GET` | `/api/prototype/dark-ship` | Cached Tier 2 response, no `run_id` needed |
| `GET` | `/api/prototype/oil-type` | Cached Tier 2 response, no `run_id` needed |

---

## 6. Data Contracts (full — source of truth for both sides)

```json
// slick_polygon.json
{
  "polygon": [[lat, lon], ...],
  "detection_time": "ISO8601",
  "bbox": [minLat, minLon, maxLat, maxLon],
  "area_km2": 0.0,
  "elongation_ratio": 0.0,
  "age_estimate_hours": 0.0
}

// shortlist.json
{
  "candidates": [
    {
      "mmsi": "string",
      "vessel_name": "string",
      "vessel_type": "tanker|cargo|bunkering",
      "operator": "string",
      "flag": "string",
      "destination": "string",
      "position_at_event": {"lat":0,"lon":0,"time":"ISO8601"},
      "anomaly_score": 0.0,
      "anomaly_breakdown": {"blackout":0,"speed":0,"route":0,"draft":0},
      "candidate_release_points": [{"lat":0,"lon":0,"time":"ISO8601"}]
    }
  ]
}

// ranked_suspects.json
{
  "ranking": [
    {
      "mmsi": "string",
      "vessel_name": "string",
      "match_score": 0.0,
      "iou": 0.0,
      "centroid_distance_km": 0.0,
      "orientation_match": 0.0,
      "rank": 1
    }
  ]
}

// pipeline_status.json
{
  "stages": [
    {"name": "perception", "status": "pending|running|done|failed", "progress_pct": 0, "detail": "string"},
    {"name": "ais_ingestion", "status": "pending", "progress_pct": 0, "detail": "string"},
    {"name": "candidate_filtering", "status": "pending", "progress_pct": 0, "detail": "string"},
    {"name": "anomaly_scoring", "status": "pending", "progress_pct": 0, "detail": "string"},
    {"name": "drift_simulation", "status": "pending", "progress_pct": 0, "detail": "string"},
    {"name": "verification_matching", "status": "pending", "progress_pct": 0, "detail": "string"}
  ]
}
```

These four shapes are the seam between frontend and backend — `backend/app/schemas/` and `frontend/src/types/contracts.ts` must stay in lockstep. Any pipeline change that alters an output shape updates both.

---

*Next file: `rules.md` — what to use, what to avoid, error handling, boundaries for the AI agent building this.*
