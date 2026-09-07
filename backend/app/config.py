from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("SLICKTRACE_DATA_DIR", BACKEND_DIR / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
RUNS_DIR = DATA_DIR / "runs"
CACHE_DIR = DATA_DIR / "cache"
PROTOTYPE_CACHE_DIR = CACHE_DIR / "prototype"

AGE_WEATHERING_LIMIT_HOURS = float(os.getenv("SLICKTRACE_AGE_LIMIT_HOURS", "72"))
WIND_VALID_RANGE_M_S: tuple[float, float] = (1.5, 10.0)
TOP_N_SHORTLIST = int(os.getenv("SLICKTRACE_TOP_N", "10"))

UNET_WEIGHTS_PATH = os.getenv("SLICKTRACE_UNET_WEIGHTS", "") or None

DEMO_SCENE_BBOX: list[float] = [28.4, -94.6, 29.4, -93.6]  # minLat, minLon, maxLat, maxLon
DEMO_PIXEL_SIZE_DEG = 0.003

DATASET_TYPES = ("wind", "current", "sar", "ais")


def ensure_dirs() -> None:
    for directory in (UPLOADS_DIR, RUNS_DIR, PROTOTYPE_CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)