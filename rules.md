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
| Drift simulation | OpenDrift (`OilDrift`/`OpenOil` module) | Hand-rolled advection math — the PS explicitly expects a real drift model |
| Geo ops | geopandas, shapely | Rolling your own polygon/IoU math |
| Tabular/AIS handling | pandas | — |
| Dark-ship prototype detector | CFAR (classical, `scipy`/`numpy`) or a small CNN | A full YOLO/Detectron pipeline — overkill for a cached prototype |
| Oil-type prototype classifier | scikit-learn or a small CNN | Large pretrained hyperspectral models you can't explain in Q&A |
| Background task execution | FastAPI `BackgroundTasks` or a simple in-process queue | Celery/Redis — unnecessary infra for a single-case demo |
| Validation | pydantic (schemas already defined in `architecture.md`) | Manual dict-shape checking |

### Frontend (TypeScript/React)
| Purpose | Use | Do not use |
|---|---|---|
| Map | Leaflet + react-leaflet | Mapbox GL (token/billing dependency — only switch if the team explicitly signs up for it) |
| State | Zustand | Redux (unjustified boilerplate for this app's size) |
| Styling | Tailwind CSS | Inline styles as the primary method; a component-library that fights the custom layout (e.g. Material UI's opinionated shell) |
| Charts | Recharts | D3 from scratch — no time budget for it here |
| HTTP | native `fetch` wrapped in `src/api/client.ts` | axios (adds a dependency for no capability gain here) |

### Hard bans, no exceptions
- No hardcoded API keys, tokens, or credentials in source — `.env` + `.env.example`, `.env` gitignored.
- No client-side storage of uploaded satellite/AIS data beyond the current session's in-memory state — the backend's `data/uploads/{run_id}/` is the only persistence layer.
- No pulling in a UI kit that ships its own map component (fights Leaflet, bloats bundle).
- No swapping PyTorch/TensorFlow mid-project once Stage 0 is implemented in one of them.

---

## 2. Error Handling

**Principle: every failure state must be visible in the UI, never silent.** A hackathon demo that fails silently looks broken; one that fails with a clear message looks like a real product with real edge-case handling.

### Backend
- Every pipeline stage function returns a discriminated result: `{"status": "success", "data": ...}` or `{"status": "failed", "stage": "...", "reason": "..."}` — never raises an unhandled exception into the orchestrator.
- `orchestrator.py` catches per-stage failures, marks that stage `"failed"` in `pipeline_status.json` with a human-readable `detail`, and **halts downstream stages** rather than propagating garbage forward (e.g., don't run Stage 5 forward-sim on a Stage 4 shortlist that came from a failed Stage 2/3 filter).
- Dataset upload validation (`POST /api/datasets/{type}`) rejects malformed files immediately with a specific reason (`"missing timestamp column"`, `"CRS not recognized"`, `"file empty"`) — never a bare 500.
- Long-running stages (Stage 1, Stage 5 drift sims) get a timeout; on timeout, mark the stage `"failed"` with `detail: "simulation exceeded time budget"` rather than hanging the poll loop indefinitely.

### Frontend
- Every API call in `src/api/client.ts` handles the failure branch explicitly — a failed fetch renders an inline error state in the relevant tab/panel, not a blank panel or an uncaught console error.
- Polling (`pipelineStore.ts`) has a max-retry/backoff — if `/pipeline/status` fails repeatedly, surface a visible "connection lost, retrying…" banner rather than failing silently and leaving stale progress bars on screen.
- Disabled-button states (e.g. "Simulate" before a shortlist exists) always carry a tooltip explaining *why*, per the dashboard spec — never a disabled button with no explanation.

---

## 3. Boundaries for the AI Agent (Antigravity)

These are hard rules for whatever builds this, human or AI. Violating them undermines the project's own honesty framing (§7 of `approach_3_-_oil_spill.pdf`, "Known Gaps") — the whole pitch is that this tool doesn't overclaim, so the build process can't either.

1. **Never fabricate data to make a demo look better.** If real AIS/SAR data isn't available for a code path, use clearly-labeled synthetic data (per `architecture.md`'s data provenance tags) — never silently substitute fake numbers into what's presented as a real pipeline output.
2. **Never present a Tier 2 (prototype) feature as live inference.** Dark-ship detection and oil-type fingerprinting must always route through the cached `/api/prototype/*` endpoints, never through the live `run_id` pipeline. If asked to "make it dynamic" for Tier 2, push back and confirm that's actually intended — it contradicts the PRD's explicit framing.
3. **Never collapse the two output scores into one number.** `AnomalyScore` and `MatchScore` stay visible and separate everywhere they're displayed — combining them into a single opaque "confidence %" anywhere in the UI is a PRD violation (see `prd.md` §6, F6).
4. **Never change a data contract shape without updating both sides in the same change.** `backend/app/schemas/*.py` and `frontend/src/types/contracts.ts` are one seam — a PR/change that touches one without the other is incomplete, not done.
5. **Don't add scope beyond `prd.md` without flagging it.** No new tabs, no multi-case support, no auth — if a task seems to require one of these, stop and surface that rather than quietly building it (this is a non-goal per PRD §5).
6. **Don't hide known limitations in code comments only.** Anything that's a stated tradeoff (rule-based anomaly scoring, uncalibrated Fay-spreading coefficients, synthetic-if-needed AIS) should be reflected in a user-visible label/tooltip in the dashboard, not just a code comment nobody in the demo will read.
7. **Ask before introducing a new external dependency** not in the §1 allow-list, and note the reason if one gets added.
8. **Keep compute bounded per the architecture doc**: never write a code path that runs Stage 1 or Stage 5 drift simulation against anything other than the post-filter/post-shortlist candidate set. This is a stated design constraint (PRD §9), not a performance nice-to-have.
9. **When uncertain about a physical/oceanographic modeling choice** (e.g. weathering coefficients, wind-window thresholds), use the literature defaults already specified in `approach_3_-_oil_spill.pdf` rather than inventing new ones — consistency with the source doc matters more than marginal accuracy gains for this build.

---

## 4. Code Style / Conventions

- **Python**: type-hint everything in `app/pipeline/` and `app/schemas/` (these are the parts most likely to be read/debugged under demo-day time pressure); `black` + `ruff` for formatting/linting.
- **TypeScript**: strict mode on; no `any` in `src/types/contracts.ts` (that file is the whole point of having contracts).
- **Naming**: stage modules and their outputs use the same vocabulary as `prd.md`/`architecture.md` (`AnomalyScore`, `MatchScore`, `shortlist`, `ranked_suspects`) — no renaming mid-build; it breaks the traceability back to the PS.
- **Commits**: one stage or one tab per commit where feasible — makes it possible to demo an incremental build if something breaks late.
- **Tests**: every stage function in `app/pipeline/` gets at least one test against the fixtures in `backend/tests/fixtures/` before it's wired into the orchestrator — untested stages are not "done."

---

*Next file: `phases.md` — build phases, sequencing, what "dashboard, login, and all" ships in which phase.*
