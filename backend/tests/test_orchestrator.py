import json
from pathlib import Path
import pytest

from app.services.run_store import create_run, write_run_artifact, load_stage_output, run_dir

def test_artifact_bare_name_no_double_extension(tmp_path):
    run_id = "test_artifact_ext_run"
    create_run(run_id)

    payload = {"test": "data", "area_km2": 42.0}
    # Bare name without .json
    write_run_artifact(run_id, "slick_polygon", payload)

    # Must exist as slick_polygon.json, NEVER slick_polygon.json.json
    rdir = run_dir(run_id)
    correct_file = rdir / "slick_polygon.json"
    buggy_file = rdir / "slick_polygon.json.json"

    assert correct_file.exists(), f"Expected {correct_file} to exist"
    assert not buggy_file.exists(), f"Regression: double extension file {buggy_file} was created"

    # Reading it via load_stage_output must return the exact payload
    loaded = load_stage_output(run_id, "slick_polygon")
    assert loaded == payload

def test_scenario_detection_time_loading():
    scenario_path = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "scenario.json"
    if scenario_path.exists():
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        assert "detection_time" in data
        assert data["detection_time"].startswith("2024-09-14")
