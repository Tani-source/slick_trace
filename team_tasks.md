# SlickTrace — Manual Task Assignments

> These are the **non-automatable** tasks. The AI agent handles all code. Your job is to get the right data, credentials, and environment into its hands.

---

## Person A — SAR Imagery + U-Net Training

**Vertical:** Stage 0 (Perception)

### Tasks

| # | Task | Done? |
|---|---|---|
| A1 | Download Zenodo **Sentinel-1 SAR Oil Spill Dataset** — [doi.org/10.5281/zenodo.1487237](https://doi.org/10.5281/zenodo.1487237) | ☐ |
| A2 | Provision a GPU (Colab Pro / Kaggle / local) and run the U-Net training script the agent will write | ☐ |
| A3 | Monitor training — save the best checkpoint as `unet_weights.pt` and drop it in `backend/app/models/` | ☐ |
| A4 | Get **Copernicus Open Access Hub** account → download 1–2 Sentinel-1 GRD scenes of the demo region | ☐ |
| A5 | Get **Copernicus Marine Service (CMEMS)** credentials → share `.env` values with D for the whole team | ☐ |
| A6 | Get **ECMWF ERA5** access (CDS API key) → share with D | ☐ |

### Hand-off to agent when done
- `unet_weights.pt` in `backend/app/models/`
- At least one real Sentinel-1 `.tif` scene for the demo region
- CMEMS + ERA5 `.env` values (give to D, D puts in `.env`)

### Dependency note
> A5 + A6 must reach **D** before Phase 2 (backward drift) can start — D needs to test OpenDrift with real forcing data.

---

## Person B — AIS Data + Demo Region Decision

**Vertical:** Stage 2/3 (AIS Filter)

### Tasks

| # | Task | Done? |
|---|---|---|
| B1 | **Pick the demo region** — must have real AIS coverage on MarineCadastre. Recommended: Gulf of Mexico (US EEZ) or US East Coast. Document the bounding box + date range used. This closes **PRD §10 open question #2**. | ☐ |
| B2 | Download real AIS from **MarineCadastre** for the chosen region + time window → [marinecadastre.gov/data](https://marinecadastre.gov/data/) | ☐ |
| B3 | Sanity-check the AIS CSV: confirm columns (`MMSI`, `LAT`, `LON`, `BaseDateTime`, `VesselType`, `Draft`) exist; note any missing columns so agent can handle them | ☐ |
| B4 | If real AIS coverage is thin for the chosen window, **decide + document** that synthetic fallback will be used — the agent needs this decision explicitly, it cannot make it (PRD §9) | ☐ |
| B5 | Find or confirm a **real/documented spill event** in the chosen region to use as a backtest — or explicitly decide "no backtest in this build" and prepare the honest answer for judges (PRD §10 open question #1) | ☐ |

### Hand-off to agent when done
- AIS CSV file(s) dropped in `backend/data/uploads/` or a shared path
- A one-paragraph note: region chosen, date range, spill event used (or "no backtest"), any AIS column gaps found
- Decision on real vs. synthetic AIS

### Dependency note
> B1 must be decided **before** A4 (A needs to know which Sentinel-1 scenes to download) and before Phase 3 starts.

---

## Person C — Physics Validation + Runtime Tuning

**Vertical:** Stage 5 (Forward Drift) + Stage 6 (Matching)

### Tasks

| # | Task | Done? |
|---|---|---|
| C1 | Read **§4–§5 of `approach_3_-_oil_spill.pdf`** and extract the exact Fay-spreading coefficients the source doc uses — agent will use these verbatim (rules.md §3.9) | ☐ |
| C2 | Cross-check the weathering validity threshold (72h) and wind-speed window (1.5–10 m/s) against the source PDF — confirm or flag discrepancies | ☐ |
| C3 | Once D has OpenDrift working: run a **test forward-sim on demo hardware** for 1 vessel over a 24h window — record wall-clock time | ☐ |
| C4 | Based on C3 timing, **decide top-N** (5 or 10 or other) that fits the demo time budget. This closes the time-budget constraint in PRD §9. | ☐ |
| C5 | Decide the simulation time step and particle count OpenDrift should use — these are physics/performance tradeoffs only you can validate on real hardware | ☐ |

### Hand-off to agent when done
- Fay-spreading coefficients (exact values from PDF)
- Confirmed wind/age thresholds (or corrections)
- Chosen `TOP_N` value to set in `backend/app/config.py`
- OpenDrift time step + particle count recommendation

### Dependency note
> C3–C5 **block Phase 4** — agent cannot write `stage5_forward_drift.py` with correct coefficients and a realistic time budget until C gives sign-off.  
> C3 also depends on D finishing OpenDrift setup.

---

## Person D — OpenDrift Environment + Hosting + Compliance

**Vertical:** Cross-cutting (highest risk — start day one)

### Tasks

| # | Task | Done? |
|---|---|---|
| D1 | **Install and smoke-test OpenDrift on demo hardware today** — `pip install opendrift`, run their basic `OilDrift` example, confirm it works: [opendrift.github.io](https://opendrift.github.io/) | ☐ |
| D2 | Test OpenDrift with **CMEMS forcing data** (from A5) — confirm current fields load without CRS errors | ☐ |
| D3 | Test OpenDrift with **ERA5 wind data** (from A6) — confirm wind fields load | ☐ |
| D4 | Set up the **shared `.env` file** with all credentials (CMEMS, ERA5, any hosting tokens) — never commit `.env`, use `.env.example` as the template | ☐ |
| D5 | Choose + set up **hosting** for demo day (Render, Railway, or run locally — confirm which) | ☐ |
| D6 | **Phase 6/7 owner** — own the demo rehearsal script; run the full happy path 3× on demo hardware; time each run | ☐ |
| D7 | Prepare a written answer for every row of the **"Known Gaps" table** in `approach_3_-_oil_spill.pdf §7` — this is a named PRD goal (PRD §4.6) | ☐ |
| D8 | Before any merge: check each PR/change against `rules.md` — specifically §3.1 (no silent fallbacks), §3.2 (Tier 2 labeling), §3.3 (scores never merged), §3.6 (tradeoffs visible in UI) | ☐ |

### Hand-off to agent when done
- Confirmation that `opendrift` + CMEMS + ERA5 works on the target machine
- The working `pip install` / conda environment spec for the agent to reference in docs
- `.env` populated with all keys
- Hosting URL (if cloud) so agent can configure CORS

### Dependency note
> **D1 must start immediately — today — in parallel with Phase 0 coding.**  
> A (Phase 2), C (Phase 4), and the entire demo (Phase 7) all block on D1 working.  
> D7 can be done any time but must be rehearsed before Phase 7.

---

## Sequencing Summary

```
Day 1 (NOW):
  D1 ─── OpenDrift smoke test ──────────────────────────────► unblocks A+C
  B1 ─── Pick demo region ──────────────────────────────────► unblocks A4, Phase 3
  Agent: Phase 0 scaffold + Phase 1 (running ✅)

Day 2–3:
  A1–A4 ─── SAR data + training ───────────────────────────► feeds Phase 1 real data
  B2–B4 ─── AIS download + decision ───────────────────────► feeds Phase 3
  D2–D3 ─── Forcing data wiring ───────────────────────────► unblocks Phase 2
  Agent: Phase 2 (backward drift)

Day 4–5:
  C1–C2 ─── Physics coefficients ─────────────────────────► feeds Phase 4 config
  D4–D5 ─── .env + hosting setup ─────────────────────────► feeds demo
  Agent: Phase 3 (AIS filter + anomaly scoring)

Day 6:
  C3–C5 ─── Runtime tuning on real hardware ───────────────► finalizes top-N
  Agent: Phase 4 (forward drift + ranking)

Day 7+:
  D6–D8 ─── Rehearsal + Known-Gaps prep ──────────────────► Phase 7 readiness
  Agent: Phase 5 (Tier 2 prototypes) + Phase 6 (polish)
```

---

## What the Agent Cannot Do (Hard Rules)

| What | Why |
|---|---|
| Download from Copernicus / MarineCadastre | Requires authenticated human sessions |
| Run GPU training | No GPU access |
| Decide the demo region | PRD §10 open question — team decision |
| Decide "real vs. synthetic AIS" | PRD §9 — must be an honest, deliberate choice |
| Validate physics coefficients against a PDF | Requires reading the source doc |
| Benchmark OpenDrift on your hardware | No access to demo machine specs |
| Prepare Known-Gaps Q&A answers | Requires rehearsed human judgment |

---

> **When any person finishes their hand-off items, ping the agent with the data/values and it will immediately wire them into the pipeline.**
