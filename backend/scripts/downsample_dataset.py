"""
downsample_dataset.py — Streamlined downsampling and disk optimization for real SAR dataset.
Downsamples 2048x2048 SAR images to 512x512 float32 (bilinear) and masks to 512x512 uint8 (nearest-neighbor).
Immediately deletes 2048x2048 files after downsampling to prevent disk bloat.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from PIL import Image
import tifffile


def process_single_file(path_str: str, target_shape: tuple[int, int] = (512, 512)) -> tuple[str, bool]:
    path = Path(path_str)
    try:
        data = tifffile.imread(path)
        is_mask = "mask" in str(path).lower()

        # If already at or smaller than target shape, skip
        h, w = data.shape[:2]
        if h <= target_shape[0] and w <= target_shape[1]:
            return str(path), False

        if is_mask:
            if data.ndim == 3:
                data = data[..., 0] if data.shape[-1] == 1 else data[:, :, 0]
            # Nearest-neighbor to strictly preserve binary 0/1 values
            res_pil = Image.fromarray(data.astype(np.uint8)).resize(target_shape, resample=Image.Resampling.NEAREST)
            resized = np.array(res_pil, dtype=np.uint8)
            # Write directly to original path (in-place replacement)
            tifffile.imwrite(path, resized, compression="zlib")
        else:
            # Multi-channel SAR image
            if data.ndim == 2:
                res_pil = Image.fromarray(data.astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR)
                resized = np.array(res_pil, dtype=np.float32)
            elif data.ndim == 3:
                if data.shape[-1] == 2:
                    c0 = np.array(Image.fromarray(data[:, :, 0].astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR))
                    c1 = np.array(Image.fromarray(data[:, :, 1].astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR))
                    resized = np.stack([c0, c1], axis=-1).astype(np.float32)
                elif data.shape[0] == 2:
                    c0 = np.array(Image.fromarray(data[0].astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR))
                    c1 = np.array(Image.fromarray(data[1].astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR))
                    resized = np.stack([c0, c1], axis=0).astype(np.float32)
                else:
                    c0 = np.array(Image.fromarray(data[..., 0].astype(np.float32)).resize(target_shape, resample=Image.Resampling.BILINEAR))
                    resized = c0.astype(np.float32)
            else:
                return str(path), False

            tifffile.imwrite(path, resized, compression="zlib")

        return str(path), True
    except Exception as e:
        print(f"Error processing {path}: {e}")
        return str(path), False


def downsample_directory(root_dir: str | Path, workers: int = 8) -> None:
    root = Path(root_dir)
    print(f"Scanning for TIFFs to downsample in '{root}'...")
    all_tifs = [str(p) for p in root.rglob("*.tif")]
    print(f"Found {len(all_tifs)} TIFF files.")

    t0 = time.time()
    processed = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_single_file, p): p for p in all_tifs}
        for future in as_completed(futures):
            _, success = future.result()
            if success:
                processed += 1
            if processed % 500 == 0 and processed > 0:
                print(f"  Processed {processed}/{len(all_tifs)} files ({time.time() - t0:.1f}s)...")

    elapsed = time.time() - t0
    print(f"Completed downsampling: {processed} files resized to 512x512 in {elapsed:.1f}s.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "backend/data/real/sar"
    downsample_directory(target)
