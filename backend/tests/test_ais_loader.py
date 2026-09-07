"""
Tests for AIS loader — Stage 2/3.

Runs against the synthetic AIS fixture at:
  backend/data/synthetic/ais/tracks.csv

Run with: python -m pytest backend/tests/test_ais_loader.py -v
"""
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ais_loader import load_and_filter, DEFAULT_BBOX, DEFAULT_DATE_START, DEFAULT_DATE_END, SPILL_DETECTION_TIME, SPILL_ORIGIN_LAT, SPILL_ORIGIN_LON

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "ais" / "tracks.csv"


def test_load_returns_success():
    result = load_and_filter(FIXTURE)
    assert result["status"] == "success", result.get("reason")


def test_candidates_not_empty():
    result = load_and_filter(FIXTURE)
    assert len(result["data"]) > 0


def test_all_candidates_have_required_keys():
    result = load_and_filter(FIXTURE)
    required = {"mmsi", "vessel_name", "vessel_type", "position_at_event", "anomaly_breakdown", "distance_to_spill_km"}
    for cand in result["data"]:
        assert required.issubset(cand.keys()), f"Missing keys in candidate: {cand.get('mmsi')}"


def test_candidates_within_bbox():
    min_lat, min_lon, max_lat, max_lon = DEFAULT_BBOX
    result = load_and_filter(FIXTURE)
    for cand in result["data"]:
        lat = cand["position_at_event"]["lat"]
        lon = cand["position_at_event"]["lon"]
        assert min_lat <= lat <= max_lat, f"Lat {lat} out of bbox for {cand['mmsi']}"
        assert min_lon <= lon <= max_lon, f"Lon {lon} out of bbox for {cand['mmsi']}"


def test_vessel_types_are_relevant():
    result = load_and_filter(FIXTURE)
    valid_types = {"tanker", "cargo", "fishing", "other"}
    for cand in result["data"]:
        assert cand["vessel_type"] in valid_types, f"Unexpected type: {cand['vessel_type']}"


def test_sorted_by_distance():
    result = load_and_filter(FIXTURE)
    dists = [c["distance_to_spill_km"] for c in result["data"]]
    assert dists == sorted(dists), "Candidates should be sorted by distance to spill"


def test_missing_file_returns_failed():
    result = load_and_filter("/nonexistent/path.csv")
    assert result["status"] == "failed"
    assert result["stage"] == "ais_ingestion"


if __name__ == "__main__":
    import json

    print("Running AIS loader against synthetic fixture...\n")
    result = load_and_filter(FIXTURE)
    print(f"Status : {result['status']}")
    if result["status"] == "success":
        print(f"Candidates found: {len(result['data'])}")
        print(f"\nTop 5 by proximity to spill:\n")
        for c in result["data"][:5]:
            print(f"  MMSI {c['mmsi']} | {c['vessel_name']} | {c['vessel_type']} "
                  f"| {c['distance_to_spill_km']:.1f} km | blackout={c['anomaly_breakdown']['blackout']}")
    else:
        print(f"FAILED: {result['reason']}")
