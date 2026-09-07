import pytest
from app.pipeline.stage6_matching import run_matching, compute_metrics

def test_stage6_matching_hand_calculated_iou():
    # Square 1: [0, 0] to [2, 2] -> Area = 4
    poly1 = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]
    # Square 2: [1, 0] to [3, 2] -> Area = 4
    poly2 = [[1.0, 0.0], [3.0, 0.0], [3.0, 2.0], [1.0, 2.0], [1.0, 0.0]]

    # Intersection: [1, 0] to [2, 2] -> Area = 2
    # Union: Area = 4 + 4 - 2 = 6
    # IoU: 2 / 6 = 0.33333333...
    iou, overlap_km2, dist_km = compute_metrics(poly1, poly2)
    assert abs(iou - 1.0 / 3.0) < 1e-4

def test_stage6_matching_ranking_differentiation():
    observed_slick = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]

    simulations = [
        {
            "mmsi": "111111111",
            "vessel_name": "HIGH_OVERLAP_VESSEL",
            "simulated_polygon": [[0.5, 0.5], [2.5, 0.5], [2.5, 2.5], [0.5, 2.5], [0.5, 0.5]],
        },
        {
            "mmsi": "222222222",
            "vessel_name": "ZERO_OVERLAP_VESSEL",
            "simulated_polygon": [[10.0, 10.0], [12.0, 10.0], [12.0, 12.0], [10.0, 12.0], [10.0, 10.0]],
        }
    ]

    res = run_matching(simulations, observed_slick)
    assert res["status"] == "success"
    ranking = res["data"]["ranking"]

    assert len(ranking) == 2
    assert ranking[0]["mmsi"] == "111111111"
    assert ranking[0]["rank"] == 1
    assert ranking[0]["match_score"] > 0.0

    assert ranking[1]["mmsi"] == "222222222"
    assert ranking[1]["rank"] == 2
    assert ranking[1]["match_score"] == 0.0
