# rules.md — SlickTrace

**Binding constraints for whoever/whatever builds this — including an AI coding agent (Antigravity).**
If `architecture.md` says *what* and *where*, this file says *how* and *how not to*.

---

## 1. Library Allow-List (use these, nothing else without a reason logged)

### Backend (Python)
| Purpose | Use | Do not use |
|---|---|---|
| Web framework | FastAPI | Flask, Django (no auth/ORM-heavy needs here) |
| Segmentation model | PyTorch | TensorFlow/Keras (pick one, don't mix — PyTorch has better OpenDrift-adjacent tooling) |
| GeoTIFF & Image I/O | Rasterio, Pillow (PIL fallback) | Manual binary slicing or unvalidated image loaders |
| MetOcean Forcing I/O | xarray, netCDF4 | Manual binary NetCDF parsers |
| Drift simulation | OpenDrift (`OpenOil`) with environment-aware NumPy fallback | Hand-rolled advection math *without* fallback labeling; never spawn `ProcessPoolExecutor` forks in memory-constrained cloud tiers (<1GB RAM) |
| Geo ops | GeoPandas, Shapely | Rolling your own polygon/IoU math |
| Tabular/AIS handling | Pandas | — |
| Dark-ship prototype detector | CFAR (classical, `scipy`/`numpy`) or a small CNN | A full YOLO/Detectron pipeline — overkill for a cached prototype |
| Oil-type prototype classifier | scikit-learn or a small CNN | Large pretrained hyperspectral models you can't explain in Q&A |
| Background task execution | FastAPI `BackgroundTasks` (synchronous `def` workers) | Async functions for CPU-heavy tasks (blocks event loop); Celery/Redis (unnecessary infra) |
| Validation | Pydantic (schemas in `app/schemas/`) | Manual dict-shape checking |

### Frontend (TypeScript/React)
| Purpose | Use | Do not use |
|---|---|---|
| Map | Leaflet + react-leaflet | Mapbox GL (token/billing dependency — only switch if the team explicitly signs up for it) |
| State | Zustand (`pipelineStore.ts`, `uiStore.ts`) | Redux (unjustified boilerplate for this app's size) |
| Styling | Vanilla CSS + Tailwind Tokens (`st-*` classes) | Heavy UI component libraries (MUI, AntD) that fight custom map layout |
| Charts / Telemetry | Custom SVG or Recharts | D3 from scratch — no time budget for it here |
| HTTP | Native `fetch` wrapped in `src/api/client.ts` | Axios (adds dependency for zero capability gain) |

### Hard bans, no exceptions
- No hardcoded API keys, tokens, or credentials in source — `.env` + `.env.example`, `.env` gitignored.
- No client-side storage of uploaded satellite/AIS data beyond the current session's in-memory state — backend `data/uploads/{run_id}/` is the only persistence layer.
- No pulling in a UI kit that ships its own map component (fights Leaflet, bloats bundle).
- No swapping PyTorch/TensorFlow mid-project once Stage 0 is implemented.

---

## 2. Error Handling & Concurrency Rules

**Principle: every failure state must be visible in the UI, never silent.** A hackathon demo that fails silently looks broken; one that fails with a clear message looks like a real product with real edge-case handling.

### Backend
- **Discriminated Stage Returns**: Every pipeline stage returns `{"status": "success", "data": ...}` or `{"status": "failed", "stage": "...", "reason": "..."}` — never raises an unhandled exception into the orchestrator.
- **Halt Downstream on Failure**: `orchestrator.py` catches per-stage failures, marks that stage `"failed"` in `pipeline_status.json` with a human-readable `detail`, and **halts downstream stages** rather than propagating invalid intermediate state forward.
- **FastAPI Event Loop Safety**: All CPU-bound background workers dispatched via `BackgroundTasks` must be synchronous (`def _run_and_release()`, not `async def`), so FastAPI executes them in threadpool workers and leaves the asyncio event loop responsive to health checks and polling requests.
- **In-flight Deduplication**: Concurrent submissions to `/api/pipeline/run` or `/api/pipeline/simulate` for an already-active `run_id` must return HTTP 409 Conflict using thread-safe locking (`threading.Lock()`).
- **Upload Validation**: `POST /api/datasets/{type}` validates magic bytes and structural headers immediately, returning descriptive error messages (`"missing timestamp column"`, `"CRS not recognized"`, `"file empty"`) with HTTP 400 — never a bare 500.
- **Cloud Memory Safety**: On memory-constrained tiers (Render 512MB), full OpenDrift is disabled (`_disable_opendrift = True`) to prevent kernel OOM `SIGKILL`, engaging vector advection with transparent `"fallback_used": True` disclosure.

### Frontend
- **Failure Branch Handling**: Every API call in `src/api/client.ts` handles the failure branch explicitly.
- **Continuous Polling Loop**: `pipelineStore.ts` runs an active polling loop (1.0s interval) checking for stage completion and errors.
- **Stale-Run Recovery (404 Handling)**: If `/api/pipeline/status` returns HTTP 404 (e.g. cloud container sleep/restart), the frontend clears stale state, auto-navigates to Datasets (`input`) tab, and displays an actionable notice: *"Active run has expired or server restarted. Please click '⚡ Load Demo Scenario' or re-upload datasets to proceed."*
- **Persistent Connection Banner**: If `/api/health` fails repeatedly, a top-level banner (`"Connection lost, retrying…"`) informs the user without throwing uncaught exceptions.
- **Disabled Controls with Tooltips**: Any disabled action button (e.g. "Run Simulation" before shortlist generation) must render an explanatory hover tooltip explaining the unmet condition.

---

## 3. Boundaries for the AI Agent (Antigravity)

These are hard rules for whatever builds this, human or AI. Violating them undermines the project's own honesty framing (§7 of `approach_3_-_oil_spill.pdf`, "Known Gaps").

1. **Never fabricate data to make a demo look better.** If real AIS/SAR data isn't available for a code path, use clearly-labeled synthetic data (per `architecture.md`'s data provenance tags) — never silently substitute fake numbers into what's presented as a real pipeline output.
2. **Never present a Tier 2 (prototype) feature as live inference.** Dark-ship detection and oil-type fingerprinting must always route through the cached `/api/prototype/*` endpoints, never through the live `run_id` pipeline.
3. **Never collapse the two output scores into one number.** `AnomalyScore` and `MatchScore` stay visible and separate everywhere they're displayed — combining them into a single opaque "confidence %" anywhere in the UI is a PRD violation (see `prd.md` §6, F6).
4. **Never change a data contract shape without updating both sides in the same change.** `backend/app/schemas/*.py` and `frontend/src/types/contracts.ts` are one seam — a change that touches one without the other is incomplete, not done.
5. **Don't add scope beyond `prd.md` without flagging it.** No new tabs, no multi-case support, no auth — keep the investigative desktop HUD lean and robust.
6. **Don't hide known limitations in code comments only.** Anything that's a stated tradeoff (rule-based anomaly scoring, uncalibrated Fay-spreading coefficients, synthetic benchmark datasets, advection fallbacks) should be reflected in a user-visible badge or tooltip in the dashboard.
7. **Ask before introducing a new external dependency** not in the §1 allow-list, and note the reason if one gets added.
8. **Keep compute bounded per the architecture doc**: never write a code path that runs Stage 5 forward drift simulation against anything other than the top-N shortlist candidates (PRD §9).
9. **When uncertain about an oceanographic parameter**, use the literature defaults specified in `approach_3_-_oil_spill.pdf` rather than inventing arbitrary constants.
10. **Preserve the 1-Click Demo Pathway**: Never remove or break `POST /api/datasets/load-demo` or the UI's **"⚡ Load Demo Scenario"** button — evaluators require a friction-free evaluation route.
11. **Maintain Cloud Free-Tier Compatibility**: Do not introduce dependencies or memory footprints (>400MB) without verifying execution on 512MB RAM cloud environments (Render).

---

## 4. Code Style & Verification

- **Python**: Type hints required across `app/pipeline/`, `app/schemas/`, and `app/services/`. Pydantic models for validation. Formatting with `ruff`/`black`.
- **TypeScript**: Strict mode enabled; no `any` in `src/types/contracts.ts`.
- **Testing**: All pipeline stage functions must be covered by tests in `backend/tests/` running against fixtures in `backend/data/synthetic/`. Verify test suite passes with `pytest backend/tests`.
- **Frontend Build**: Verify production bundle compiles with zero errors via `npm run build` in `frontend/`.

---

*Together, `architecture.md`, `design.md`, `phases.md`, `prd.md`, and `rules.md` document the complete technical reality and operational constraints of SlickTrace.*

