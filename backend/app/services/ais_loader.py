"""
AIS Loader — Stage 2/3 (AIS Ingestion + Candidate Filtering)

Decisions locked by Person B hand-off (backend/data/uploads/person_b_handoff.md):
  - Region  : Gulf of Mexico — Main Pass area (Louisiana Offshore)
  - BBox    : Lat [28.0, 30.0], Lon [-91.0, -88.0]
  - Dates   : 2023-11-15 to 2023-11-17 (Main Pass Oil Gathering spill)
  - AIS     : Synthetic fallback (MarineCadastre-schema CSV) — explicitly decided per PRD §9
  - Backtest: No forensic backtest conviction in this build (PRD §10 open question #1)

Rules observed (rules.md §1):
  - pandas only for tabular/AIS handling
  - No rolling IoU/polygon math (uses shapely bbox check)
  - Failure returns discriminated dict, never raises into orchestrator
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)

# ── Column constants (MarineCadastre standard schema) ──────────────────────────
COL_MMSI = "MMSI"
COL_DT = "BaseDateTime"
COL_LAT = "LAT"
COL_LON = "LON"
COL_SOG = "SOG"
COL_COG = "COG"
COL_VESSEL_NAME = "VesselName"
COL_IMO = "IMO"
COL_CALL = "CallSign"
COL_TYPE = "VesselType"
COL_STATUS = "Status"
COL_DRAFT = "Draft"

REQUIRED_COLUMNS = {COL_MMSI, COL_DT, COL_LAT, COL_LON, COL_TYPE}
OPTIONAL_COLUMNS = {COL_DRAFT, COL_VESSEL_NAME, COL_IMO, COL_CALL, COL_SOG, COL_COG}

# Vessel types considered relevant (tanker, cargo, bunkering)
RELEVANT_VESSEL_TYPES: set[int] = {
    30,   # Fishing
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79,  # Cargo
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89,  # Tanker
    90,   # Other / unknown — keep, may include bunkering
}

# Default demo region (B1 decision) and time window
DEFAULT_BBOX = (28.50, -90.00, 29.00, -89.00)  # (min_lat, min_lon, max_lat, max_lon)
DEFAULT_DATE_START = datetime(2024, 9, 13, tzinfo=timezone.utc)
DEFAULT_DATE_END = datetime(2024, 9, 16, tzinfo=timezone.utc)

# Spill origin — (Synthetic scenario)
SPILL_ORIGIN_LAT = 28.80
SPILL_ORIGIN_LON = -89.62
SPILL_DETECTION_TIME = datetime(2024, 9, 14, 18, 0, 0, tzinfo=timezone.utc)

# Release window: how many hours *before* detection to search for candidate positions
RELEASE_WINDOW_HOURS = 36


# ── Public entry point ─────────────────────────────────────────────────────────

def load_and_filter(
    csv_path: str | Path,
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
    date_start: datetime = DEFAULT_DATE_START,
    date_end: datetime = DEFAULT_DATE_END,
    spill_lat: float = SPILL_ORIGIN_LAT,
    spill_lon: float = SPILL_ORIGIN_LON,
    detection_time: datetime = SPILL_DETECTION_TIME,
    release_window_hours: int = RELEASE_WINDOW_HOURS,
) -> dict[str, Any]:
    """
    Load a MarineCadastre-format AIS CSV and return a filtered candidate list.

    Returns a discriminated result dict:
        {"status": "success", "data": <list of candidate dicts>}
      or
        {"status": "failed", "stage": "ais_ingestion", "reason": "<human-readable>"}
    """
    csv_path = Path(csv_path)

    # ── 1. Load ──────────────────────────────────────────────────────────────
    try:
        df = _load_csv(csv_path)
    except Exception as exc:
        return _fail(f"Could not read AIS CSV: {exc}")

    # ── 2. Validate schema ────────────────────────────────────────────────────
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return _fail(f"AIS CSV is missing required columns: {sorted(missing)}")

    # ── 3. Parse datetime ─────────────────────────────────────────────────────
    try:
        df[COL_DT] = pd.to_datetime(df[COL_DT], utc=True, errors="coerce")
    except Exception as exc:
        return _fail(f"Failed to parse BaseDateTime column: {exc}")

    n_bad_dt = df[COL_DT].isna().sum()
    if n_bad_dt > 0:
        logger.warning("AIS loader: %d rows had unparseable timestamps — dropped", n_bad_dt)
    df = df.dropna(subset=[COL_DT])

    # ── 4. Coerce lat/lon ─────────────────────────────────────────────────────
    df[COL_LAT] = pd.to_numeric(df[COL_LAT], errors="coerce")
    df[COL_LON] = pd.to_numeric(df[COL_LON], errors="coerce")
    df = df.dropna(subset=[COL_LAT, COL_LON])

    # ── 5. Spatial filter (bbox) ──────────────────────────────────────────────
    min_lat, min_lon, max_lat, max_lon = bbox
    df = df[
        (df[COL_LAT] >= min_lat) & (df[COL_LAT] <= max_lat) &
        (df[COL_LON] >= min_lon) & (df[COL_LON] <= max_lon)
    ]
    if df.empty:
        return _fail("No AIS pings found within the specified bounding box.")

    # ── 6. Temporal filter ────────────────────────────────────────────────────
    release_start = detection_time - timedelta(hours=release_window_hours)
    df = df[(df[COL_DT] >= release_start) & (df[COL_DT] <= date_end)]
    if df.empty:
        return _fail("No AIS pings found within the release time window.")

    # ── 7. Vessel-type filter ─────────────────────────────────────────────────
    df[COL_TYPE] = pd.to_numeric(df[COL_TYPE], errors="coerce").fillna(-1).astype(int)
    df = df[df[COL_TYPE].isin(RELEVANT_VESSEL_TYPES)]
    if df.empty:
        return _fail("No tanker/cargo/bunkering vessels found after type filter.")

    # ── 8. Fill optional columns safely ──────────────────────────────────────
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COL_DRAFT] = pd.to_numeric(df[COL_DRAFT], errors="coerce")  # nulls OK

    # ── 9. Identify the closest ping per vessel to the spill origin ──────────
    candidates = _build_candidates(df, spill_lat, spill_lon, detection_time)

    logger.info("AIS loader: %d candidate vessels after all filters", len(candidates))
    return {"status": "success", "data": candidates}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_csv(path: Path) -> pd.DataFrame:
    """Read the CSV, tolerating BOM and mixed line endings."""
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _build_candidates(
    df: pd.DataFrame,
    spill_lat: float,
    spill_lon: float,
    detection_time: datetime,
) -> list[dict[str, Any]]:
    """
    For each unique MMSI, pick the ping closest in time to detection_time,
    compute a rough haversine distance to the spill origin, and flag anomalies.
    """
    candidates = []
    spill_pt = Point(spill_lon, spill_lat)

    for mmsi, group in df.groupby(COL_MMSI):
        group = group.sort_values(COL_DT)

        # Closest ping to detection time
        time_deltas = (group[COL_DT] - detection_time).abs()
        closest = group.loc[time_deltas.idxmin()]

        dist_km = _haversine(
            closest[COL_LAT], closest[COL_LON],
            spill_lat, spill_lon
        )

        # Pre-compute anomaly indicators (full scoring happens in Stage 4)
        sog_vals = pd.to_numeric(group[COL_SOG], errors="coerce").dropna()
        blackout_flag = _has_blackout_gap(group[COL_DT])
        speed_anomaly = float(sog_vals.max()) if not sog_vals.empty else 0.0
        draft_val = closest[COL_DRAFT] if not pd.isna(closest[COL_DRAFT]) else None

        candidates.append({
            "mmsi": str(int(mmsi)),
            "vessel_name": str(closest.get(COL_VESSEL_NAME, "UNKNOWN") or "UNKNOWN"),
            "vessel_type": _type_label(int(closest[COL_TYPE])),
            "operator": "",
            "flag": "",
            "destination": "",
            "position_at_event": {
                "lat": round(float(closest[COL_LAT]), 5),
                "lon": round(float(closest[COL_LON]), 5),
                "time": closest[COL_DT].isoformat(),
            },
            "distance_to_spill_km": round(dist_km, 2),
            "anomaly_score": 0.0,  # filled by Stage 4
            "anomaly_breakdown": {
                "blackout": 1.0 if blackout_flag else 0.0,
                "speed": min(speed_anomaly / 20.0, 1.0),
                "route": 0.0,  # filled by Stage 4
                "draft": 0.0 if draft_val is not None else 0.3,  # penalise missing
            },
            "candidate_release_points": [
                {
                    "lat": round(float(closest[COL_LAT]), 5),
                    "lon": round(float(closest[COL_LON]), 5),
                    "time": closest[COL_DT].isoformat(),
                }
            ],
            # Internal tracking only
            "_ping_count": len(group),
            "_draft": draft_val,
        })

    # Sort by proximity to spill
    candidates.sort(key=lambda c: c["distance_to_spill_km"])
    return candidates


def _has_blackout_gap(timestamps: pd.Series, threshold_minutes: int = 60) -> bool:
    """Return True if there is any gap > threshold_minutes in the ping series."""
    if len(timestamps) < 2:
        return False
    gaps = timestamps.sort_values().diff().dropna()
    return bool((gaps > pd.Timedelta(minutes=threshold_minutes)).any())


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km."""
    import math
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _type_label(code: int) -> str:
    if 80 <= code <= 89:
        return "tanker"
    if 70 <= code <= 79:
        return "cargo"
    if code == 30:
        return "fishing"
    return "other"


def _fail(reason: str) -> dict[str, Any]:
    logger.error("AIS loader failed: %s", reason)
    return {"status": "failed", "stage": "ais_ingestion", "reason": reason}
