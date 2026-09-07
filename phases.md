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

## Phase 0 — Scaffolding & Contracts

**Goal:** a running (empty) app, not a working one. Nobody writes pipeline logic yet.

**Backend**
- Repo/folder structure exactly as `architecture.md` §3.
- `pyproject.toml` / `requirements.txt` pinned to the `rules.md` §1 allow-list only.
- `app/schemas/*.py` — pydantic models for all four contracts (`slick_polygon`, `shortlist`, `ranked_suspects`, `pipeline_status`), copied verbatim in shape from `architecture.md` §6.
- `app/main.py` with CORS + router mounting; every endpoint in `architecture.md` §5 exists and returns **static fixture JSON** matching its schema (no real computation).
- `.env.example` committed; `.env` gitignored (rules.md hard ban).

**Frontend**
- Vite + React + TS scaffold, Tailwind configured, Zustand stores created (`pipelineStore.ts`, `uiStore.ts`) with empty/default state.
- `src/types/contracts.ts` — TS interfaces mirroring the same four shapes, strict mode on, no `any`.
- `src/api/client.ts` — typed fetch wrappers for every endpoint, **including the failure branch** (rules.md §2 frontend rules apply from commit one, not bolted on later).
- App shell: collapsible sidebar with 4 icon tabs (empty panels), map canvas (basemap only, no layers), bottom panel strip (static placeholder), right-edge floating tool stack (buttons present, wired to no-ops).

**Exit criteria**
- `npm run dev` + `uvicorn` both boot.
- All 4 tabs switch correctly, sidebar collapses/expands and remembers the active tab.
- Every panel, empty as it is, shows an explanatory empty state — never a blank div (PRD §8 success criterion, applies from day one).
- Contract types on both sides reviewed side-by-side and confirmed identical.

**If time is short:** this phase cannot be skipped or shortened — everything after depends on the contracts being locked first. Cutting corners here is the single biggest risk to the "one seam" rule (rules.md §3.4).

---

## Phase 1 — Stage 0 (Perception) + Tab 2 (Input) + Map's Slick Layer

**Goal:** first real pipeline output, first real map layer.

**Backend**
- `stage0_perception.py`: U-Net inference (PyTorch) on a SAR crop → binary mask → polygon (geopandas/shapely) → area, shape descriptors, age estimate.
- Look-alike rejection: wind-speed window (1.5–10 m/s) + shape/texture heuristic.
- `POST /api/datasets/{type}` implemented for real — validates format per type, rejects with a specific reason (rules.md §2: `"missing timestamp column"`, `"CRS not recognized"`, `"file empty"`), never a bare 500.
- Weathering-validity flag (age > 72h → downstream low-confidence tag) written into the output, not just logged.

**Frontend**
- Tab 2: 4 upload cards wired to real upload endpoint, status indicators (Not uploaded / Uploaded ✓ / Invalid ⚠), provenance tags, inferred bbox/date range display.
- Map: `SlickLayer.tsx` renders the real polygon once Stage 0 completes.
- Tab 3 (Pipeline): "Perception" stage now shows real progress/status instead of static fixture data; other 5 stages still show descriptions + "Upload data first."

**Exit criteria**
- A real SAR crop uploaded → real polygon appears on the map, with age/area/weathering-flag visible somewhere in the UI (not just in the API response).
- Invalid file upload → visible inline error in Tab 2, not a console error.

**If time is short:** ship with a smaller/pretrained U-Net or a coarser threshold-based segmentation as a documented fallback — **only if labeled as such**; this is a case for rules.md §3.1 (never present a fallback as the "real" model without disclosure), not a case for silently downgrading.

---

## Phase 2 — Stage 1 (Backward Drift) + Map's Origin Envelope Layer

**Goal:** first use of OpenDrift, first "trace it backward" moment in the demo.

**Backend**
- `services/drift_engine.py`: thin OpenDrift/OilDrift wrapper, config for reversed advection (negated CMEMS current + ERA5 wind + optional Stokes drift), capped at Stage 0's age window.
- `stage1_backward_drift.py`: seeds particles at slick centroid/polygon, runs reversed sim, outputs a probability-weighted origin region + time window (not a point).
- Timeout wired per rules.md §2 (long-running stage → `"failed"` with `detail: "simulation exceeded time budget"` on timeout, never a hang).

**Frontend**
- Map: origin-envelope layer appears once Stage 1 completes.
- Tab 3: "Backward Drift Trace" stage animates live.
- Bottom panel: first live stat (e.g. "origin window: 6h, envelope area: X km²") replaces the static placeholder.

**Exit criteria**
- Real reversed-drift run completes inside a bounded time budget on demo hardware; timeout path manually tested at least once (kill the sim mid-run, confirm the UI shows the failure state, not a spinner forever).

**If time is short:** this is the phase most likely to blow the schedule (physics sim + real forcing data wiring). If OpenDrift setup stalls, fall back to a documented single-step reversed-advection approximation *temporarily*, but this directly triggers rules.md §3.1 ("hand-rolled advection math" is explicitly banned) — flag it and get sign-off rather than shipping it silently; the PS explicitly expects a real drift model here.

---

## Phase 3 — Stage 2/3 (AIS Filter) + Stage 4 (Anomaly Scoring) + Tab 4 (Shortlist)

**Goal:** AIS enters the picture; first shortlist; first anomaly scores.

**Backend**
- `services/ais_loader.py`: MarineCadastre ingestion (preferred) with a synthetic-generator fallback, provenance-tagged per architecture.md.
- `stage2_3_filter.py`: spatiotemporal query against the Stage 1 envelope + vessel-type/draft/tonnage filter → candidate pool.
- `stage4_anomaly.py`: blackout/speed/route(DTW)/draft sub-scores → hand-tuned weighted `AnomalyScore [0,1]` (blackout weighted highest) → top N (5–10) shortlist. Weighting constants live in `models/anomaly_weights.py`, documented inline as a stand-in for a future learned model (PRD §6.1 F4, §9).
- `POST /api/pipeline/run` becomes real: kicks off Stages 0–4 as a background task, returns `run_id`; `GET /api/pipeline/status` reflects real per-stage state.

**Frontend**
- Tab 4 fully built: vessel cards with MMSI, type, operator, flag, destination, position-at-event, `anomaly_score` + breakdown, candidate release points — and the note distinguishing it from Tab 1's post-simulation results.
- Map: AIS track layer, color-coded by anomaly score.
- Tab 3: stages 1–4 animate through progress live on a real `run_id`; polling backoff/banner behavior (rules.md §2) exercised for the first time against a real long-running run.

**Exit criteria**
- Upload all 4 datasets → "Run pipeline" → shortlist populates Tab 4 with real, distinct anomaly sub-scores per vessel (not all-identical placeholder numbers).
- Killing the backend mid-poll shows the "connection lost, retrying…" banner, not silent staleness.

**If time is short:** synthetic AIS is an acceptable, pre-approved fallback (PRD §9 already frames it as such) — real data is preferred, not required, for this phase specifically. The anomaly weights are allowed to be rougher than ideal; what's not allowed is hiding that they're hand-tuned (rules.md §3.6).

---

## Phase 4 — Stage 5 (Forward Drift) + Stage 6 (Matching) + Tab 1 (Results)

**Goal:** the payoff stage — the ranked, evidence-backed suspect list.

**Backend**
- `stage5_forward_drift.py`: for each shortlisted vessel, forward-simulate from candidate release point(s) using OpenDrift/OilDrift (advection + wind drag + Fay spreading + weathering) to the Stage 0 detection timestamp — **only ever on the top-N shortlist**, never the full AIS pool (rules.md §3.8, PRD §9 — this is a stated design constraint, not a nice-to-have; write it so it's structurally impossible to call Stage 5 on anything but the shortlist, not just conventionally avoided).
- `stage6_matching.py`: IoU, centroid distance, orientation/elongation similarity → weighted `MatchScore`, confidence decay for longer sim windows.
- `POST /api/pipeline/simulate` + `GET /api/results/{run_id}` wired for real.
- Fay-spreading coefficients: literature defaults from `approach_3_-_oil_spill.pdf`, not invented (rules.md §3.9).

**Frontend**
- Tab 1 fully built: "Simulate" button (disabled + tooltip until shortlist exists, per rules.md §2 disabled-state rule), progress state during simulation, ranked vessel cards with `MatchScore` + IoU/centroid-distance/orientation sub-row + carried-over `AnomalyScore` breakdown — **`AnomalyScore` and `MatchScore` always visible and separate, never collapsed into one number** (rules.md §3.3, PRD §6 F6 — this is the single most-checked rule in this phase's review).
- Map: `SimulatedDriftLayer.tsx` + `CompareView.tsx` (split/overlay slider, observed vs. simulated).
- "Download" action → `GET /api/results/{run_id}/export`.

**Exit criteria**
- Full happy path works end-to-end, unassisted: 4 uploads → Run pipeline → shortlist → Simulate → ranked results → compare view → export.
- A reviewer can point at any vessel card and find both scores, separately, without hunting.

**If time is short:** this phase is not optional — it's the PS's part (c) and the demo's climax. If forward-sim performance is a problem, reduce top-N (e.g. 5 instead of 10) rather than cutting the stage; note the reduced N as a stated tradeoff if asked.

---

## Phase 5 — Tier 2 Prototypes (Dark-Ship, Oil-Type)

**Goal:** the two bonus channels, strictly isolated from the live pipeline.

**Backend**
- `stage2b_dark_ship.py` (CFAR/small CNN) and `stage5b_oil_type.py` (sklearn/small CNN) run **once, offline, ahead of the demo**, cached to `data/cache/prototype/`.
- `GET /api/prototype/dark-ship` and `GET /api/prototype/oil-type` — no `run_id` parameter, structurally cannot touch the live pipeline (architecture.md §2.2 — this is an architectural boundary, not a labeling choice; verify by checking neither route imports anything from `orchestrator.py` or accepts a `run_id`).

**Frontend**
- Two toggles ("Enable Dark-Ship Detection" / "Enable Oil-Type Fingerprinting"), both labeled **"Prototype — architecture below"** wherever they render, in both Tab 1 and the map (rules.md §3.2 — this label travels with the feature everywhere it appears, not just at first mention).

**Exit criteria**
- Toggling either on/off has zero effect on any live-run number elsewhere in the UI (manually verify: toggle on, check `ranked_suspects` didn't change).
- Prototype labeling is visible in the UI itself, not only in a code comment (rules.md §3.6).

**If time is short:** this entire phase is the first one to cut. PRD frames it as bonus (§6.2); dropping it entirely and stating so honestly is preferable to shipping a rushed, under-labeled version that risks looking like overclaiming (rules.md §3.2 explicit push-back rule).

---

## Phase 6 — Polish, Error States, Right-Edge Tools, Timeline

**Goal:** everything that makes the difference between "working pipeline" and "product a judge trusts."

**Backend**
- Confirm every stage function returns the discriminated `{"status": "success"/"failed", ...}` shape end-to-end (rules.md §2 audit pass).
- Confirm orchestrator halts downstream stages on any upstream failure (test by deliberately corrupting a Stage 2/3 input and confirming Stage 5 never runs).

**Frontend**
- `FloatingToolStack.tsx`: zoom, reset view, maximize/minimize, annotate, screenshot/export — all functional, not placeholders.
- `TimelineScrubber.tsx`: AIS playback and/or drift-sim playback, play/pause, granularity toggle.
- `StatsStrip.tsx`: live glance-able numbers mirroring Tab 3, condensed.
- Full pass on empty/loading/error states across all 4 tabs and the map — nothing renders blank at any point in the demo flow, including a cold start with zero data (PRD §8).
- Visual/tone pass against `design.md` tokens.

**Exit criteria**
- A judge can click every button on a fresh page load, before uploading anything, and never hit a blank panel or console error.
- Deliberately breaking the network (dev tools offline mode) mid-poll produces the "connection lost, retrying…" banner, then recovers cleanly when network is restored.

**If time is short:** annotate/screenshot tools are the safest cuts inside this phase — they're presenter conveniences, not pipeline-integrity features. Error-state coverage and empty-state coverage are not safe cuts; they're PRD §8 success criteria.

---

## Phase 7 — Demo Rehearsal & Known-Gaps Prep

**Goal:** not a build phase — a readiness check.

- Run the full happy path 3× on the actual demo machine/network, timed.
- Rehearse the PS's own (a)/(b)/(c) → live/prototype mapping as a one-slide answer (PRD §8).
- Rehearse a specific, honest answer for every row in `approach_3_-_oil_spill.pdf` §7 "Known Gaps" — this is a named PRD goal (PRD §4.6), not optional Q&A prep.
- Confirm final choice on the two PRD §10 open questions (backtest case, demo region) is reflected consistently across the dashboard, the pitch, and the Known Gaps answers.

**Exit criteria:** the team can answer "why did you flag this vessel?" live, from the dashboard's own visible sub-scores, without narrating around a black box (PRD §8).

---

## Cross-Cutting: What Never Moves, Regardless of Time Pressure

Per `rules.md` §3, these hold at every phase above, not just their "home" phase:
- No fabricated data presented as real pipeline output (synthetic must be labeled, always).
- Tier 2 never routes through the live `run_id`.
- `AnomalyScore` and `MatchScore` never collapse into one number.
- Schema changes touch both `backend/app/schemas/*.py` and `frontend/src/types/contracts.ts` in the same change.
- No scope creep beyond `prd.md` (new tabs, multi-case, auth) without flagging it first.

---

*Next file: `design.md` — visual design tokens, layout spec, and per-tab component detail for the dashboard.*
