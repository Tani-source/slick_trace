"""Download and extract the Zenodo Sentinel-1 SAR oil-spill dataset on a GPU host.

Runbook (Google Colab/Kaggle):
    1.  git clone <your repo>  (or upload backend/ and docs/)
    2.  cd backend
    3.  pip install requests py7zr
    4.  python scripts/download_sar_dataset.py            # all 3 parts (~97 GB)
        python scripts/download_sar_dataset.py --records i   # oil train only (40.7 GB)
    5.  python scripts/train_unet.py --data-dir data/dataset

Why this dataset: the DOI in team_tasks.md (10.5281/zenodo.1487237) is invalid —
that record is an unrelated herbarium image. The verified matching archive is
the Trujillo-Acatitla et al. (2024) "Sentinel-1 SAR Oil spill image dataset for
train, validate, and test deep learning models" (Marine Pollution Bulletin,
10.1016/j.marpolbul.2024.116549):

    Part I   10.5281/zenodo.8346860     1200 oil-spill training images + masks
    Part II  10.5281/zenodo.8253899     685 no-oil + 685 look-alike images + masks
    Part III 10.5281/zenodo.13761290    150 test images + masks (all classes)

Images are 2048x2048x2 Sigma0 dB (VV, VH) TIFFs; masks are 2048x2048, value 1
for the foreground. File lists are resolved live from the Zenodo API so this
script does not hardcode URLs or checksums. Downloads resume on interrupt and
verify MD5 before extracting. Extraction prefers py7zr and falls back to the
`7z` binary when available.

Zenodo may rate-limit large downloads; keep the Google Colab VM alive (open a
tab running something interactive) or re-run, since downloads resume.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import requests
    from requests import Response
except ImportError:
    sys.exit("requests is required:  pip install requests")

API = "https://zenodo.org/api/records"
PART_RECORDS: dict[str, tuple[str, int]] = {
    # label, display name, Zenodo record id for the current version
    "i": ("Part I — oil-spill train/val (images + masks)", 8346860),
    "ii": ("Part II — no-oil + look-alike train/val (images + masks)", 8253899),
    "iii": ("Part III — test images + masks (all classes)", 13761290),
}


def fetch_record_files(record_id: int) -> list[dict]:
    resp: Response = requests.get(f"{API}/{record_id}", timeout=60)
    resp.raise_for_status()
    record = resp.json()
    return record["files"]


def download_file(url: str, dest: Path) -> None:
    """Download with resume; a partial file that still passes MD5 is kept."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {}
    mode = "wb"
    if dest.exists():
        existing = dest.stat().st_size
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"
    with requests.get(url, headers=headers, stream=True, timeout=120) as resp:
        if resp.status_code == 416:
            print(f"    already complete: {dest.name}")
            return
        if resp.status_code not in (200, 206):
            resp.raise_for_status()
        if resp.status_code == 200 and mode == "ab":
            mode = "wb"
        total = int(resp.headers.get("content-length", 0)) + (dest.stat().st_size if mode == "ab" else 0)
        done = dest.stat().st_size if mode == "ab" else 0
        with open(dest, mode) as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                gib = 1024**3
                print(f"\r    {done / gib:6.2f} / {total / gib:6.2f} GiB", end="", flush=True)
        print()


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_7z(archive: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import py7zr  # type: ignore

        print(f"    extracting with py7zr: {archive.name}")
        with py7zr.SevenZipFile(archive, mode="r") as zf:
            zf.extractall(out_dir)
        return
    except ImportError:
        pass
    except Exception as exc:  # py7zr can fail on some filter combinations
        print(f"    py7zr failed ({exc}), trying 7z binary")
    if shutil.which("7z"):
        print(f"    extracting with 7z: {archive.name}")
        subprocess.run(["7z", "x", "-y", f"-o{out_dir}", str(archive)], check=True)
        return
    raise RuntimeError(
        "No extractor available: pip install py7zr (or install 7-Zip and put 7z on PATH)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        choices=["i", "ii", "iii", "all"],
        default="all",
        help="which Zenodo part(s) to fetch (default: all)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "dataset",
        help="root directory for archives + extracted folders",
    )
    parser.add_argument("--skip-extract", action="store_true", help="download only, do not extract")
    args = parser.parse_args()

    selected = ["i", "ii", "iii"] if args.records == "all" else list(args.records)
    records = [(label, *PART_RECORDS[label]) for label in selected]

    for label, title, record_id in records:
        print(f"\n=== {title} (Zenodo record {record_id}) ===")
        files = fetch_record_files(record_id)
        print(f"record files: {', '.join(f['key'] for f in files)}")
        for f in files:
            archive = args.dest / "raw" / f["key"]
            size_gib = f["size"] / 1024**3
            print(f"  {f['key']} ({size_gib:.2f} GiB)")
            download_file(f["links"]["self"], archive)
            expected = f["checksum"].split(":", 1)[-1]
            actual = md5_of(archive)
            if actual != expected:
                print(f"  MD5 MISMATCH for {archive.name} (expected {expected}, got {actual})")
                return 1
            print(f"  md5 ok: {actual}")
            if not args.skip_extract:
                extract_7z(archive, archive.with_suffix(""))

    dest = args.dest
    print("\nDone. Next step:")
    print(f"  python scripts/train_unet.py --data-dir {dest}")
    print(f"  (run from the backend/ directory; --data-dir may point anywhere in Colab, e.g. /content/dataset)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())