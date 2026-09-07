"""Slick particle advection and polygon generation.

Seeds a cloud of Lagrangian particles at the origin point, advects them
through the shared forcing fields (currents + 3 % wind), and produces:
- A slick polygon (list of [lat, lon] vertices) at detection time
- Slick metadata (area, elongation, centroid) in the same shape as
  ``slick_polygon.json`` in architecture.md §6
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

from . import config as C


def _release_particles(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Return (lats, lons) of particles seeded in a circle at the origin."""
    radii = C.PARTICLE_SEED_RADIUS_M * np.sqrt(rng.uniform(0, 1, C.NUM_PARTICLES))
    angles = rng.uniform(0, 2 * np.pi, C.NUM_PARTICLES)
    dlat = (radii * np.cos(angles)) / 111_320.0
    dlon = (radii * np.sin(angles)) / (111_320.0 * np.cos(np.radians(C.ORIGIN_LAT)))
    return C.ORIGIN_LAT + dlat, C.ORIGIN_LON + dlon


def advect_particles(
    nc_currents: Path,
    nc_wind: Path,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Advect particles from release to detection time.

    Returns
    -------
    init_lats, init_lons : (N,) — release positions
    final_lats, final_lons : (N,) — positions at detection time
    lats_history, lons_history : (N, n_substeps) — trajectory archive
    """
    from .forcing import batch_load_velocities

    release_dt = datetime.fromisoformat(C.RELEASE_TIME).replace(tzinfo=timezone.utc)
    detect_dt = datetime.fromisoformat(C.DETECTION_TIME).replace(tzinfo=timezone.utc)
    total_s = (detect_dt - release_dt).total_seconds()
    n_steps = int(total_s / C.ADVECTION_DT_S)

    lats, lons = _release_particles(rng)
    N = len(lats)
    history_lats = np.empty((N, n_steps + 1))
    history_lons = np.empty((N, n_steps + 1))
    history_lats[:, 0] = lats
    history_lons[:, 0] = lons

    epoch = datetime.fromisoformat(C.FORCING_START).replace(tzinfo=timezone.utc)
    # Turbulent diffusion: displacement std dev per step = sqrt(2 * K * dt)
    diff_std_m = np.sqrt(2.0 * C.DIFFUSION_K_M2_PER_S * C.ADVECTION_DT_S)
    for step in range(n_steps):
        t_s = np.full(N, (release_dt - epoch).total_seconds() + step * C.ADVECTION_DT_S)
        u_tot, v_tot = batch_load_velocities(nc_currents, nc_wind, lats, lons, t_s)
        # Random-walk diffusion (Fay spreading proxy)
        u_tot = u_tot + rng.normal(0, diff_std_m / C.ADVECTION_DT_S, N)
        v_tot = v_tot + rng.normal(0, diff_std_m / C.ADVECTION_DT_S, N)
        lat_m = u_tot * C.ADVECTION_DT_S / 111_320.0
        lon_m = v_tot * C.ADVECTION_DT_S / (111_320.0 * np.cos(np.radians(lats)))
        lats = lats + lat_m
        lons = lons + lon_m
        history_lats[:, step + 1] = lats
        history_lons[:, step + 1] = lons

    return history_lats[:, 0], history_lons[:, 0], lats, lons, history_lats, history_lons


def compute_slick_polygon(final_lats: np.ndarray, final_lons: np.ndarray) -> dict:
    """Compute slick polygon and metadata from advected particle positions.

    Returns a dict matching ``slick_polygon.json`` shape from architecture.md.
    """
    pts = np.column_stack([final_lats, final_lons])
    hull = ConvexHull(pts)
    vertices = pts[hull.vertices].tolist()
    centroid_lat = float(np.mean(final_lats))
    centroid_lon = float(np.mean(final_lons))
    area_m2 = hull.volume * (111_320.0 ** 2) * np.cos(np.radians(centroid_lat))
    area_km2 = area_m2 / 1e6
    dlat = np.ptp(final_lats)
    dlon = np.ptp(final_lons)
    elongation = max(dlat, dlon) / max(min(dlat, dlon), 1e-8)
    return {
        "polygon": vertices,
        "detection_time": C.DETECTION_TIME + ":00Z",
        "bbox": [float(min(final_lats)), float(min(final_lons)),
                 float(max(final_lats)), float(max(final_lons))],
        "area_km2": round(area_km2, 4),
        "elongation_ratio": round(float(elongation), 2),
        "age_estimate_hours": C.SLICK_AGE_HOURS,
        "centroid": {"lat": round(centroid_lat, 6), "lon": round(centroid_lon, 6)},
        "origin": {"lat": C.ORIGIN_LAT, "lon": C.ORIGIN_LON},
        "provenance": "synthetic",
    }


def save_scenario(
    out_dir: Path,
    slick_meta: dict,
    history_lats: np.ndarray,
    history_lons: np.ndarray,
) -> Path:
    """Save the full scenario ground-truth JSON."""
    release_dt = datetime.fromisoformat(C.RELEASE_TIME).replace(tzinfo=timezone.utc)
    detect_dt = datetime.fromisoformat(C.DETECTION_TIME).replace(tzinfo=timezone.utc)
    scenario = {
        "provenance": "synthetic",
        "region": C.REGION_NAME,
        "bbox": C.BBOX,
        "origin": {"lat": C.ORIGIN_LAT, "lon": C.ORIGIN_LON},
        "release_time": C.RELEASE_TIME + ":00Z",
        "detection_time": C.DETECTION_TIME + ":00Z",
        "slick_age_hours": C.SLICK_AGE_HOURS,
        "wind_drag_factor": C.WIND_DRAG_FACTOR,
        "culprit": {
            "mmsi": C.CULPRIT_MMSI,
            "name": C.CULPRIT_NAME,
            "imo": C.CULPRIT_IMO,
            "callsign": C.CULPRIT_CALLSIGN,
            "flag": C.CULPRIT_FLAG,
            "type": C.CULPRIT_TYPE,
            "draft_m": C.CULPRIT_DRAFT,
            "blackout_window": [
                (release_dt - timedelta(hours=C.CULPRIT_BLACKOUT_BEFORE_H)).isoformat(),
                (release_dt + timedelta(hours=C.CULPRIT_BLACKOUT_AFTER_H)).isoformat(),
            ],
        },
        "slick": slick_meta,
        "trajectory_summary": {
            "num_particles": C.NUM_PARTICLES,
            "mean_drift_km": round(float(np.mean(
                np.sqrt(((history_lats[:, -1] - history_lats[:, 0]) * 111_320.0) ** 2 +
                        ((history_lons[:, -1] - history_lons[:, 0]) * 111_320.0 *
                         np.cos(np.radians(C.ORIGIN_LAT))) ** 2)
            )) / 1000.0, 2),
        },
        "datasets": {
            "currents": "forcing/currents.nc",
            "wind": "forcing/wind.nc",
            "ais": "ais/tracks.csv",
            "sar_demo": "sar/demo_scene.tif",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "scenario.json"
    p.write_text(json.dumps(scenario, indent=2), encoding="utf-8")
    return p
