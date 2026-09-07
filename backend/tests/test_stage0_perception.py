from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.stage0_perception import run_stage0
from tests.fixtures.make_fixtures import ensure_fixtures

SAR_FIXTURE = ensure_fixtures()
SCENE = [28.4, -94.6, 29.4, -93.6]  # minLat, minLon, maxLat, maxLon


def _run(**kwargs) -> dict:
    defaults = {"run_id": "__test__", "input_path": SAR_FIXTURE, "scene_bbox": SCENE}
    defaults.update(kwargs)
    return run_stage0(**defaults)


def test_success_on_illustrative_dark_patch():
    result = _run()
    assert result["status"] == "success"
    assert result["data"]["area_km2"] > 0
    assert result["method"] == "threshold"


def test_polygon_within_scene_and_bbox_sane():
    result = _run()
    lat_min, lon_min, lat_max, lon_max = SCENE
    for lat, lon in result["data"]["polygon"]:
        assert lat_min <= lat <= lat_max
        assert lon_min <= lon <= lon_max
    b = result["data"]["bbox"]
    assert b[0] < b[2] and b[1] < b[3]


def test_elongation_ratio_finite_and_ge_one():
    result = _run()
    ratio = result["data"]["elongation_ratio"]
    assert ratio is not None
    assert ratio >= 1.0


def test_weathering_validity_true_for_fresh_heuristic():
    result = _run()
    assert result["data"]["weathering_validity"] is True
    assert result["data"]["age_estimate_hours"] is not None


def test_weathering_flag_false_when_age_exceeds_window():
    result = _run(age_override_hours=100.0)
    assert result["status"] == "success"
    assert result["data"]["weathering_validity"] is False
    assert result["data"]["age_confidence"] == "low"


def test_wind_below_window_rejects():
    result = _run(wind_speed_ms=0.5)
    assert result["status"] == "failed"
    assert "wind" in result["reason"].lower()


def test_wind_above_window_rejects():
    result = _run(wind_speed_ms=12.0)
    assert result["status"] == "failed"
    assert "wind" in result["reason"].lower()


def test_insufficient_contrast_rejects_as_look_alike(tmp_path):
    import PIL.Image as Image

    arr = np.ones((128, 128), dtype=np.float32) * 0.5
    arr[50:80, 30:100] = 0.485
    image_path = tmp_path / "low_contrast.png"
    Image.fromarray((arr * 255).astype("uint8"), mode="L").save(image_path)
    result = run_stage0(run_id="__test__", input_path=image_path, scene_bbox=SCENE)
    assert result["status"] == "failed"
    assert "contrast" in result["reason"].lower()


def test_empty_scene_no_dark_object_fails(tmp_path):
    arr = np.ones((128, 128), dtype=np.float32) * 0.8
    image_path = tmp_path / "empty_scene.png"
    import PIL.Image as Image

    Image.fromarray((arr * 255).astype("uint8"), mode="L").save(image_path)
    result = run_stage0(run_id="__test__", input_path=image_path, scene_bbox=SCENE)
    assert result["status"] == "failed"
    assert "dark object" in result["reason"].lower()