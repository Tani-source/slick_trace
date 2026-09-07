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


def test_mmsi_deduplication_regression(tmp_path):
    # Multiple points for the same MMSI must yield exactly 1 candidate
    csv_file = tmp_path / "tracks_dupe.csv"
    csv_file.write_text(
        "MMSI,BaseDateTime,LAT,LON,SOG,VesselName,VesselType,Draft\n"
        "111111111,2026-09-02T01:00:00Z,28.5,-90.0,12.0,TANKER_A,80,10.0\n"
        "111111111,2026-09-02T01:30:00Z,28.6,-89.9,12.0,TANKER_A,80,10.0\n"
        "111111111,2026-09-02T02:00:00Z,28.7,-89.8,12.0,TANKER_A,80,10.0\n"
        "222222222,2026-09-02T01:00:00Z,28.5,-90.0,14.0,CARGO_B,70,8.0\n"
    )
    res = load_and_filter(csv_file, bbox=[28.0, -91.0, 29.0, -89.0])
    assert res["status"] == "success"
    cands = res["data"]
    assert len(cands) == 2
    mmsis = [c["mmsi"] for c in cands]
    assert set(mmsis) == {"111111111", "222222222"}
    assert len(mmsis) == len(set(mmsis))


def test_numeric_vessel_type_mapping(tmp_path):
    csv_file = tmp_path / "vessel_types.csv"
    csv_file.write_text(
        "MMSI,BaseDateTime,LAT,LON,SOG,VesselName,VesselType,Draft\n"
        "100000001,2026-09-02T01:00:00Z,28.5,-90.0,10.0,V_TANKER,80,10.0\n"
        "100000002,2026-09-02T01:00:00Z,28.5,-90.0,10.0,V_CARGO,70,10.0\n"
        "100000003,2026-09-02T01:00:00Z,28.5,-90.0,10.0,V_FISHING,30,10.0\n"
        "100000004,2026-09-02T01:00:00Z,28.5,-90.0,10.0,V_OTHER,99,10.0\n"
    )
    res = load_and_filter(csv_file, bbox=[28.0, -91.0, 29.0, -89.0])
    assert res["status"] == "success"
    cands = {c["mmsi"]: c["vessel_type"] for c in res["data"]}
    assert cands["100000001"] == "tanker"
    assert cands["100000002"] == "cargo"
    assert cands["100000003"] == "fishing"
    assert cands["100000004"] == "other"



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
