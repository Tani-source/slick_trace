"""
stage1_backward_drift.py — Stage 1 of the pipeline.
Seeds particles at slick polygon boundary, runs backward drift,
and generates the origin envelope.
"""

import datetime
import math
from app.services.drift_engine import run_backward

def calculate_area(points: list[list[float]]) -> float:
    """Very rough area calculation for a polygon of lat/lon points."""
    # Shoelace formula on lat/lon, scaled to km^2 (approx)
    if len(points) < 3:
        return 0.0
    x = [p[1] * 111.0 * math.cos(math.radians(p[0])) for p in points]
    y = [p[0] * 111.0 for p in points]
    area = 0.5 * abs(sum(x[i]*y[i+1] - x[i+1]*y[i] for i in range(-1, len(x)-1)))
    return area

def run_backward_drift(
    slick_polygon: list[list[float]],
    age_hours: float,
    detection_time_iso: str,
    current_path: str | None = None,
    wind_path: str | None = None
) -> dict:
    """
    Execute Stage 1: Backward Drift.
    Returns discriminated dict.
    """
    if age_hours <= 0:
        return {"status": "failed", "reason": "Slick age must be > 0 for backward drift."}

    # 1. Run backward drift
    res = run_backward(slick_polygon, age_hours, current_path, wind_path, detection_time_iso)
    if res.get("status") == "failed":
        return res
        
    envelope_points = res["points"]
    fallback_used = res["fallback_used"]
    
    # 2. Compute bbox and area
    lats = [p[0] for p in envelope_points]
    lons = [p[1] for p in envelope_points]
    bbox = [min(lats), min(lons), max(lats), max(lons)]
    area = calculate_area(envelope_points)
    
    # 3. Compute time window
    detection_time = datetime.datetime.fromisoformat(detection_time_iso.replace('Z', '+00:00'))
    start_time = detection_time - datetime.timedelta(hours=age_hours)
    
    return {
        "status": "success",
        "data": {
            "polygon": envelope_points,
            "bbox": bbox,
            "area_km2": area,
            "time_window_hours": age_hours,
            "start_time": start_time.isoformat(),
            "end_time": detection_time.isoformat(),
            "fallback_used": fallback_used
        }
    }
