"""
drift_engine.py — Thin wrapper around OpenDrift with a numpy fallback.
Provides run_backward and run_forward capabilities.
(rules.md §3.1: fallback must be labeled if used)
"""

import logging
import math
import numpy as np
import datetime
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError

import os

logger = logging.getLogger(__name__)

# OpenDrift (OpenOil) loads GSHHG global basemaps and the NOAA ADIOS oil database,
# consuming >1.5GB of RAM. In memory-constrained environments (such as Render's 512MB free tier),
# allocating OpenOil triggers the kernel OOM killer (SIGKILL) and crashes the server (502 Bad Gateway).
# Therefore, we safely use the documented numpy advection engine (rules.md §3.1) on Render.
_disable_opendrift = os.getenv("DISABLE_OPENDRIFT", "").lower() in ("1", "true") or bool(os.getenv("RENDER"))
if _disable_opendrift:
    OPENDRIFT_AVAILABLE = False
    logger.info("Memory-constrained environment detected (Render) — using numpy advection engine (rules.md §3.1).")
else:
    try:
        import opendrift
        from opendrift.models.openoil import OpenOil
        OPENDRIFT_AVAILABLE = True
    except ImportError:
        OPENDRIFT_AVAILABLE = False
        logger.warning("OpenDrift not found. Falling back to numpy single-step advection.")


def _run_opendrift_backward(seed_points: list[list[float]], hours: float, current_path: str | None, wind_path: str | None, time_iso: str | None = None) -> list[list[float]]:
    o = OpenOil(loglevel=50)
    readers = [p for p in [current_path, wind_path] if p]
    if readers:
        o.add_readers_from_list(readers)
    else:
        # If no readers, use a constant dummy reader so it doesn't instantly fail 
        # (though it might fail if we actually wanted real data)
        # We will let it fail if no readers exist, relying on fallback
        pass

    # Disable irreversible physics for hindcast
    o.set_config('drift:current_uncertainty', 0)
    o.set_config('drift:wind_uncertainty', 0)
    # OpenOil specific config to disable weathering/spreading going backward
    try:
        o.disable_vertical_motion()
    except Exception:
        pass

    lons = [p[1] for p in seed_points]
    lats = [p[0] for p in seed_points]
    # In OpenDrift time is UTC datetime
    if time_iso:
        clean_iso = time_iso.rstrip('Z').replace('+00:00', '')
        t = datetime.datetime.fromisoformat(clean_iso)
        if t.tzinfo is not None:
            t = t.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    else:
        t = datetime.datetime.utcnow()
    o.seed_elements(lon=lons, lat=lats, time=t, number=len(seed_points))
    
    # Run backward
    o.run(time_step=datetime.timedelta(minutes=-30), duration=datetime.timedelta(hours=hours))
    
    final_lons = o.elements.lon
    final_lats = o.elements.lat
    
    # Return as [lat, lon]
    return [[float(lat), float(lon)] for lat, lon in zip(final_lats, final_lons) if not np.isnan(lat)]


def _run_opendrift_forward(release_point: list[float], hours: float, current_path: str | None, wind_path: str | None, time_iso: str | None = None) -> list[list[float]]:
    o = OpenOil(loglevel=50)
    readers = [p for p in [current_path, wind_path] if p]
    if readers:
        o.add_readers_from_list(readers)
        
    if time_iso:
        clean_iso = time_iso.rstrip('Z').replace('+00:00', '')
        t = datetime.datetime.fromisoformat(clean_iso)
        if t.tzinfo is not None:
            t = t.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    else:
        t = datetime.datetime.utcnow()
    o.seed_elements(lon=release_point[1], lat=release_point[0], time=t, number=1000)
    
    # Run forward (Fay spreading is on by default in OpenOil)
    o.run(time_step=datetime.timedelta(minutes=30), duration=datetime.timedelta(hours=hours))
    
    final_lons = o.elements.lon
    final_lats = o.elements.lat
    
    # Convex hull of the points to form a polygon footprint
    points = np.column_stack((final_lons, final_lats))
    points = points[~np.isnan(points).any(axis=1)]
    if len(points) < 3:
        return []
        
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(points)
        poly_lons_lats = points[hull.vertices]
        return [[float(lat), float(lon)] for lon, lat in poly_lons_lats]
    except Exception:
        # Fallback if hull fails
        return [[float(lat), float(lon)] for lon, lat in points[:20]]


def _numpy_backward_fallback(seed_points: list[list[float]], hours: float) -> list[list[float]]:
    lats = [p[0] for p in seed_points]
    lons = [p[1] for p in seed_points]
    if not lats: return []
    c_lat, c_lon = sum(lats)/len(lats), sum(lons)/len(lons)
    drift_dist_deg = (0.5 * hours) / 111.0
    expansion_deg = (0.1 * hours) / 111.0
    shift_lat = drift_dist_deg * 0.7
    shift_lon = drift_dist_deg * 0.7
    
    result_points = []
    for lat, lon in seed_points:
        v_lat, v_lon = lat - c_lat, lon - c_lon
        dist = math.hypot(v_lat, v_lon)
        if dist > 0:
            n_lat, n_lon = v_lat / dist, v_lon / dist
        else:
            n_lat, n_lon = 0, 0
        result_points.append([lat + shift_lat + n_lat * expansion_deg, lon + shift_lon + n_lon * expansion_deg])
    return result_points


def _numpy_forward_fallback(release_point: list[float], hours: float) -> list[list[float]]:
    radius_deg = 0.0045 * hours
    drift_dist_deg = (0.5 * hours) / 111.0
    shift_lat = -drift_dist_deg * 0.7
    shift_lon = -drift_dist_deg * 0.7
    c_lat = release_point[0] + shift_lat
    c_lon = release_point[1] + shift_lon
    
    poly = []
    for i in range(8):
        angle = 2 * math.pi * i / 8
        r_lat, r_lon = radius_deg * 0.8, radius_deg * 1.2
        poly.append([c_lat + math.sin(angle) * r_lat, c_lon + math.cos(angle) * r_lon])
    return poly


def run_backward(seed_points: list[list[float]], hours: float, current_path: str | None = None, wind_path: str | None = None, time_iso: str | None = None) -> dict:
    if OPENDRIFT_AVAILABLE:
        try:
            points = _run_opendrift_backward(seed_points, hours, current_path, wind_path, time_iso)
            logger.info("OpenDrift backward simulation succeeded.")
            return {"points": points, "fallback_used": False}
        except Exception as e:
            logger.error(f"OpenDrift backward simulation failed: {e}. Using numpy fallback.")
            
    # Fallback path
    return {
        "status": "success",
        "points": _numpy_backward_fallback(seed_points, hours),
        "fallback_used": True
    }


def run_forward(
    release_point: list[float], 
    hours: float, 
    current_path: str | None = None, 
    wind_path: str | None = None,
    time_iso: str | None = None
) -> dict:
    if OPENDRIFT_AVAILABLE:
        try:
            poly = _run_opendrift_forward(release_point, hours, current_path, wind_path, time_iso)
            logger.info("OpenDrift forward simulation succeeded.")
            return {"polygon": poly, "fallback_used": False}
        except Exception as e:
            logger.error(f"OpenDrift forward simulation failed: {e}. Using numpy fallback.")

    # Fallback path
    return {
        "status": "success",
        "polygon": _numpy_forward_fallback(release_point, hours),
        "fallback_used": True
    }

