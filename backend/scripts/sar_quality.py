"""
sar_quality.py — Quality evaluation and filtering for Sentinel-1 SAR oil spill dataset.

Flags low-quality oil pairs if either:
1. Mask coverage > 20% of image area (alert-zone label artifact).
2. Radiometric contrast (mean SAR value inside mask minus mean SAR value outside mask) > -0.5 dB
   (masked region isn't meaningfully darker than surrounding water).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import tifffile


def evaluate_oil_pair_quality(
    mask: np.ndarray,
    sar: np.ndarray | None = None,
    max_coverage_pct: float = 20.0,
    max_contrast_db: float = -0.5,
    cls_name: str = "oil_spill",
) -> dict[str, Any]:
    """
    Evaluate quality of an image/mask pair.
    
    Returns dict:
      {
        'passed': bool,
        'coverage_pct': float,
        'contrast_db': float | None,
        'reasons': list[str]
      }
    """
    if mask.ndim == 3:
        mask = mask[..., 0] if mask.shape[-1] == 1 else mask[0]
    
    bin_mask = mask > 0
    total_px = mask.size
    pos_px = int(bin_mask.sum())
    coverage_pct = float((pos_px / total_px) * 100.0) if total_px > 0 else 0.0

    reasons: list[str] = []
    if coverage_pct > max_coverage_pct:
        reasons.append(f"excessive_coverage ({coverage_pct:.2f}% > {max_coverage_pct}%)")

    contrast_db: float | None = None
    if sar is not None:
        if sar.ndim == 3:
            if sar.shape[-1] <= 4:
                sar_ch = sar[..., 0]
            elif sar.shape[0] <= 4:
                sar_ch = sar[0]
            else:
                sar_ch = sar[..., 0]
        else:
            sar_ch = sar
        
        # Valid sea pixels: exclude zero-padding / swath borders (usually 0 or > -5 dB in raw dB SAR)
        valid_px = sar_ch < -5.0
        inside_valid = sar_ch[bin_mask & valid_px]
        outside_valid = sar_ch[(~bin_mask) & valid_px]

        # Fallback to unmasked if valid_px is empty (e.g. synthetic data)
        if len(inside_valid) == 0:
            inside_valid = sar_ch[bin_mask]
        if len(outside_valid) == 0:
            outside_valid = sar_ch[~bin_mask]

        if len(inside_valid) > 0 and len(outside_valid) > 0:
            contrast_db = float(inside_valid.mean() - outside_valid.mean())
            if contrast_db > max_contrast_db:
                reasons.append(f"insufficient_contrast ({contrast_db:.2f} dB > {max_contrast_db} dB)")
        elif pos_px == 0 and cls_name == "oil_spill":
            reasons.append("empty_oil_mask (0% oil)")

    passed = len(reasons) == 0
    return {
        "passed": passed,
        "coverage_pct": round(coverage_pct, 3),
        "contrast_db": round(contrast_db, 3) if contrast_db is not None else None,
        "reasons": reasons,
    }


def load_or_create_quality_report(report_path: Path) -> dict[str, Any]:
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
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


def save_quality_report(report: dict[str, Any], report_path: Path) -> None:
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    pairs = report.get("pairs", {})
    total = len(pairs)
    passed = sum(1 for p in pairs.values() if p.get("passed", False))
    flagged = total - passed
    report["summary"] = {
        "total_evaluated": total,
        "total_passed": passed,
        "total_flagged": flagged,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def update_pair_in_report(
    report: dict[str, Any],
    split: str,
    cls_name: str,
    filename: str,
    mask: np.ndarray,
    sar: np.ndarray | None = None,
) -> dict[str, Any]:
    """Evaluate and update a single pair in the quality report."""
    key = f"{cls_name}/{split}/{filename}"
    res = evaluate_oil_pair_quality(mask, sar, cls_name=cls_name)
    entry = {
        "split": split,
        "class": cls_name,
        "filename": filename,
        "coverage_pct": res["coverage_pct"],
        "contrast_db": res["contrast_db"],
        "passed": res["passed"],
        "reasons": res["reasons"],
    }
    report.setdefault("pairs", {})[key] = entry
    return entry
