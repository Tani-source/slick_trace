# design.md — SlickTrace

**Visual design tokens, layout spec, and per-tab component detail.**
Implements the skeleton from the original build-instructions sketch (Global Fishing Watch–style reference) inside the stack `architecture.md` already committed to (React + Leaflet + Tailwind + Zustand + Recharts). This file is the source of truth for `frontend/src/styles/` and every component under `frontend/src/components/`.

---

## 1. Design Language

**Tone: operational, not decorative.** SlickTrace is investigative tooling, not a marketing dashboard — the reference screenshot's dark-ocean/glanceable-HUD aesthetic is right for that, and it also happens to make data layers (tracks, polygons, heat) legible against a dark basemap. Every visual decision below optimizes for "a judge or analyst can read the state of the pipeline at a glance," not for polish for its own sake.

**Three rules that override everything else in this file if they conflict:**
1. Empty/pending states are never visually blank — see §7.
2. `AnomalyScore` and `MatchScore` are never visually merged into one badge/number — see §5.1 (rules.md §3.3).
3. Disabled controls always carry a visible reason, not just a lower opacity — see §7.3 (rules.md §2).

---

## 2. Design Tokens

### 2.1 Color

| Token | Hex | Usage |
|---|---|---|
| `--bg-ocean` | `#0B1E3D` | Base map ocean fill, app background |
| `--bg-panel` | `#122A52` | Sidebar panel, bottom panel, card backgrounds |
| `--bg-panel-raised` | `#1B3866` | Cards/rows within a panel (one step lighter, for nesting) |
| `--border-subtle` | `#2A4A80` | Panel borders, dividers |
| `--land` | `#DCE3EA` | Landmass fill on basemap |
| `--accent-teal` | `#2DD4BF` | Primary data/activity color — AIS density, observed-slick outline, active tab indicator |
| `--accent-cyan` | `#38BDF8` | Secondary data color — simulated/predicted layers, links |
| `--accent-amber` | `#F5A524` | Warning / anomaly-flagged / prototype-labeled content |
| `--accent-red` | `#F04438` | Failed stage, invalid upload, low-confidence badge |
| `--accent-green` | `#22C55E` | High-confidence badge, success/done stage chip |
| `--text-primary` | `#F1F5F9` | Primary text on dark backgrounds |
| `--text-secondary` | `#94A3B8` | Labels, captions, empty-state copy |
| `--text-disabled` | `#5B6B84` | Disabled control text |

Confidence-score color mapping (used identically for `AnomalyScore` and `MatchScore` badges, kept visually distinct only by label/position, never by inventing a third merged scale):
- ≥ 0.7 → `--accent-green`
- 0.4–0.69 → `--accent-amber`
- < 0.4 → `--accent-red`

### 2.2 Typography

| Token | Font-size / weight | Usage |
|---|---|---|
| `--text-display` | 20px / 600 | Panel headers ("Results", "Input", "Pipeline", "Shortlist"), score numbers |
| `--text-body` | 14px / 400 | Card content, descriptions |
| `--text-label` | 12px / 500, uppercase, 0.04em tracking | Field labels ("MMSI", "MATCH SCORE"), section headers |
| `--text-caption` | 11px / 400 | Timestamps, provenance tags, empty-state copy |

Font family: system UI stack (`-apple-system, "Segoe UI", Roboto, sans-serif`) — no custom web font load, one less thing to break on demo Wi-Fi.

### 2.3 Spacing & Radius

- Base spacing unit: 4px; components use multiples of it (8, 12, 16, 24).
- `--radius-card`: 8px. `--radius-badge`: 999px (pill). `--radius-button`: 6px.
- Sidebar expanded width: 340px. Collapsed (icon-rail) width: 56px.
- Right-edge tool stack: 40px circular buttons, 12px gap, pinned 16px from the right edge, vertically centered.
- Bottom panel height: 96px collapsed strip / 160px when the timeline scrubber is active.

---

## 3. Layout Skeleton

```
┌────┬──────────────────────────────────────────────────────┬────┐
│    │                                                        │ ●  │ ← right-edge floating tools
│ SB │                                                        │ ●  │   (zoom, reset, maximize,
│    │                    MAP (always visible)                │ ●  │    annotate, screenshot)
│    │                                                        │ ●  │
│    │                                                        │ ●  │
├────┴──────────────────────────────────────────────────────┴────┤
│  live stats strip  │  timeline scrubber (play/pause, granularity) │
└──────────────────────────────────────────────────────────────────┘
```

- **Sidebar (SB)**: collapsible icon-rail on the far left. Hamburger toggles expanded ↔ collapsed; active tab persists across the toggle.
- **Map**: fills the remaining canvas regardless of which sidebar tab is open — the map is shared state, not owned by any one tab (architecture.md §2.3).
- **Right-edge tools**: fixed screen position, independent of sidebar/map state.
- **Bottom panel**: persistent strip; the timeline scrubber row only renders when a time-based layer exists to scrub (AIS playback or drift-sim playback), collapsing to just the stats row otherwise — this satisfies "never blank" without showing a scrubber with nothing to scrub.

---

## 4. Left Sidebar

### 4.1 Header
- Hamburger (≡) top-left. Click → collapses to the 56px icon rail (hamburger + 4 tab icons only, no labels/content). Click again → restores to 340px with the previously active tab's panel content intact.
- "SlickTrace" wordmark + a simple droplet/radar glyph, with a subtle "Beta" pill tag.
- System operational dot indicator pinned in the sidebar footer (`st-rail-foot`).

### 4.2 Tab Icon Rail (Top to Bottom)
1. **Verdict** (ID: `output`, glyph: target/radar) — Attribution map & report, ranked suspects, `MatchScore` badge, carried-over `AnomalyScore` breakdown, split comparison, export bundle.
2. **Datasets** (ID: `input`, glyph: upload/tray) — 4 dataset cards (Wind, Current, SAR Image, AIS) + ⚡ **Load Demo Scenario** button + "Run Pipeline" trigger.
3. **Pipeline** (ID: `pipeline`, glyph: stepper/gear) — 7-stage vertical execution stepper with live progress %, descriptions, and failed-stage alert banner (`.st-stage.failed`).
4. **Shortlist** (ID: `suspects`, glyph: list/flag) — Pre-simulation candidate vessels flagged by origin filter and anomaly scoring prior to forward drift simulation.

Active tab: `--accent-teal` icon fill + a 2px left-edge indicator bar. Inactive: `--text-secondary`.

### 4.3 Tab 1 — Verdict (`output`)

| Element | Spec |
|---|---|
| Run Simulation button | Full-width, top of panel or in bottom panel. Enabled state: `--accent-teal` fill. Disabled state: `--bg-panel-raised` fill, `--text-disabled` label, with clear tooltip: "Run pipeline and generate a shortlist first." |
| Running state | Spinner + one-line status text sourced live from `pipeline_status.json` current stage `detail` (e.g. "Starting forward drift simulation…"). |
| Result card (one per ranked vessel) | Rank badge (top-left corner) · vessel name + MMSI (`--text-display`) · **`MatchScore` badge**, colored per §2.1 scale, large and top-right of the card · sub-score row: IoU / centroid distance (km) / orientation match, small stat chips · **separate `AnomalyScore` row below a divider**, carried from Tab 4, with its own blackout/speed/route/draft breakdown · vessel type, flag, operator, small caption row · "View on map" toggle button. |
| Post-simulation actions | "View simulated map" (toggles `CompareView`) and "Export Package" (`GET /api/results/{run_id}/export`), downloading a `.zip` containing GeoJSON and JSON artifacts. |
| Empty state (no sim run yet) | Radar icon + one sentence: "Run a simulation to see ranked suspects and match scores here." — never a blank panel. |

**Non-negotiable layout rule (rules.md §3.3):** `MatchScore` and `AnomalyScore` are always two visually distinct rows/badges on the same card. No component may compute or display a merged single "confidence %."

### 4.4 Tab 2 — Datasets (`input`)

Top action: **"⚡ Load Demo Scenario"** button. Single-click action that calls `POST /api/datasets/load-demo` to immediately populate all 4 dataset cards with the pre-packaged synthetic benchmark fixtures (SAR GeoTIFF, AIS tracks, Wind NetCDF, Current NetCDF).

Four upload cards, identical structure, in this order: **Wind → Ocean Current → SAR Image → AIS**.

| Card element | Spec |
|---|---|
| Title + one-line description | "10m Wind Fields (u/v)", "Surface Ocean Currents", "SAR Satellite Imagery", "AIS Vessel Tracks". |
| File-type hint | `--text-caption`, e.g. "NetCDF, CSV" or "GeoTIFF, PNG". |
| Upload control | Drag-and-drop zone with fallback native file picker. |
| Status indicator | Pill badge: "Not uploaded" (`--text-disabled`), "Uploaded ✓" (`--accent-green`), "Invalid ⚠" (`--accent-red`, with the specific rejection reason shown inline). |
| Provenance tag | Small pill: "Real" / "Synthetic" / "Illustrative" — `--text-caption` size, unobtrusive per PRD's honesty framing. |
| Inferred bbox/date range | Shown once uploaded, small caption under the status pill, confirming dataset spatiotemporal coverage. |

Bottom of panel: **"Run Pipeline"** button, enabled only when all 4 cards show "Uploaded ✓". When clicked, automatically transitions UI focus to Tab 3 (Pipeline).

### 4.5 Tab 3 — Pipeline (`pipeline`)

Vertical stepper, **7 stages** in fixed order. Each stage row:

| Stage Name | Pipeline Role | Default Description |
|---|---|---|
| 0. Perception | `perception` | U-Net deep segmentation on SAR imagery to extract slick geometry and age. |
| 1. Backward Drift | `backward_drift` | Reverse advection using ocean currents & winds to calculate probable origin envelope. |
| 2. AIS Ingestion | `ais_ingestion` | Ingestion of maritime AIS vessel traffic within the origin spatiotemporal envelope. |
| 3. Candidate Filtering | `candidate_filtering` | Corridor, vessel-type, draft, and physical discharge plausibility filtering. |
| 4. Anomaly Scoring | `anomaly_scoring` | Multi-factor anomaly scoring (AIS blackout, speed anomalies, route deviation, draft). |
| 5. Drift Simulation | `drift_simulation` | Forward trajectory advection of shortlisted vessels to satellite detection timestamp. |
| 6. Verification / Matching | `verification_matching` | Spatial overlap, centroid proximity, and elongation alignment scoring. |

Row elements:
- **Status chip**: Pending (`--text-disabled`) / Running (`--accent-cyan`, subtle pulse) / Done (`--accent-green`) / Failed (`--accent-red`).
- **Progress**: Percentage numeric progress or stage detail string.
- **Failed-stage detail**: If `status: "failed"`, the row expands into a prominent alert card (`.st-stage.failed`) with an exclamation glyph and the exact backend error `detail` string verbatim, enforcing rules.md §2's halt-downstream policy.

Stages 5–6 stay visually "Pending" until the user triggers "Run Simulation", accurately reflecting the two-phase pipeline execution model.

### 4.6 Tab 4 — Shortlist (`suspects`)

Read-only vessel cards showing: name + MMSI, vessel type, flag, operator, position-at-event (lat/lon + time relative to slick detection), destination, `AnomalyScore` + blackout/speed/route/draft breakdown, candidate release point(s). A fixed caption pinned at the top: *"These are AIS-flagged candidates prior to drift simulation. See Verdict for final confidence-scored rankings."*

---

## 5. Map Canvas

### 5.1 Layers (Toggleable, listed in z-order bottom→top)
1. **Basemap**: Leaflet dark-ocean tile layer (`--bg-ocean` water, `--land` landmasses).
2. **AIS Vessel Tracks (`AISTrackLayer`)**: Polylines color-coded along the `--accent-green`→`--accent-amber`→`--accent-red` gradient by `anomaly_score` (higher anomaly = red).
3. **Observed Slick Polygon (`SlickLayer`)**: Solid `--accent-teal` outline + semi-transparent teal fill.
4. **Origin Envelope (`OriginEnvelopeLayer`)**: Dashed `--accent-amber` polygon showing the probable hindcast release area.
5. **Candidate Release Points (`ReleasePointLayer`)**: `--accent-cyan` circular markers representing vessel positions during the origin window.
6. **Simulated Drift Footprints (`SimulatedDriftLayer`)**: `--accent-cyan` polygon outlines representing forward advection results for shortlisted vessels.
7. **Dark-Ship Targets (`DarkShipLayer`)**: Tier 2 prototype radar targets detected in SAR imagery without active AIS.

### 5.2 Compare Mode
Triggered from Tab 1's "View simulated map" button or the bottom action bar. When active, enables a split view (`st-view.split`) presenting the observed slick polygon side-by-side with the forward-simulated suspect footprint for direct geometric verification.

Clicking any vessel track or candidate release point on the map automatically highlights the corresponding card in the active sidebar tab (Tab 1 or Tab 4).

---

## 6. Right-Edge Floating Tools

Six circular `--bg-panel-raised` buttons, single glyph each, `--text-primary` icon color, `--accent-teal` on hover: **Zoom in · Zoom out · Reset/home view · Maximize (hide sidebar + bottom panel) · Annotate (freehand/pin) · Screenshot/export**. Pinned at a fixed screen position.

---

## 7. State Handling & Error Boundaries

### 7.1 Empty States
Every panel and map layer has an explanatory empty state with an icon and concise instruction (e.g. "Upload all 4 datasets or click ⚡ Load Demo Scenario to begin"). No panel ever renders blank.

### 7.2 Connection & Error States
- **Persistent Connection Banner**: If `/api/health` fails or polling network errors exceed threshold, a fixed top banner renders: `"Connection lost, retrying…"` (`--accent-red` / rust background), auto-dismissing upon recovery.
- **Stale Run / 404 Recovery**: If a container restarts or an active `run_id` is lost, the polling loop catches the 404, resets `runId`, switches to the Datasets tab, and displays: *"Active run has expired or server restarted. Please click '⚡ Load Demo Scenario' or re-upload datasets to proceed."*
- **Stage Failure**: Displayed inside the stage row itself with red styling and the exact backend exception message.

### 7.3 Disabled Controls
Any disabled button (e.g. "Run Pipeline" before 4 datasets are ready, "Run Simulation" before shortlist generation) includes an explanatory hover tooltip stating the unmet precondition.

### 7.4 Loading States
Spinners are always paired with live status text from `pipeline_status.json` (e.g. "Seeding particles…", "Running reversed advection…", "Scoring candidates…").

---

## 8. Explicit Non-Goals for This Design Pass

- No dark/light theme toggle — single dark-ocean operational theme only.
- No mobile/responsive layout — desktop investigative dashboard for demo presentation.
- No custom iconography library — standard Lucide/SVG glyphs adhering to token colors.

---

*Together with `architecture.md`, `rules.md`, `phases.md`, and `prd.md`, this design spec defines the complete visual and behavioral system of SlickTrace.*
