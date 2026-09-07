"""Write consolidated data provenance metadata for the synthetic dataset.

The dashboard's Input tab shows provenance tags per dataset (rules.md §3.1 —
synthetic data must be clearly labelled). This module emits a
``provenance.json`` that the backend can serve as the source for those tags,
and a ``README-data.md`` documenting licence-free / no-download status.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config as C


def write_provenance(
    out_dir: Path,
    n_ais_vessels: int,
    n_ais_rows: int,
    sar_counts: dict,
    slick_polygon_count: int,
) -> Path:
    meta = {
        "dataset": "SlickTrace Synthetic Demo Dataset",
        "provenance": "synthetic",
        "licence": "No third-party data. Generated programmatically, no co-pirated content.",
        "licence_note": "Free to use. No downloads, no accounts, no licence acceptance required.",
        "region": C.REGION_NAME,
        "bbox": C.BBOX,
        "forcing_window": [C.FORCING_START, C.FORCING_END],
        "deterministic": True,
        "seed_desc": "Seeded RNG; regeneration reproduces the exact same files.",
        "datasets": {
            "currents": {
                "path": "forcing/currents.nc",
                "format": "NetCDF-3 (CF)",
                "variables": ["uo", "vo"],
                "units": "m/s",
                "source": "synthetic (shelf current + anticyclonic eddy + M2 tide)",
                "size_approx_mb": None,
            },
            "wind": {
                "path": "forcing/wind.nc",
                "format": "NetCDF-3 (CF)",
                "variables": ["u10", "v10"],
                "units": "m/s",
                "source": "synthetic (synoptic + diurnal + red noise)",
                "size_approx_mb": None,
            },
            "ais": {
                "path": "ais/tracks.csv",
                "format": "CSV (MarineCadastre columns)",
                "n_vessels": n_ais_vessels,
                "n_rows": n_ais_rows,
                "source": "synthetic (realistic Gulf of Mexico traffic, incl. one blackout vessel)",
                "columns": ["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
                            "VesselName", "IMO", "CallSign", "VesselType", "Status",
                            "Length", "Width", "Draft", "Cargo", "TransceiverClass"],
            },
            "sar": {
                "demo_scene": "sar/demo_scene.tif + sar/demo_scene_mask.png",
                "training": sar_counts,
                "format": "TIFF (2-band VV,VH float32 dB) + PNG mask",
                "source": "synthetic (Rayleigh speckle, power-law clutter, dam ped slick)",
            },
            "scenario": {
                "path": "scenario.json",
                "slick_polygon_vertices": slick_polygon_count,
                "ground_truth": {
                    "origin": [C.ORIGIN_LAT, C.ORIGIN_LON],
                    "release_time": C.RELEASE_TIME,
                    "detection_time": C.DETECTION_TIME,
                    "culprit_mmsi": C.CULPRIT_MMSI,
                },
            },
        },
        "consistency": {
            "note": "All datasets share one seed and one scenario; the slick polygon is "
                    "advected through the same forcing fields the pipeline consults.",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "provenance.json"
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return p


def write_data_readme(out_dir: Path) -> Path:
    text = (
        "# Synthetic Demo Data — SlickTrace\n\n"
        "This directory contains **fully synthetic** data for the SlickTrace demo.\n"
        "Everything is generated programmatically by `backend/scripts/generate_synthetic/`.\n\n"
        "## Licence / acquisition\n"
        "- No third-party copyright material.\n"
        "- No downloads, no accounts, no licence acceptance.\n"
        "- `python scripts/generate_all.py` reproduces exact files (deterministic seed).\n\n"
        "## Why synthetic (documented tradeoff, per rules.md §3.1)\n"
        "The plan calls for real Sentinel-1 / CMEMS / ERA5 / MarineCadastre data. Those "
        "sources each require free accounts and licence acceptance (hours–days of waiting) "
        "and the SAR training archive alone is ~40–97 GB. For a hackathon time budget the "
        "team chose **synthetic** data, clearly labelled, trading real-world coverage for "
        "a fast, deterministic, internally-consistent demo.\n"
        "The physical model is simplified but motivated: the slick is advected through the "
        "same (synthetic) current+wind fields, and the culprit vessel's AIS track has a "
        "transponder blackout centred on the release.\n\n"
        "## Files\n"
        "- `forcing/currents.nc`, `forcing/wind.nc` — OpenDrift-compatible NetCDF\n"
        "- `ais/tracks.csv` — MarineCadastre-format vessel tracks (~30 vessels)\n"
        "- `sar/demo_scene.tif(.png)` — geolocated demo slick scene + mask\n"
        "- `sar/oil_spill|no_oil|mask/` — U-Net training set (2-band VV/VH)\n"
        "- `scenario.json` — ground truth tying all datasets together\n"
        "- `provenance.json` — machine-readable provenance (served to Input tab)\n"
    )
    p = out_dir / "README-data.md"
    p.write_text(text, encoding="utf-8")
    return p
