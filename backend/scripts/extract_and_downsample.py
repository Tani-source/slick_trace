"""
extract_and_downsample.py — Batch-extracts 7z archives, downsamples each TIFF to 512x512 immediately,
and purges the 2048x2048 raw files on the fly to minimize peak disk usage.
Deletes the .7z archive upon completion.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
import tifffile


def get_archive_file_list(archive_path: Path) -> list[str]:
    """List all file paths inside a 7z archive using 7zz."""
    cmd = ["/opt/homebrew/bin/7zz", "l", "-ba", "-slt", str(archive_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    files: list[str] = []
    current_path = None
    is_folder = False

    for line in res.stdout.splitlines():
        if line.startswith("Path = "):
            current_path = line[len("Path = "):].strip()
        elif line.startswith("Attributes = "):
            if "D" in line[len("Attributes = "):]:
                is_folder = True
            else:
                is_folder = False
        elif line == "":
            if current_path and not is_folder and current_path.lower().endswith(".tif"):
                files.append(current_path)
            current_path = None
            is_folder = False

    if current_path and not is_folder and current_path.lower().endswith(".tif"):
        files.append(current_path)

    return files


def determine_destination(file_rel_path: str, target_root: Path) -> Path:
    """Map archive relative path to organized target directory in 512x512 structure."""
    p = Path(file_rel_path)
    parts = [part.lower() for part in p.parts]
    inner_parts = parts[1:] if len(parts) > 1 and "test_images_and_ground_truth" in parts[0] else parts
    inner_str = "/".join(inner_parts)

    is_mask = False
    if any(part in ("images", "image", "img") for part in inner_parts[:-1]):
        is_mask = False
    elif any(k in inner_str for k in ("mask", "ground_truth", "groundtruth", "gt_", "ground")):
        is_mask = True
    elif any(k in p.name.lower() for k in ("mask", "gt_", "segmentation")):
        is_mask = True

    p_lower = file_rel_path.lower()
    if "lookalike" in p_lower or "look-alike" in p_lower or "look_alike" in p_lower:
        cls_folder = "lookalike_masks" if is_mask else "lookalike"
    elif "no_oil" in p_lower or "no oil" in p_lower or "nooil" in p_lower:
        cls_folder = "no_oil_masks" if is_mask else "no_oil"
    elif "oil" in p_lower:
        cls_folder = "oil_spill_masks" if is_mask else "oil_spill"
    else:
        cls_folder = "unknown_masks" if is_mask else "unknown"

    split = "test" if ("test" in p_lower or "02_test" in p_lower or "images/" in p_lower or "mask/" in p_lower) else "train"
    dest_dir = target_root / cls_folder / split
    dest_dir.mkdir(parents=True, exist_ok=True)

    clean_name = p.name
    for suffix in ("_segmentation.tif", "_segmentation.tiff", "_mask.tif", "_mask.tiff", "_gt.tif"):
        if clean_name.lower().endswith(suffix):
            clean_name = clean_name[: -len(suffix)] + (".tiff" if clean_name.lower().endswith(".tiff") else ".tif")
            break

    return dest_dir / clean_name


def downsample_tiff(src_path: Path, dst_path: Path, target_size: tuple[int, int] = (512, 512)) -> None:
    """Downsample a TIFF to 512x512 with proper interpolation and write to dst_path."""
    data = tifffile.imread(src_path)
    is_mask = "mask" in str(dst_path).lower()

    if is_mask:
        if data.ndim == 3:
            data = data[..., 0] if data.shape[-1] == 1 else data[:, :, 0]
        # Nearest-neighbor to strictly preserve binary 0/1 values
        res_pil = Image.fromarray(data.astype(np.uint8)).resize(target_size, resample=Image.Resampling.NEAREST)
        resized = np.array(res_pil, dtype=np.uint8)
    else:
        # Dual-polarization SAR image (VV, VH)
        if data.ndim == 2:
            res_pil = Image.fromarray(data.astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR)
            resized = np.array(res_pil, dtype=np.float32)
        elif data.ndim == 3:
            if data.shape[-1] == 2:
                c0 = np.array(Image.fromarray(data[:, :, 0].astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR))
                c1 = np.array(Image.fromarray(data[:, :, 1].astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR))
                resized = np.stack([c0, c1], axis=-1).astype(np.float32)
            elif data.shape[0] == 2:
                c0 = np.array(Image.fromarray(data[0].astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR))
                c1 = np.array(Image.fromarray(data[1].astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR))
                resized = np.stack([c0, c1], axis=0).astype(np.float32)
            else:
                c0 = np.array(Image.fromarray(data[..., 0].astype(np.float32)).resize(target_size, resample=Image.Resampling.BILINEAR))
                resized = c0.astype(np.float32)
        else:
            raise ValueError(f"Unexpected array shape {data.shape} in {src_path}")

    tifffile.imwrite(dst_path, resized, compression="zlib")


def process_archive(archive_path: str | Path, target_root: str | Path = "backend/data/real/sar", batch_size: int = 50, delete_archive_after: bool = True) -> None:
    arc = Path(archive_path).resolve()
    target = Path(target_root).resolve()

    if not arc.exists():
        print(f"Archive '{arc}' does not exist.")
        return

    print(f"\n========================================================")
    print(f"Processing archive: {arc.name} ({arc.stat().st_size / (1024*1024):.1f} MB)")
    print(f"========================================================")

    file_list = get_archive_file_list(arc)
    total_files = len(file_list)
    print(f"Archive contains {total_files} TIFF files.")

    t0 = time.time()
    processed_count = 0

    with tempfile.TemporaryDirectory(prefix="sar_downsample_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Process in batches
        for i in range(0, total_files, batch_size):
            batch = file_list[i:i + batch_size]
            batch_t0 = time.time()

            # Extract current batch into temp folder
            cmd = ["/opt/homebrew/bin/7zz", "x", "-y", f"-o{tmp_path}", str(arc)] + batch
            subprocess.run(cmd, capture_output=True, check=True)

            # Immediately downsample and delete extracted raw 2048x2048 files
            for rel_file in batch:
                extracted_file = tmp_path / rel_file
                if not extracted_file.exists():
                    # Handle flat extraction or folder variants
                    candidates = list(tmp_path.rglob(Path(rel_file).name))
                    extracted_file = candidates[0] if candidates else None

                if extracted_file and extracted_file.exists():
                    dest_file = determine_destination(rel_file, target)
                    downsample_tiff(extracted_file, dest_file)
                    # Delete full-resolution file immediately!
                    extracted_file.unlink()
                    processed_count += 1

            # Clean any remaining temp files in batch dir
            for item in tmp_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

            elapsed = time.time() - t0
            print(f"  Processed {processed_count}/{total_files} ({processed_count/total_files*100:.1f}%) in {elapsed:.1f}s...")

    print(f"Finished downsampling {processed_count} files from {arc.name} to 512x512!")

    if delete_archive_after:
        print(f"Deleting archive '{arc.name}' to free disk space...")
        arc.unlink(missing_ok=True)
        aria2_file = arc.with_suffix(arc.suffix + ".aria2")
        aria2_file.unlink(missing_ok=True)
        print("Archive deleted successfully.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        archive = sys.argv[1]
        target_dir = sys.argv[2] if len(sys.argv) > 2 else "backend/data/real/sar"
        process_archive(archive, target_dir)
    else:
        print("Usage: python extract_and_downsample.py <path_to_7z_archive> [target_directory]")
