"""
generate_quality_report.py — Retroactively evaluate existing SAR oil dataset
and build backend/data/real/sar/quality_report.json.
"""

from __future__ import annotations

import sys
from pathlib import Path
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sar_quality import (
    load_or_create_quality_report,
    save_quality_report,
    update_pair_in_report,
)


def run_retroactive_evaluation(data_root: str = "backend/data/real/sar", reset: bool = True) -> None:
    root = Path(data_root).resolve()
    report_path = root / "quality_report.json"
    
    # Start fresh if reset is requested to remove old colliding keys
    if reset:
        report = {
            "updated_at": "",
            "filter_criteria": {
                "max_coverage_pct": 20.0,
                "max_contrast_db": -0.5,
            },
            "summary": {
                "total_evaluated": 0,
                "total_passed": 0,
                "total_flagged": 0,
            },
            "pairs": {},
        }
    else:
        report = load_or_create_quality_report(report_path)

    print(f"Running comprehensive quality evaluation on {root} (namespaced keys)...")

    classes = ["oil_spill", "no_oil", "lookalike"]
    splits = ["test", "train"]

    for split in splits:
        for cls_name in classes:
            img_dir = root / cls_name / split
            msk_dir = root / f"{cls_name}_masks" / split
            if not msk_dir.exists():
                continue

            evaluated = 0
            flagged = 0
            for msk_p in sorted(msk_dir.glob("*.tif")):
                img_p = img_dir / msk_p.name
                msk = tifffile.imread(msk_p)
                sar = tifffile.imread(img_p) if img_p.exists() else None
                entry = update_pair_in_report(report, split, cls_name, msk_p.name, msk, sar)
                evaluated += 1
                if not entry["passed"]:
                    flagged += 1

            print(f"  {split:>5}/{cls_name:<12}: {evaluated:>4} evaluated, {evaluated - flagged:>4} passed, {flagged:>4} flagged")

    save_quality_report(report, report_path)
    print(f"\n[Saved] Quality report written to {report_path}")
    print(f"Total evaluated: {report['summary']['total_evaluated']}")
    print(f"Total passed:    {report['summary']['total_passed']}")
    print(f"Total flagged:   {report['summary']['total_flagged']}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "backend/data/real/sar"
    run_retroactive_evaluation(target)
