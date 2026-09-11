"""
organize_real_data.py — Organize extracted Zenodo SAR datasets into the SlickTrace structure.
Mirrors backend/data/synthetic/sar/ so discover_pairs() in train_unet.py works out of the box.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def organize_directory(source_dir: str | Path, target_dir: str | Path = "backend/data/real/sar") -> None:
    src = Path(source_dir).resolve()
    dst = Path(target_dir).resolve()

    print(f"Scanning source directory '{src}' for SAR images and masks...")
    all_tifs = list(src.rglob("*.tif"))
    print(f"Found {len(all_tifs)} TIFF files.")

    count = 0
    for p in all_tifs:
        p_str = str(p).lower()
        rel_str = str(p.relative_to(src)).lower()

        # Class determination
        if "lookalike" in rel_str or "look-alike" in rel_str or "look_alike" in rel_str:
            cls = "lookalike"
            cls_mask = "lookalike_masks"
        elif "no_oil" in rel_str or "no oil" in rel_str or "nooil" in rel_str:
            cls = "no_oil"
            cls_mask = "no_oil_masks"
        elif "oil" in rel_str:
            cls = "oil_spill"
            cls_mask = "oil_spill_masks"
        else:
            cls = "unknown"
            cls_mask = "unknown_masks"

        # Split determination
        split = "test" if ("test" in rel_str or "02_test" in p_str) else "train"

        # Kind determination (mask vs image)
        is_mask = any(k in rel_str for k in ("mask", "ground", "groundtruth", "gt_"))

        folder = cls_mask if is_mask else cls
        dest_dir = dst / folder / split
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / p.name

        if not dest_path.exists():
            shutil.copy2(p, dest_path)
            count += 1

    print(f"Organized {count} files into '{dst}'.")


if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "downloads/extracted"
    target = sys.argv[2] if len(sys.argv) > 2 else "backend/data/real/sar"
    organize_directory(source, target)
