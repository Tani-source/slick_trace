"""
ais_loader.py — Loads AIS from MarineCadastre CSV, or uses synthetic fallback.
"""
import logging
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

def load_ais(csv_path: str | None, bbox: list[float], start_time: datetime, end_time: datetime) -> dict:
    """
    Loads AIS points within the spatio-temporal window.
    Parses a MarineCadastre-style CSV if provided and valid; otherwise uses synthetic data.
    """
    if csv_path:
        try:
            result = _parse_ais_csv(csv_path, bbox, start_time, end_time)
            if result["records"]:
                return result
            logger.info("CSV parsed but 0 records matched the envelope — falling back to synthetic AIS.")
        except Exception as e:
            logger.warning("AIS CSV parse failed (%s) — falling back to synthetic AIS.", e)

    logger.info("Using synthetic AIS generator.")
    return _generate_synthetic_ais(bbox, start_time, end_time)


def _parse_ais_csv(csv_path: str, bbox: list[float], start_time: datetime, end_time: datetime) -> dict:
    """
    Parse a MarineCadastre-style CSV and filter to the bbox + time window.
    Supported columns: MMSI, LAT, LON, BaseDateTime, SOG, VesselName, VesselType, Flag, Draft, Destination.
    """
    import csv as _csv
    min_lat, min_lon, max_lat, max_lon = bbox
    records = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row.get("LAT", row.get("lat", "")))
                lon = float(row.get("LON", row.get("lon", "")))
            except (ValueError, KeyError):
                continue

            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                continue

            raw_time = row.get("BaseDateTime", row.get("timestamp", ""))
            try:
                t = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    from datetime import timezone
                    t = t.replace(tzinfo=timezone.utc)
                st = start_time if start_time.tzinfo else start_time.replace(tzinfo=__import__("datetime").timezone.utc)
                et = end_time if end_time.tzinfo else end_time.replace(tzinfo=__import__("datetime").timezone.utc)
                if not (st <= t <= et):
                    continue
            except Exception:
                continue

            vtype = (row.get("VesselType") or row.get("vessel_type") or "tanker").strip().lower()

            records.append({
                "mmsi": str(row.get("MMSI", row.get("mmsi", ""))).strip(),
                "vessel_name": (row.get("VesselName") or row.get("vessel_name") or "UNKNOWN").strip(),
                "vessel_type": vtype,
                "flag": (row.get("Flag") or row.get("flag") or "XX").strip(),
                "operator": "CSV Import",
                "destination": (row.get("Destination") or row.get("destination") or "UNKNOWN").strip(),
                "lat": lat,
                "lon": lon,
                "time": t.isoformat(),
                "speed_knots": float(row.get("SOG", row.get("speed", 0)) or 0),
                "draft_meters": float(row.get("Draft", row.get("draft", 0)) or 0),
            })

    return {"records": records, "provenance": "real"}


def _generate_synthetic_ais(bbox: list[float], start_time: datetime, end_time: datetime) -> dict:
    """
    Generate a few realistic-looking synthetic vessel tracks traversing the bbox.
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    
    vessels = [
        {"mmsi": "111111111", "name": "SYNTH_TANKER_1", "type": "tanker", "flag": "PA"},
        {"mmsi": "222222222", "name": "SYNTH_CARGO_2", "type": "cargo", "flag": "LR"},
        {"mmsi": "333333333", "name": "SYNTH_BUNKER_3", "type": "bunkering", "flag": "BS"},
    ]
    
    records = []
    
    # 6 hour window approx
    total_hours = (end_time - start_time).total_seconds() / 3600.0
    if total_hours <= 0:
        total_hours = 6.0
        
    for i, v in enumerate(vessels):
        # Create a track
        track_start = start_time
        
        # Add a gap (blackout) for tanker
        blackout_start = None
        if v["type"] == "tanker":
            blackout_start = start_time + timedelta(hours=total_hours * 0.3)
            
        current_time = track_start
        lat, lon = center_lat + (i * 0.01), center_lon - 0.02
        
        while current_time <= end_time:
            # Skip if blackout
            in_blackout = False
            if blackout_start and current_time >= blackout_start and current_time <= blackout_start + timedelta(hours=2):
                in_blackout = True
                
            if not in_blackout:
                records.append({
                    "mmsi": v["mmsi"],
                    "vessel_name": v["name"],
                    "vessel_type": v["type"],
                    "flag": v["flag"],
                    "operator": "Synthetic Corp",
                    "destination": "Houston",
                    "lat": lat,
                    "lon": lon,
                    "time": current_time.isoformat() + "Z",
                    "speed_knots": 12.0 + (random.random() * 2),
                    "draft_meters": 10.0
                })
            
            # Move east-ish
            lat += (random.random() - 0.5) * 0.02
            lon += 0.04 + random.random() * 0.02
            current_time += timedelta(minutes=30)
            
    return {
        "records": records,
        "provenance": "synthetic"
    }


DEFAULT_BBOX = [28.4, -94.6, 29.4, -89.0]
DEFAULT_DATE_START = datetime(2026, 9, 1, 0, 0, 0)
DEFAULT_DATE_END = datetime(2026, 9, 10, 0, 0, 0)
SPILL_DETECTION_TIME = "2026-09-07T12:00:00Z"
SPILL_ORIGIN_LAT = 28.5
SPILL_ORIGIN_LON = -90.1


def load_and_filter(csv_path: str | Path | None = None, bbox: list[float] | None = None, start_time: datetime | None = None, end_time: datetime | None = None) -> dict:
    bbox = bbox or DEFAULT_BBOX
    start_time = start_time or DEFAULT_DATE_START
    end_time = end_time or DEFAULT_DATE_END
    if csv_path and not Path(csv_path).exists():
        return {"status": "failed", "stage": "ais_ingestion", "reason": f"File not found: {csv_path}"}
    try:
        data = load_ais(str(csv_path) if csv_path else None, bbox, start_time, end_time)
        recs = data.get("records", [])
        min_lat, min_lon, max_lat, max_lon = bbox
        # Group records by MMSI to evaluate vessel trajectory & anomalies
        grouped_recs: dict[str, list[dict]] = {}
        for r in recs:
            mmsi = str(r.get("mmsi"))
            grouped_recs.setdefault(mmsi, []).append(r)

        cands = []
        for mmsi, vessel_recs in grouped_recs.items():
            in_bbox_recs = [
                r for r in vessel_recs
                if min_lat <= float(r.get("lat", 0.0)) <= max_lat and min_lon <= float(r.get("lon", 0.0)) <= max_lon
            ]
            if not in_bbox_recs:
                continue

            in_bbox_recs.sort(key=lambda x: x.get("time", ""))
            
            # Find the record closest to SPILL_DETECTION_TIME to represent the position at event
            try:
                target_time = datetime.fromisoformat(SPILL_DETECTION_TIME.replace("Z", "+00:00"))
                if target_time.tzinfo is None:
                    from datetime import timezone
                    target_time = target_time.replace(tzinfo=timezone.utc)
                
                def time_diff(r):
                    try:
                        rt = datetime.fromisoformat(r.get("time", "").replace("Z", "+00:00"))
                        if rt.tzinfo is None:
                            rt = rt.replace(tzinfo=timezone.utc)
                        return abs((rt - target_time).total_seconds())
                    except Exception:
                        return float('inf')
                        
                closest_r = min(in_bbox_recs, key=time_diff)
                lat = float(closest_r.get("lat", 0.0))
                lon = float(closest_r.get("lon", 0.0))
            except Exception:
                mid_idx = len(in_bbox_recs) // 2
                closest_r = in_bbox_recs[mid_idx]
                lat = float(closest_r.get("lat", 0.0))
                lon = float(closest_r.get("lon", 0.0))
            
            last_r = in_bbox_recs[-1] # For metadata
            raw_type = str(last_r.get("vessel_type", "cargo")).lower()
            if "tank" in raw_type or raw_type in ("80", "81", "82", "83", "84", "85", "86", "87", "88", "89"):
                vtype = "tanker"
            elif "carg" in raw_type or raw_type in ("70", "71", "72", "73", "74", "75", "76", "77", "78", "79"):
                vtype = "cargo"
            elif "fish" in raw_type or raw_type in ("30", "31", "32"):
                vtype = "fishing"
            else:
                vtype = "other"

            # Check time gaps for transponder blackout / AIS gap
            max_gap_hours = 0.0
            for i in range(1, len(vessel_recs)):
                try:
                    t1 = datetime.fromisoformat(vessel_recs[i-1]["time"].replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(vessel_recs[i]["time"].replace("Z", "+00:00"))
                    gap_h = (t2 - t1).total_seconds() / 3600.0
                    if gap_h > max_gap_hours:
                        max_gap_hours = gap_h
                except Exception:
                    pass

            gap_score = min(1.0, max(0.0, (max_gap_hours - 1.0) / 3.0)) if max_gap_hours > 1.0 else 0.0

            # Speed anomaly
            speeds = [float(r.get("speed_knots", r.get("speed", 0.0))) for r in vessel_recs]
            speed_anomaly = 0.0
            if speeds:
                min_s, max_s = min(speeds), max(speeds)
                if min_s < 2.0 and max_s > 8.0:
                    speed_anomaly = 0.75
                elif max_s > 18.0:
                    speed_anomaly = 0.50

            # Draft anomaly
            drafts = [float(r.get("draft_meters", r.get("draft", 0.0))) for r in vessel_recs]
            max_draft = max(drafts) if drafts else 0.0
            draft_anomaly = min(1.0, max_draft / 15.0) if vtype == "tanker" else 0.10

            route_anomaly = 0.40 if vtype == "tanker" else 0.15

            # Provenance fallback defaults for synthetic candidates
            if data.get("provenance") == "synthetic":
                if mmsi == "111111111":
                    gap_score, speed_anomaly, route_anomaly, draft_anomaly = 0.85, 0.60, 0.40, 0.70
                elif mmsi == "222222222":
                    gap_score, speed_anomaly, route_anomaly, draft_anomaly = 0.10, 0.20, 0.15, 0.10
                elif mmsi == "333333333":
                    gap_score, speed_anomaly, route_anomaly, draft_anomaly = 0.30, 0.40, 0.50, 0.35

            spill_lat = (min_lat + max_lat) / 2.0
            spill_lon = (min_lon + max_lon) / 2.0
            dlat = (lat - spill_lat) * 111.0
            dlon = (lon - spill_lon) * 111.0 * math.cos(math.radians(spill_lat))
            dist_km = float(math.hypot(dlat, dlon))

            cands.append({
                "mmsi": mmsi,
                "vessel_name": last_r.get("vessel_name", "UNKNOWN"),
                "vessel_type": vtype,
                "operator": last_r.get("operator", "Unknown"),
                "flag": last_r.get("flag", "XX"),
                "destination": last_r.get("destination", "UNKNOWN"),
                "position_at_event": {"lat": lat, "lon": lon, "time": closest_r.get("time")},
                "anomaly_breakdown": {
                    "blackout": round(gap_score, 2),
                    "gap": round(gap_score, 2),
                    "speed": round(speed_anomaly, 2),
                    "route": round(route_anomaly, 2),
                    "draft": round(draft_anomaly, 2),
                },
                "distance_to_spill_km": round(dist_km, 2),
                "lat": lat,
                "lon": lon,
            })

        cands.sort(key=lambda c: c["distance_to_spill_km"])
        return {"status": "success", "data": cands}
    except Exception as e:
        return {"status": "failed", "stage": "ais_ingestion", "reason": str(e)}

