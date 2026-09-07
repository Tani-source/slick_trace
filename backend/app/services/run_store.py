from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ..config import RUNS_DIR, UPLOADS_DIR

_lock = threading.Lock()


def _safe_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


def upload_dir(run_id: str) -> Path:
    return UPLOADS_DIR / run_id


def run_exists(run_id: str) -> bool:
    return run_dir(run_id).is_dir()


def create_run(run_id: str) -> dict:
    with _lock:
        path = run_dir(run_id)
        path.mkdir(parents=True, exist_ok=True)
        inputs_path = path / "inputs.json"
        if not inputs_path.exists():
            _safe_write(inputs_path, {"run_id": run_id, "datasets": {}})
    return load_run(run_id)


def load_run(run_id: str) -> dict | None:
    return _read_json(run_dir(run_id) / "inputs.json")


def save_run(run_id: str, payload: dict) -> None:
    _safe_write(run_dir(run_id) / "inputs.json", payload)


def all_datasets(run_id: str) -> dict:
    data = load_run(run_id) or {}
    return data.get("datasets", {})


def get_dataset(run_id: str, dataset_type: str) -> dict | None:
    return all_datasets(run_id).get(dataset_type)


def record_upload(run_id: str, dataset_type: str, info: dict) -> None:
    with _lock:
        data = load_run(run_id) or create_run(run_id)
        data.setdefault("datasets", {})[dataset_type] = info
        save_run(run_id, data)


def save_upload_bytes(run_id: str, dataset_type: str, filename: str, content: bytes) -> Path:
    directory = upload_dir(run_id)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    path = directory / f"{dataset_type}{suffix}"
    path.write_bytes(content)
    return path


def uploaded_file(run_id: str, dataset_type: str) -> Path | None:
    directory = upload_dir(run_id)
    if not directory.is_dir():
        return None
    matches = sorted(directory.glob(f"{dataset_type}.*"))
    return matches[0] if matches else None


def load_pipeline_status(run_id: str) -> dict | None:
    return _read_json(run_dir(run_id) / "pipeline_status.json")


def save_pipeline_status(run_id: str, payload: dict) -> None:
    _safe_write(run_dir(run_id) / "pipeline_status.json", payload)


def save_stage_output(run_id: str, name: str, payload: dict) -> None:
    _safe_write(run_dir(run_id) / f"{name}.json", payload)


def load_stage_output(run_id: str, name: str) -> dict | None:
    return _read_json(run_dir(run_id) / f"{name}.json")


# Alias helpers for orchestrator compatibility
write_run_artifact = save_stage_output
read_run_artifact = load_stage_output
upload_path = uploaded_file


def update_stage(run_id: str, stage_name: str, status: str, progress: int = 0, message: str = "") -> None:
    current = load_pipeline_status(run_id) or {"run_id": run_id, "stages": {}}
    stages = current.setdefault("stages", {})
    stages[stage_name] = {
        "status": status,
        "progress": progress,
        "message": message,
    }
    save_pipeline_status(run_id, current)