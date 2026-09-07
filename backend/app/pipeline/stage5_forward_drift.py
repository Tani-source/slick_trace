"""
stage5_forward_drift.py — Stage 5: Forward simulation on top-N shortlist.
(rules.md §3.8: NEVER run on the full AIS pool)
"""

from app.services.drift_engine import run_forward
import datetime

def run_forward_simulation(
    shortlist_candidates: list, 
    target_time_iso: str,
    current_path: str | None = None,
    wind_path: str | None = None
) -> dict:
    """
    Execute Stage 5: Forward drift from release points to the target detection time.
    """
    if not shortlist_candidates:
        return {"status": "failed", "reason": "No candidates provided in shortlist."}
        
    def _parse_time(iso_str):
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        # sometimes synthetic data adds duplicate +00:00
        if '+00:00+00:00' in iso_str:
            iso_str = iso_str.replace('+00:00+00:00', '+00:00')
        dt = datetime.datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt

    target_time = _parse_time(target_time_iso)
    
    results = []
    
    for cand in shortlist_candidates:
        position = cand.get("position_at_event")
        if not position:
            continue
        if isinstance(position, dict):
            lat, lon = position.get("lat", 0.0), position.get("lon", 0.0)
            rel_time_str = position.get("time") or cand.get("time") or target_time_iso
        elif isinstance(position, list) and len(position) >= 2:
            lat, lon = position[0], position[1]
            rel_time_str = cand.get("time") or target_time_iso
        else:
            continue

        release_time = _parse_time(rel_time_str)
        duration_hours = max(0.5, (target_time - release_time).total_seconds() / 3600.0)
        
        # Run forward simulation
        sim = run_forward([lat, lon], duration_hours, current_path, wind_path, rel_time_str)
        
        if sim.get("status") == "failed":
            return sim

        results.append({
            "mmsi": cand["mmsi"],
            "vessel_name": cand["vessel_name"],
            "simulated_polygon": sim["polygon"],
            "fallback_used": sim["fallback_used"]
        })
        
    return {
        "status": "success",
        "data": {
            "simulations": results
        }
    }
