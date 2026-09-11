"""
inspect_real_data.py — Inspection and visualization utility for real Sentinel-1 SAR dataset.
Loads sample image + mask pairs, prints shape/dtype/value ranges, computes oil pixel percentages,
and saves side-by-side visual previews to /tmp/real_data_preview/.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import tifffile


def find_dataset_pairs(data_dir: Path) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    """
    Find image and mask pairs for oil and non-oil/lookalike classes.
    Directly mirrors discover_pairs() from train_unet.py to ensure 100% compatibility.
    """
    try:
        from backend.scripts.train_unet import discover_pairs
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from train_unet import discover_pairs
    grouped = discover_pairs(data_dir)
    oil_pairs: list[tuple[Path, Path]] = []
    non_oil_pairs: list[tuple[Path, Path]] = []

    for (split, cls), pairs in grouped.items():
        if cls == "oil_spill":
            oil_pairs.extend(pairs)
        else:
            non_oil_pairs.extend(pairs)

    return oil_pairs, non_oil_pairs


def inspect_samples(data_dir: str | Path = "backend/data/real/sar", out_preview_dir: str | Path = "/tmp/real_data_preview") -> None:
    data_path = Path(data_dir)
    out_dir = Path(out_preview_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        print(f"Error: Dataset directory '{data_path}' does not exist.")
        return

    oil_pairs, non_oil_pairs = find_dataset_pairs(data_path)
    print(f"Discovered {len(oil_pairs)} oil pairs and {len(non_oil_pairs)} non-oil/look-alike pairs in {data_path}.\n")

    if not oil_pairs and not non_oil_pairs:
        # Check subdirectories directly
        print("Searching all tif files directly in directory hierarchy...")
        all_imgs = [p for p in data_path.rglob("*.tif") if "mask" not in str(p).lower()]
        all_masks = [p for p in data_path.rglob("*.tif") if "mask" in str(p).lower()]
        print(f"Total image files found: {len(all_imgs)}, mask files found: {len(all_masks)}")

    rng = random.Random(42)
    sample_oil = rng.sample(oil_pairs, min(3, len(oil_pairs))) if oil_pairs else []
    sample_nonoil = rng.sample(non_oil_pairs, min(3, len(non_oil_pairs))) if non_oil_pairs else []

    print("=" * 75)
    print("OIL SAMPLES INSPECTION (3 random pairs):")
    print("=" * 75)
    for i, (img_p, msk_p) in enumerate(sample_oil, 1):
        img = tifffile.imread(img_p)
        msk = tifffile.imread(msk_p)
        if msk.ndim == 3:
            msk = msk[..., 0] if msk.shape[-1] == 1 else msk[:, :, 0]

        total_px = msk.size
        pos_px = int((msk > 0).sum())
        pos_pct = (pos_px / total_px) * 100.0

        print(f"\n[Oil Sample {i}]")
        print(f"  Image: {img_p.relative_to(data_path)}")
        print(f"    Shape: {img.shape} | Dtype: {img.dtype} | Min: {img.min():.2f} | Max: {img.max():.2f} | Mean: {img.mean():.2f} | Std: {img.std():.2f}")
        print(f"  Mask:  {msk_p.relative_to(data_path)}")
        print(f"    Shape: {msk.shape} | Dtype: {msk.dtype} | Unique: {np.unique(msk).tolist()}")
        print(f"    Positive (oil) pixels: {pos_px:,} / {total_px:,} ({pos_pct:.3f}%)")

    print("\n" + "=" * 75)
    print("NO-OIL / LOOK-ALIKE SAMPLES INSPECTION (3 random pairs):")
    print("=" * 75)
    for i, (img_p, msk_p) in enumerate(sample_nonoil, 1):
        img = tifffile.imread(img_p)
        msk = tifffile.imread(msk_p)
        if msk.ndim == 3:
            msk = msk[..., 0] if msk.shape[-1] == 1 else msk[:, :, 0]

        total_px = msk.size
        pos_px = int((msk > 0).sum())
        pos_pct = (pos_px / total_px) * 100.0

        print(f"\n[Non-Oil / Lookalike Sample {i}]")
        print(f"  Image: {img_p.relative_to(data_path)}")
        print(f"    Shape: {img.shape} | Dtype: {img.dtype} | Min: {img.min():.2f} | Max: {img.max():.2f} | Mean: {img.mean():.2f} | Std: {img.std():.2f}")
        print(f"  Mask:  {msk_p.relative_to(data_path)}")
        print(f"    Shape: {msk.shape} | Dtype: {msk.dtype} | Unique: {np.unique(msk).tolist()}")
        print(f"    Positive (oil) pixels: {pos_px:,} / {total_px:,} ({pos_pct:.3f}%)")

    # Generate 3 side-by-side visualizations
    viz_samples = sample_oil[:2] + sample_nonoil[:1] if len(sample_oil) >= 2 else (sample_oil + sample_nonoil)[:3]
    print("\n" + "=" * 75)
    print(f"SAVING 3 SIDE-BY-SIDE VISUALIZATIONS TO {out_dir}:")
    print("=" * 75)

    for idx, (img_p, msk_p) in enumerate(viz_samples, 1):
        img = tifffile.imread(img_p)
        msk = tifffile.imread(msk_p)
        if msk.ndim == 3:
            msk = msk[..., 0] if msk.shape[-1] == 1 else msk[:, :, 0]

        # Use primary SAR channel (VV) for visualization
        sar_ch = img[..., 0] if (img.ndim == 3 and img.shape[-1] >= 1) else (img[0] if (img.ndim == 3 and img.shape[0] == 2) else img)
        
        # Robust percentile scaling for SAR contrast
        p1, p99 = np.percentile(sar_ch, (1, 99))
        sar_disp = np.clip((sar_ch - p1) / max(p99 - p1, 1e-6), 0.0, 1.0)

        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        
        # SAR Image
        im0 = axes[0].imshow(sar_disp, cmap="gray")
        axes[0].set_title(f"SAR (VV Channel)\n{img_p.name}", fontsize=11)
        axes[0].axis("off")
        plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

        # Ground Truth Mask
        im1 = axes[1].imshow(msk, cmap="hot", vmin=0, vmax=1)
        pos_pct = ((msk > 0).sum() / msk.size) * 100.0
        axes[1].set_title(f"Ground Truth Mask\nOil pixels: {pos_pct:.2f}% ({msk_p.name})", fontsize=11)
        axes[1].axis("off")
        plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

        plt.suptitle(f"Real Sentinel-1 SAR Inspection — Sample {idx}", fontsize=13, fontweight="bold")
        plt.tight_layout()

        out_file = out_dir / f"sample_{idx}_{img_p.stem}.png"
        plt.savefig(out_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  [Saved] {out_file}")

    print("\nInspection complete!")


if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "backend/data/real/sar"
    inspect_samples(target_dir)
