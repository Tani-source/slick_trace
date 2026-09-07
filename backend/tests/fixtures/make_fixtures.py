from __future__ import annotations

from pathlib import Path

import numpy as np

FIXTURES_DIR = Path(__file__).resolve().parent


def build_sar_crop() -> np.ndarray:
    """Illustrative SAR-like intensity crop: bright sea with a dark slick patch."""
    arr = np.ones((128, 128), dtype=np.float32) * 0.8
    arr[50:80, 30:100] = 0.05
    return arr


def ensure_fixtures() -> Path:
    path = FIXTURES_DIR / "sar_crop.npy"
    if not path.exists():
        np.save(path, build_sar_crop())
    return path


if __name__ == "__main__":
    ensure_fixtures()
    print(ensure_fixtures())