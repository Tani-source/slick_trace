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

## 6. Core Features (Functional Requirements)

Features are grouped by pipeline stage (backend) and by dashboard tab (frontend), since the two map directly onto each other.

### 6.1 Tier 1 — Must Be Live and Working

**F1 — Slick Detection & Characterization (Stage 0)**
- Input: Sentinel-1 SAR (primary), Sentinel-2 EO (secondary).
- U-Net/encoder-decoder segmentation → binary oil/not-oil mask → polygon.
- Look-alike rejection using wind speed at capture (1.5–10 m/s valid window) and shape/texture heuristics.
- Output: slick polygon, area, shape descriptors, age estimate, weathering-validity flag (age > ~72h → low-confidence tag downstream).

**F2 — Backward Drift Trace (Stage 1)**
- Seed particles at slick centroid/polygon; run OpenDrift in reverse (negated CMEMS current + ERA5 wind + Stokes drift), capped at Stage 0's age window.
- Output: probability-weighted origin region + time-window envelope (not a single point).

**F3 — AIS Spatiotemporal + Vessel-Type Filter (Stage 2/3)**
- Query AIS tracks against the Stage 1 origin envelope.
- Filter to discharge-capable types (tanker, bulk/cargo, bunkering) via AIS type code + draft/tonnage.
- Output: candidate pool of physically plausible ships.

**F4 — AIS Behavioral Anomaly Scoring (Stage 4)**
- Score each candidate on: blackout/gap detection, speed anomaly, route deviation (DTW vs. expected lane), draft inconsistency (if available).
- Weighted sum → `AnomalyScore [0,1]`, hand-tuned weights (blackout weighted highest), explicitly noted in-product as "would be learned via logistic regression given labeled data."
- Output: top N (5–10) shortlist.

**F5 — Forward Drift Simulation & Matching (Stage 5)**
- For each shortlisted ship, simulate forward from candidate release point(s) to the Stage 0 detection timestamp (advection + wind drag + Fay spreading + weathering).
- Match metrics: IoU, centroid distance, orientation/elongation similarity → weighted `MatchScore`.
- Confidence decay applied/reported for longer simulation windows.

**F6 — Final Ranking & Dashboard (Stage 6)**
- Combine `AnomalyScore` + `MatchScore` → ranked suspect list.
- All component scores visible — never collapse to one opaque number.

**F7 — Dashboard: 4-Tab Sidebar**
- **Tab 1 (Results)**: post-simulation ranked suspects, "Simulate" trigger, per-vessel score breakdown, side-by-side simulated-vs-observed map view, download action.
- **Tab 2 (Input)**: 4 dataset upload cards (wind, ocean current, SAR, AIS) with status + provenance tags, "Run pipeline" trigger.
- **Tab 3 (Pipeline)**: live stage-by-stage status/progress for all 6 stages, always showing stage descriptions even pre-upload.
- **Tab 4 (Shortlist)**: pre-simulation candidate list from Stage 4, read-only.

**F8 — Map Canvas**
- Always-visible base map with toggleable layers: SAR/observed slick, AIS tracks (color-coded by anomaly score), candidate release points, simulated drift footprint (post-simulation only), split/overlay compare mode.

**F9 — Bottom Panel**
- Live glance-able pipeline stats strip + timeline scrubber (AIS playback and/or drift simulation playback) with play/pause and granularity toggle.

**F10 — Right-Edge Tools**
- Zoom in/out, reset view, maximize/minimize map, annotate (freehand/pin), screenshot/export.

### 6.2 Tier 2 — Prototype Toggle Only (Not in the PS, Bonus)

**F11 — Dark-Ship Detection (Stage 2b)**
- CFAR or CNN point-target detector on the Stage 0 SAR scene; any detected vessel near/inside the slick with no matching AIS is flagged as top suspect directly, bypassing behavioral scoring.
- Dashboard toggle: "Enable Dark-Ship Detection," backed by a pre-computed example, labeled **"Prototype — architecture below."**

**F12 — Oil-Type Fingerprinting (Stage 5b)**
- Classify oil type (crude/bunker/refined) from Sentinel-2 spectral/texture signature; cross-check against top suspect's declared cargo type.
- Match → confidence multiplier; no match/no EO coverage → falls back to drift-match alone, no penalty.
- Dashboard toggle, same "Prototype" labeling as F11.

---

## 7. Data Contracts (Summary — full shapes in `architecture.md`)

The dashboard is wired to four JSON contracts so frontend and backend stay decoupled:

- `slick_polygon.json` — feeds map's observed-slick layer + Input tab SAR status
- `shortlist.json` — feeds Shortlist tab (Stage 4 output)
- `ranked_suspects.json` — feeds Results tab (Stage 6 output)
- `pipeline_status.json` — feeds Pipeline tab + bottom panel live numbers

---

## 8. Success Criteria (Hackathon Context)

- Every Tier 1 stage (F1–F6) runs on real or realistic demo data end-to-end without manual intervention once the 4 inputs are uploaded.
- The pitch can show, on one slide, the PS's own (a)/(b)/(c) structure mapped 1:1 to what's live vs. what's prototype (per `approach_3_-_oil_spill.pdf` §6).
- No screen in the dashboard is ever blank/broken-looking, even with zero data uploaded (empty states always explain what will appear there).
- Judges can ask "why did you flag this vessel?" and get an answer from visible sub-scores, not a black box.
- Every "Known Gap" from the source doc (§7) has a rehearsed, honest answer ready.

---

## 9. Key Constraints & Assumptions

- Demo region chosen specifically for real AIS coverage (MarineCadastre US coastal waters) — real data preferred over synthetic where available.
- Physics simulation (drift, forward/backward) is compute-bounded by design: Stage 2/3 filtering happens *before* any simulation runs, and simulation only ever touches the top-N shortlist.
- Weathering/spreading coefficients are standard literature values (Fay spreading), explicitly not calibrated against real measured spills — stated as a roadmap item, not hidden.
- Anomaly scoring is hand-weighted/rule-based for the hackathon build, explicitly framed as a stand-in for a future logistic regression/GBM model once labeled data exists.

---

## 10. Open Questions (carry into `phases.md`)

- Which specific documented real-world spill case (if any) will be used for a backtest, or will this be explicitly stated as not attempted in the timeframe?
- Final demo region/dataset selection (must have real AIS coverage per MarineCadastre).
- Streamlit vs. React for the dashboard — `architecture.md` will make this call based on team velocity vs. the fidelity needed to match the dashboard spec.

---

*Next file: `architecture.md` — app flow, folder/file structure, tech stack.*
