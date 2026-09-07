"""Generate realistic AIS vessel tracks in MarineCadastre CSV format.

Each vessel follows a plausible shipping-lane route through the demo region.
The culprit tanker's track passes through the release point and contains a
transponder blackout window centred on the discharge event. All other vessels
have continuous, unbroken tracks with no anomaly.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config as C

# Navigation status codes
NAV_UNDERWAY = 0
NAV_ANCHORED = 1
NAV_MOORED = 5
NAV_NOT_DEFINED = 15

# Pre-computed route waypoints for each vessel (lat, lon pairs)
# Each vessel enters the domain from one edge and exits from another.
# Coordinates are chosen so routes cross realistic shipping lanes.

_ROUTE_TEMPLATES: dict[str, list[tuple[float, float]]] = {
    # East–west tanker lane (north of domain)
    "tanker_ew": [
        (28.55, -90.05), (28.70, -89.85), (28.80, -89.62), (28.85, -89.40),
        (28.88, -89.10), (28.90, -88.95),
    ],
    # East–west tanker lane (south of domain)
    "tanker_ew_south": [
        (28.52, -90.05), (28.55, -89.75), (28.58, -89.40), (28.60, -89.10),
        (28.62, -88.95),
    ],
    # North–south cargo to Mississippi delta
    "cargo_ns": [
        (28.45, -89.50), (28.65, -89.48), (28.85, -89.45), (29.05, -89.42),
    ],
    # Diagonal NW–SE (supply vessel to platforms)
    "supply_diag": [
        (29.05, -89.90), (28.88, -89.72), (28.70, -89.55), (28.52, -89.35),
    ],
    # West–east transit
    "transit_we": [
        (28.50, -90.05), (28.60, -89.70), (28.72, -89.30), (28.80, -89.00),
        (28.82, -88.95),
    ],
    # Short inshore (fishing)
    "fishing_1": [
        (28.58, -89.75), (28.65, -89.65), (28.72, -89.58), (28.65, -89.50),
        (28.58, -89.60), (28.58, -89.75),
    ],
    "fishing_2": [
        (28.70, -89.90), (28.78, -89.80), (28.82, -89.70), (28.75, -89.62),
        (28.68, -89.72), (28.70, -89.90),
    ],
    "fishing_3": [
        (28.85, -89.95), (28.90, -89.78), (28.88, -89.55), (28.82, -89.50),
        (28.78, -89.60), (28.85, -89.80), (28.85, -89.95),
    ],
    # Passenger transiting north
    "passenger_ns": [
        (28.45, -89.20), (28.65, -89.15), (28.85, -89.08), (29.05, -89.00),
    ],
    # Coast guard patrol
    "patrol": [
        (28.60, -89.30), (28.72, -89.40), (28.80, -89.50), (28.72, -89.60),
        (28.60, -89.50), (28.60, -89.30),
    ],
}

# Map vessel fleet index to route template
_VESSEL_ROUTES: list[str] = [
    "tanker_ew",         # PACIFIC TRADER (culprit)
    "tanker_ew_south",   # ATLANTIC VOYAGER (suspect — passes near origin)
    "tanker_ew",         # GULF HORIZON
    "tanker_ew_south",   # NORTHERN SPIRIT
    "tanker_ew",         # SOUTHERN STAR
    "transit_we",        # EVERGREEN WAVE
    "cargo_ns",          # COSCO FORTUNE
    "transit_we",        # MAERSK SELETAR
    "supply_diag",       # YANG MING UNITED
    "cargo_ns",          # ONE INNOVATION
    "transit_we",        # PIL PHILIPPINES
    "supply_diag",       # SEACOR WARRIOR
    "supply_diag",       # BOIS BLOUIN
    "fishing_1",         # GULF TUG 12
    "fishing_1",         # LOUISIANA REEL
    "fishing_2",         # DELTA CATCH
    "fishing_3",         # BAYOU FISHER
    "passenger_ns",      # CARNIVAL SPIRIT
    "patrol",            # USCG RESCUE 4412
]


def _interpolate_route(waypoints: list[tuple[float, float]],
                       speed_kn: float,
                       rng: np.random.Generator) -> list[tuple[float, float]]:
    """Return dense (lat, lon) points along the route at ~100 m spacing."""
    dense: list[tuple[float, float]] = [waypoints[0]]
    for k in range(len(waypoints) - 1):
        lat0, lon0 = waypoints[k]
        lat1, lon1 = waypoints[k + 1]
        dlat = lat1 - lat0
        dlon = lon1 - lon0
        dist_m = math.sqrt((dlat * 111_320) ** 2 + (dlon * 111_320 * math.cos(math.radians((lat0 + lat1) / 2))) ** 2)
        n_pts = max(1, int(dist_m / 100))
        for j in range(1, n_pts + 1):
            t = j / n_pts
            lat = lat0 + dlat * t + rng.normal(0, 0.0002)
            lon = lon0 + dlon * t + rng.normal(0, 0.0002)
            dense.append((lat, lon))
    return dense


def _bearing(lat0: float, lon0: float, lat1: float, lon1: float) -> float:
    dlon = math.radians(lon1 - lon0)
    lat0r = math.radians(lat0)
    lat1r = math.radians(lat1)
    x = math.sin(dlon) * math.cos(lat1r)
    y = math.cos(lat0r) * math.sin(lat1r) - math.sin(lat0r) * math.cos(lat1r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _culprit_entry_time(
    dense_pts: list[tuple[float, float]],
    seg_dists: list[float],
    speed_ms: float,
    target_dt: datetime,
) -> datetime:
    """Return the culprit's entry time so it crosses the origin at ``target_dt``.

    The culprit cruises at constant speed; we set the start of its track so
    that the cumulative distance to the track point nearest the origin is
    traversed precisely by ``target_dt`` (the blackout open time). This makes
    its last visible ping sit at the discharge location, which is what Stage 4's
    blackout-anomaly scoring detects.
    """
    target = (C.ORIGIN_LAT, C.ORIGIN_LON)
    best_d = 1e18
    best_cum = 0.0
    cum = 0.0
    for k in range(len(dense_pts) - 1):
        d_to_tgt = math.sqrt(
            ((target[0] - dense_pts[k][0]) * 111_320) ** 2
            + ((target[1] - dense_pts[k][1]) * 111_320 * math.cos(math.radians(target[0]))) ** 2
        )
        if d_to_tgt < best_d:
            best_d = d_to_tgt
            best_cum = cum
        cum += seg_dists[k]
    time_to_origin_s = best_cum / max(speed_ms, 0.1)
    entry = target_dt - timedelta(seconds=time_to_origin_s)
    return entry


def generate_ais(
    out_dir: Path,
    rng: np.random.Generator,
) -> Path:
    """Write tracks.csv in MarineCadastre format and return path."""
    release_dt = datetime.fromisoformat(C.RELEASE_TIME).replace(tzinfo=timezone.utc)
    detect_dt = datetime.fromisoformat(C.DETECTION_TIME).replace(tzinfo=timezone.utc)
    epoch = datetime.fromisoformat(C.FORCING_START).replace(tzinfo=timezone.utc)
    window_start = epoch
    window_end = datetime.fromisoformat(C.FORCING_END).replace(tzinfo=timezone.utc)
    interval = timedelta(seconds=C.AIS_INTERVAL_S)
    blackout_start = release_dt - timedelta(hours=C.CULPRIT_BLACKOUT_BEFORE_H)
    blackout_end = release_dt + timedelta(hours=C.CULPRIT_BLACKOUT_AFTER_H)

    rows: list[dict] = []
    for vi, vessel in enumerate(C.FLEET_SPEC):
        mmsi = str(C.MMSI_BASE + vi).zfill(9)
        route_name = _VESSEL_ROUTES[vi]
        waypoints = list(_ROUTE_TEMPLATES[route_name])
        speed_kn = vessel["speed_kn"] + rng.uniform(-0.5, 0.5)
        is_culprit = vessel.get("role") == "culprit"
        is_suspect = vessel.get("role") == "suspect"
        if is_culprit:
            waypoints = list(_ROUTE_TEMPLATES["tanker_ew"])
        elif is_suspect:
            waypoints = list(_ROUTE_TEMPLATES["tanker_ew_south"])
        dense_pts = _interpolate_route(waypoints, speed_kn, rng)
        n_dense = len(dense_pts)
        if n_dense < 2:
            continue
        total_dist_m = 0.0
        seg_dists = []
        for k in range(n_dense - 1):
            dlat = (dense_pts[k + 1][0] - dense_pts[k][0]) * 111_320
            dlon = (dense_pts[k + 1][1] - dense_pts[k][1]) * 111_320 * \
                   math.cos(math.radians((dense_pts[k][0] + dense_pts[k + 1][0]) / 2))
            d = math.sqrt(dlat ** 2 + dlon ** 2)
            seg_dists.append(d)
            total_dist_m += d
        if total_dist_m < 1000:
            continue
        speed_ms = speed_kn * 0.514444
        travel_time_s = total_dist_m / max(speed_ms, 0.1)

        # Determine entry time so the route crosses the origin at the release
        # time for the culprit. Other vessels enter at random offsets.
        entry_offset = 0.0
        if is_culprit:
            # Reach the origin exactly when the blackout opens, so the last
            # visible ping before the gap sits at the discharge location.
            entry_time = _culprit_entry_time(dense_pts, seg_dists, speed_ms, blackout_start)
        else:
            entry_offset = rng.uniform(-0.3, 0.7) * total_dist_m
            entry_offset = max(0.0, min(entry_offset, total_dist_m * 0.5))
            entry_wait = rng.uniform(0, max(1.0, (window_end - window_start).total_seconds() - travel_time_s))
            entry_time = window_start + timedelta(seconds=entry_wait)

        total_seconds = (window_end - entry_time).total_seconds()
        n_pings = int(total_seconds / C.AIS_INTERVAL_S) + 1
        dist_per_ping = (total_dist_m / max(travel_time_s, 1)) * C.AIS_INTERVAL_S

        cumulative_dist = np.cumsum([0.0] + seg_dists)
        vessel_rows = []
        for pi in range(n_pings):
            t = entry_time + timedelta(seconds=pi * C.AIS_INTERVAL_S)
            if t > window_end or t < window_start:
                continue
            if is_culprit and blackout_start <= t <= blackout_end:
                continue
            travel_d = entry_offset + pi * dist_per_ping
            idx = int(np.clip(np.searchsorted(cumulative_dist, travel_d) - 1, 0, n_dense - 2))
            seg_len = seg_dists[idx] if idx < len(seg_dists) else seg_dists[-1]
            alpha = (travel_d - cumulative_dist[idx]) / max(seg_len, 1e-6)
            alpha = np.clip(alpha, 0.0, 1.0)
            lat = dense_pts[idx][0] + alpha * (dense_pts[min(idx + 1, n_dense - 1)][0] - dense_pts[idx][0])
            lon = dense_pts[idx][1] + alpha * (dense_pts[min(idx + 1, n_dense - 1)][1] - dense_pts[idx][1])
            lat += rng.normal(0, 0.0003)
            lon += rng.normal(0, 0.0003)
            next_idx = min(idx + 1, n_dense - 1)
            cog = _bearing(lat, lon, dense_pts[next_idx][0], dense_pts[next_idx][1])
            sog = speed_kn + rng.normal(0, 0.3)
            sog = max(0.1, sog)
            heading = cog + rng.normal(0, 2)
            heading = heading % 360
            status = NAV_UNDERWAY
            if sog < 0.5:
                status = NAV_ANCHORED
            vessel_rows.append({
                "MMSI": mmsi,
                "BaseDateTime": t.strftime("%Y-%m-%dT%H:%M:%S"),
                "LAT": round(lat, 4),
                "LON": round(lon, 4),
                "SOG": round(sog, 1),
                "COG": round(cog, 1),
                "Heading": round(heading, 0) if heading < 510 else 511,
                "VesselName": vessel["name"],
                "IMO": vessel.get("imo", "0000000"),
                "CallSign": vessel.get("callsign", ""),
                "VesselType": vessel["type"],
                "Status": status,
                "Length": vessel["length"],
                "Width": vessel["width"],
                "Draft": vessel["draft"],
                "Cargo": 0,
                "TransceiverClass": "A",
            })
        rows.extend(vessel_rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "tracks.csv"
    fieldnames = [
        "MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
        "VesselName", "IMO", "CallSign", "VesselType", "Status",
        "Length", "Width", "Draft", "Cargo", "TransceiverClass",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["MMSI"], r["BaseDateTime"])):
            writer.writerow(row)
    return csv_path
