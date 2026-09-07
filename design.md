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
- "SlickTrace" wordmark + a simple droplet/radar glyph, replacing the reference screenshot's product branding.
- Optional top-right icons (save/share) may be present but are non-functional placeholders for this build — not a PRD feature, don't wire them to anything real.

### 4.2 Tab Icon Rail (top to bottom)
1. **Results** (target icon or ranked-list glyph)
2. **Input** (upload/tray glyph)
3. **Pipeline** (stepper/gear glyph)
4. **Shortlist** (list/flag glyph)

Active tab: `--accent-teal` icon fill + a 2px left-edge indicator bar. Inactive: `--text-secondary`.

### 4.3 Tab 1 — Results

| Element | Spec |
|---|---|
| Simulate button | Full-width, top of panel. Enabled state: `--accent-teal` fill. Disabled state: `--bg-panel-raised` fill, `--text-disabled` label, **tooltip on hover/focus**: "Upload all 4 datasets and generate a shortlist first." (rules.md §2 — never a disabled button with no explanation) |
| Running state | Spinner + one-line status text sourced live from `pipeline_status.json`'s current stage `detail`, e.g. "Running drift simulation for MMSI 241123000…" |
| Result card (one per ranked vessel) | Rank badge (top-left corner) · vessel name + MMSI (`--text-display`) · **`MatchScore` badge**, colored per §2.1 scale, large and top-right of the card · sub-score row: IoU / centroid distance (km) / orientation match, small stat chips · **separate `AnomalyScore` row below a divider**, carried from Tab 4, with its own blackout/speed/route/draft breakdown · vessel type, flag, operator, small caption row · "View on map" toggle button |
| Post-simulation actions | "View simulated map" (opens `CompareView`) and "Download" buttons, both full-width secondary style, below the result list |
| Empty state (no sim run yet) | Icon + one sentence: "Run a simulation to see ranked suspects and match scores here." — never a blank panel |

**Non-negotiable layout rule (rules.md §3.3):** `MatchScore` and `AnomalyScore` are always two visually distinct rows/badges on the same card. No component may compute or display a merged single "confidence %."

### 4.4 Tab 2 — Input

Four upload cards, identical structure, in this order: **Wind → Ocean Current → SAR Image → AIS**.

| Card element | Spec |
|---|---|
| Title + one-line description | Per the wording already fixed in the source spec (e.g. "10m wind components (u/v), NetCDF or CSV. Used as forcing input for the drift simulation.") |
| File-type hint | `--text-caption`, e.g. "NetCDF, CSV" |
| Upload control | Drag-and-drop zone with fallback file picker |
| Status indicator | Pill badge: "Not uploaded" (`--text-disabled`), "Uploaded ✓" (`--accent-green`), "Invalid ⚠" (`--accent-red`, with the specific rejection reason from the backend shown inline, per rules.md §2 — never a generic error) |
| Provenance tag | Small pill: "Real" / "Synthetic" / "Illustrative" — `--text-caption` size, unobtrusive per PRD's honesty framing |
| Inferred bbox/date range | Shown once uploaded, small caption under the status pill, so all 4 datasets' coverage can be sanity-checked against each other |

Bottom of panel: **"Run pipeline"** button, same enabled/disabled/tooltip pattern as §4.3's Simulate button, enabled only when all 4 cards show "Uploaded ✓".

### 4.5 Tab 3 — Pipeline

Vertical stepper, 6 stages in fixed order (Perception → AIS Ingestion → Candidate Filtering → Anomaly Scoring → Drift Simulation → Verification/Matching). Each stage row:

| Element | Spec |
|---|---|
| Stage name + description | Description always visible, even pre-upload — this is how a judge reads the pipeline's structure before any data exists |
| Status chip | Pending (`--text-disabled`) / Running (`--accent-cyan`, subtle pulse) / Done (`--accent-green`) / Failed (`--accent-red`) |
| Progress | Numeric where available ("342 / 3045 AIS pings — 68%") or a plain progress bar; before any upload, this slot reads "Upload data first" instead of a number, description still shown |
| Failed-stage detail | If `status: "failed"`, the row expands to show the `detail` string from `pipeline_status.json` verbatim — this is the UI's enforcement of rules.md §2's "halt downstream, never propagate garbage" rule made visible |

Stages 5–6 stay visually "Pending" until Tab 1's Simulate is pressed, even if stages 1–4 are long done — this is intentional, not a bug, and should read that way (e.g. no spinner on 5–6 while waiting).

### 4.6 Tab 4 — Shortlist

Read-only vessel cards (no action buttons other than "View on map"), each showing: name + MMSI, vessel type, flag, operator, position-at-event (lat/lon + time relative to slick detection), destination, `AnomalyScore` + blackout/speed/route/draft breakdown, candidate release point(s). A fixed caption pinned at the top of the panel: *"These are AIS-flagged candidates prior to drift simulation. See Results for final confidence-scored rankings."* — this line is not optional copy; it's what stops Tab 4 and Tab 1 from being visually confusable (rules.md §3.3 spirit extended to the pre/post-sim distinction).

---

## 5. Map Canvas

### 5.1 Layers (toggleable, listed in typical z-order bottom→top)
1. Basemap (`--bg-ocean` water, `--land` landmasses)
2. AIS vessel tracks — color-coded along the `--accent-red`→`--accent-amber`→`--accent-green` scale by `anomaly_score` (inverted from the badge scale: high anomaly = red, matching "this vessel is more suspicious")
3. Observed slick polygon — solid `--accent-teal` outline + low-opacity fill
4. Candidate release point markers — small `--accent-cyan` pins
5. Simulated drift footprint (post-simulation only) — `--accent-cyan` outline + low-opacity fill, deliberately a different color from the observed slick's teal so the two are visually distinguishable in compare mode

### 5.2 Compare Mode
Triggered from Tab 1's "View simulated map." Two implementations are acceptable per `architecture.md`; pick one and keep it consistent:
- **Split**: two synced Leaflet panes side by side, left = observed, right = simulated, shared pan/zoom.
- **Overlay + slider**: single map, both layers stacked, a horizontal swipe slider reveals one vs. the other.

Either way: clicking a vessel track or marker anywhere on the map highlights the corresponding row in whichever left-sidebar tab is currently open (Tab 1 or Tab 4) — this is the one piece of cross-component interactivity the map owns.

---

## 6. Right-Edge Floating Tools

Six circular `--bg-panel-raised` buttons, single glyph each, `--text-primary` icon color, `--accent-teal` on hover: **Zoom in · Zoom out · Reset/home view · Maximize (hide sidebar+bottom panel) · Annotate (freehand/pin) · Screenshot/export**. Fixed position regardless of sidebar collapse state or active tab.

---

## 7. State Handling (visual rules, enforcing rules.md §2)

### 7.1 Empty states
Every panel and every map layer slot has a defined empty state — an icon + one sentence describing what will appear there and what triggers it. No component ships without one; this is checked per-component during Phase 6 polish (`phases.md`).

### 7.2 Error states
- Failed API call → inline error banner within the specific panel/tab affected, `--accent-red` left border, retry action where applicable. Never a blank panel, never only a browser console error.
- Repeated polling failure → a persistent top-of-map banner: "Connection lost, retrying…" (`--accent-amber` background), auto-dismisses on recovery.

### 7.3 Disabled controls
Any disabled button (Simulate, Run pipeline, or otherwise) is always paired with a tooltip stating the specific unmet precondition — never a bare greyed-out control. This is a hard rule carried directly from `rules.md` §2, not a style preference.

### 7.4 Loading states
Spinners/progress bars always carry a text label describing what's happening (sourced from the real `detail` field where one exists), never a bare spinner with no context.

---

## 8. Explicit Non-Goals for This Design Pass

- No dark/light theme toggle — one dark theme only, matches the operational tone and halves QA surface.
- No mobile/responsive layout — this is a demo-day desktop dashboard (PRD §5 non-goals; no production infra implies no responsive requirement either).
- No custom icon set commissioned — use an existing icon library (e.g. Lucide/Heroicons) consistent with the token colors above; icon choice is implementer's latitude per the original build spec.

---

*This is the last of the five planning documents (`prd.md` → `architecture.md` → `rules.md` → `phases.md` → `design.md`). Together they're the full spec an AI coding agent (Antigravity) or a human team can build SlickTrace from without further clarification.*
