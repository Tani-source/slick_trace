"""
process_all_real_data.py — Sequential download, streaming batch downsampling (512x512),
and disk cleanup for the complete Zenodo Sentinel-1 SAR oil spill dataset.

Ensures:
1. Only one archive is downloaded at a time.
2. Full-resolution 2048x2048 TIFFs are batch-extracted into /tmp, immediately resized to 512x512
   (bilinear for SAR float32 channels, nearest-neighbor for binary uint8 masks), and unlinked.
   2048x2048 and 512x512 files never coexist on disk.
3. Each .7z archive is immediately deleted upon completing its downsampling to free disk space.
4. Total final disk usage of backend/data/real/sar/ remains < 3.5 GB (instead of 113 GB).
5. Inspects real dataset and regenerates /tmp/real_data_preview/ previews.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sar_quality import (
    evaluate_oil_pair_quality,
    load_or_create_quality_report,
    save_quality_report,
    update_pair_in_report,
)


ZENODO_PARTS = [
    {
        "name": "Part III (Test Set - Oil, Lookalike, No-Oil)",
        "archive_name": "02_Test_images_and_ground_truth.7z",
        "url": "https://zenodo.org/api/records/13761290/files/02_Test_images_and_ground_truth.7z/content",
        "expected_count": 900,  # 450 images + 450 masks
    },
    {
        "name": "Part I (Oil Spill Train Images)",
        "archive_name": "01_Train_Val_Oil_Spill_images.7z",
        "url": "https://zenodo.org/api/records/8346860/files/01_Train_Val_Oil_Spill_images.7z/content",
        "expected_count": 1200,
    },
    {
        "name": "Part II (No-Oil Train Images)",
        "archive_name": "01_Train_Val_No_Oil_Images.7z",
        "url": "https://zenodo.org/api/records/8253899/files/01_Train_Val_No_Oil_Images.7z/content",
        "expected_count": 685,
    },
    {
        "name": "Part II (Lookalike Train Images)",
        "archive_name": "01_Train_Val_Lookalike_images.7z",
        "url": "https://zenodo.org/api/records/8253899/files/01_Train_Val_Lookalike_images.7z/content",
        "expected_count": 685,
    },
]


def get_archive_file_list(archive_path: Path) -> list[str]:
    """List all TIFF file paths inside a 7z archive using 7zz."""
    cmd = ["/opt/homebrew/bin/7zz", "l", "-ba", "-slt", str(archive_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    files: list[str] = []
    current_path = None
    is_folder = False

    for line in res.stdout.splitlines():
        if line.startswith("Path = "):
            current_path = line[len("Path = "):].strip()
        elif line.startswith("Attributes = "):
            is_folder = "D" in line[len("Attributes = "):]
        elif line == "":
            if current_path and not is_folder and current_path.lower().endswith((".tif", ".tiff")):
                files.append(current_path)
            current_path = None
            is_folder = False

    if current_path and not is_folder and current_path.lower().endswith((".tif", ".tiff")):
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
        # Strict binary 0/1 uint8 conversion with nearest-neighbor to prevent interpolation artifacts
        bin_data = (data > 0).astype(np.uint8)
        res_pil = Image.fromarray(bin_data).resize(target_size, resample=Image.Resampling.NEAREST)
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


def download_with_aria2(url: str, output_path: Path) -> None:
    """Download archive using aria2c with 16 parallel connections."""
    dest_dir = output_path.parent
    file_name = output_path.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "/opt/homebrew/bin/aria2c",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        "-j", "16",
        "-c",  # resume partial download
        "-d", str(dest_dir),
        "-o", file_name,
        url,
    ]
    print(f"\n[Aria2c] Starting download: {file_name} from {url}")
    subprocess.run(cmd, check=True)
    print(f"[Aria2c] Completed download: {output_path} ({output_path.stat().st_size / (1024**3):.2f} GiB)")


def process_archive(
    archive_path: Path,
    target_root: Path,
    quality_report: dict[str, Any] | None = None,
    report_path: Path | None = None,
    batch_size: int = 50,
) -> int:
    """Batch-extract archive into temp dir, downsample immediately, evaluate quality filter inline, delete raw files, delete archive."""
    print(f"\nProcessing archive: {archive_path.name} ({archive_path.stat().st_size / (1024**2):.1f} MB)")
    file_list = get_archive_file_list(archive_path)
    total_files = len(file_list)
    print(f"Archive contains {total_files} TIFF files.")

    t0 = time.time()
    processed_count = 0
    flagged_in_archive = 0

    with tempfile.TemporaryDirectory(prefix="sar_extract_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for i in range(0, total_files, batch_size):
            batch = file_list[i:i + batch_size]

            # Extract batch
            cmd = ["/opt/homebrew/bin/7zz", "x", "-y", f"-o{tmp_path}", str(archive_path)] + batch
            subprocess.run(cmd, capture_output=True, check=True)

            # Immediately downsample and unlink raw files
            for rel_file in batch:
                extracted_file = tmp_path / rel_file
                if not extracted_file.exists():
                    candidates = list(tmp_path.rglob(Path(rel_file).name))
                    extracted_file = candidates[0] if candidates else None

                if extracted_file and extracted_file.exists():
                    dest_file = determine_destination(rel_file, target_root)
                    downsample_tiff(extracted_file, dest_file)
                    extracted_file.unlink()
                    processed_count += 1

                    # Evaluate quality filter inline if quality_report is provided
                    if quality_report is not None:
                        is_img = "mask" not in str(dest_file).lower()
                        is_oil = "oil_spill" in str(dest_file).lower() and is_img
                        is_lookalike = "lookalike" in str(dest_file).lower() and is_img
                        is_no_oil = "no_oil" in str(dest_file).lower() and is_img

                        if is_oil or is_lookalike or is_no_oil:
                            cls_name = "oil_spill" if is_oil else ("lookalike" if is_lookalike else "no_oil")
                            split_name = dest_file.parent.name
                            mask_file = target_root / f"{cls_name}_masks" / split_name / dest_file.name
                            if mask_file.exists():
                                try:
                                    mask_arr = tifffile.imread(mask_file)
                                    sar_arr = tifffile.imread(dest_file)
                                    entry = update_pair_in_report(
                                        quality_report,
                                        split=split_name,
                                        cls_name=cls_name,
                                        filename=dest_file.name,
                                        mask=mask_arr,
                                        sar=sar_arr,
                                    )
                                    if not entry["passed"]:
                                        flagged_in_archive += 1
                                        reasons_str = ", ".join(entry["reasons"])
                                        print(f"    [Quality Filter Flagged] {cls_name}/{split_name}/{dest_file.name}: {reasons_str}")
                                except Exception as e:
                                    print(f"    [Quality Filter Warning] {dest_file.name}: {e}")

            # Clean temporary dir
            for item in tmp_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

            # Persist quality report after each batch
            if quality_report is not None and report_path is not None:
                save_quality_report(quality_report, report_path)

            elapsed = time.time() - t0
            print(f"  Processed {processed_count}/{total_files} ({processed_count/total_files*100:.1f}%) in {elapsed:.1f}s (flagged in archive: {flagged_in_archive})...")

    if quality_report is not None and report_path is not None:
        save_quality_report(quality_report, report_path)

    print(f"[Success] Extracted and downsampled {processed_count} files from {archive_path.name} to 512x512 (flagged: {flagged_in_archive}).")

    # Delete archive immediately to free disk space
    print(f"Deleting archive '{archive_path.name}' to reclaim disk space...")
    archive_path.unlink(missing_ok=True)
    aria2_file = archive_path.with_suffix(archive_path.suffix + ".aria2")
    aria2_file.unlink(missing_ok=True)
    print("Archive deleted.")
    return processed_count


def run_pipeline(target_root: str = "backend/data/real/sar", downloads_dir: str = "downloads") -> None:
    target_path = Path(target_root).resolve()
    target_path.mkdir(parents=True, exist_ok=True)
    dl_dir = Path(downloads_dir).resolve()
    dl_dir.mkdir(parents=True, exist_ok=True)

    report_path = target_path / "quality_report.json"
    quality_report = load_or_create_quality_report(report_path)

    print("================================================================================")
    print("STARTING COMPLETE REAL SAR DATASET STREAMING PIPELINE (WITH QUALITY FILTER)")
    print(f"Target directory: {target_path}")
    print(f"Downloads directory: {dl_dir}")
    print(f"Quality report: {report_path}")
    print("================================================================================")

    for part in ZENODO_PARTS:
        name = part["name"]
        arc_name = part["archive_name"]
        url = part["url"]
        exp_count = part["expected_count"]
        arc_file = dl_dir / arc_name

        print(f"\n--- Checking {name} ---")

        # Check if already processed
        # If the destination files already exist in target_root, we can skip downloading!
        if arc_name == "01_Train_Val_Oil_Spill_images.7z":
            existing = len(list((target_path / "oil_spill" / "train").glob("*.tif")))
            if existing >= exp_count:
                print(f"Skipping {name}: already have {existing} images in oil_spill/train.")
                if arc_file.exists():
                    arc_file.unlink()
                continue
        elif arc_name == "01_Train_Val_No_Oil_Images.7z":
            existing = len(list((target_path / "no_oil" / "train").glob("*.tif")))
            if existing >= exp_count:
                print(f"Skipping {name}: already have {existing} images in no_oil/train.")
                if arc_file.exists():
                    arc_file.unlink()
                continue
        elif arc_name == "01_Train_Val_Lookalike_images.7z":
            existing = len(list((target_path / "lookalike" / "train").glob("*.tif")))
            if existing >= exp_count:
                print(f"Skipping {name}: already have {existing} images in lookalike/train.")
                if arc_file.exists():
                    arc_file.unlink()
                continue
        elif arc_name == "02_Test_images_and_ground_truth.7z":
            existing_oil = len(list((target_path / "oil_spill" / "test").glob("*.tif")))
            if existing_oil >= 150:
                print(f"Skipping {name}: already have {existing_oil} test images.")
                if arc_file.exists():
                    arc_file.unlink()
                continue

        # Check if an aria2 download is already running in background for this file
        aria2_lock = arc_file.with_suffix(arc_file.suffix + ".aria2")
        while True:
            # Check if aria2c is actively writing to this file
            res = subprocess.run(["pgrep", "-f", f"aria2c.*{arc_name}"], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"Aria2c download is currently running for {arc_name}. Waiting 15s...")
                time.sleep(15)
            else:
                break

        # Download if archive doesn't exist
        if not arc_file.exists() or aria2_lock.exists():
            download_with_aria2(url, arc_file)

        # Batch-extract, downsample to 512x512, evaluate quality, and delete archive
        process_archive(arc_file, target_path, quality_report=quality_report, report_path=report_path)

    # Run inspection
    print("\n================================================================================")
    print("RUNNING INSPECTION SCRIPT ON PROCESSED 512x512 REAL DATASET")
    print("================================================================================")
    cmd = [
        sys.executable,
        "backend/scripts/inspect_real_data.py",
        str(target_path),
    ]
    subprocess.run(cmd, check=True)

    # Final disk report
    print("\n================================================================================")
    print("FINAL DISK USAGE & CLEANUP CONFIRMATION")
    print("================================================================================")
    subprocess.run(["du", "-sh", str(target_path)])
    
    # Check for any remaining 7z archives
    rem_7z = list(dl_dir.glob("*.7z")) + list(target_path.glob("**/*.7z"))
    print(f"Remaining .7z archives: {len(rem_7z)} {rem_7z}")
    assert len(rem_7z) == 0, f"Error: Some .7z archives still remain: {rem_7z}"
    print("Confirmed: All .7z archives deleted successfully.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "backend/data/real/sar"
    run_pipeline(target)
