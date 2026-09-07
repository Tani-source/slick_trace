"""Generate the complete SlickTrace synthetic demo dataset.

Run from the ``backend/`` directory:

    python scripts/generate_all.py [--seed 7] [--n-train 60]

This creates everything under ``backend/data/synthetic/``:

    forcing/currents.nc, forcing/wind.nc     (OpenDrift-compatible NetCDF)
    ais/tracks.csv                            (MarineCadastre-format AIS)
    sar/demo_scene.tif + demo_scene_mask.png  (geolocated demo slick)
    sar/{oil_spill,no_oil,mask}/train/*.tif   (U-Net training set)
    scenario.json                             (ground truth)
    provenance.json + README-data.md          (consistency / provenance)

All randomness is seeded so regeneration is byte-for-byte reproducible.
No downloads, no accounts, no licence acceptance; total size is a few
hundred MB (well under the 1 GB budget).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from generate_synthetic import config as C
from generate_synthetic import ais, forcing, provenance, sar, slick


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7, help="RNG seed (default 7)")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "synthetic",
                        help="output root (default backend/data/synthetic)")
    parser.add_argument("--n-train", type=int, default=60,
                        help="number of SAR training patches to render (default 60)")
    args = parser.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(args.seed)
    out = args.out

    print(f"seed={args.seed}  output={out}")

    # 1) Forcing (currents + wind)
    print("[1/6] generating forcing fields (currents.nc, wind.nc) ...")
    forcing.generate_currents(out / "forcing", rng)
    forcing.generate_wind(out / "forcing", rng)

    # 2) Slick advection → polygon
    print("[2/6] advecting slick particles through forcing ...")
    ilats, ilons, flats, flons, hist_lat, hist_lon = slick.advect_particles(
        out / "forcing" / "currents.nc", out / "forcing" / "wind.nc", rng)
    slick_meta = slick.compute_slick_polygon(flats, flons)
    print(f"      slick area={slick_meta['area_km2']} km², "
          f"elongation={slick_meta['elongation_ratio']}")

    # 3) AIS tracks
    print("[3/6] generating AIS vessel tracks ...")
    ais_path = ais.generate_ais(out / "ais", rng)
    import csv
    with open(ais_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    n_mmsi = len({r["MMSI"] for r in rows})

    # 4) Scenario ground-truth JSON
    print("[4/6] writing scenario ground truth ...")
    slick.save_scenario(out, slick_meta, hist_lat, hist_lon)

    # 5) SAR demo scene + training set
    print(f"[5/6] rendering SAR demo scene + {args.n_train} training patches ...")
    sar.render_demo_scene(out / "sar", slick_meta["polygon"], rng)
    sar_counts = sar.render_training_scenes(out / "sar", args.n_train, rng)
    print(f"      {sar_counts['oil']} oil_spill + {sar_counts['no_oil']} no_oil scenes")

    # 6) Provenance
    print("[6/6] writing provenance metadata ...")
    provenance.write_provenance(out, n_mmsi, len(rows), sar_counts,
                                len(slick_meta["polygon"]))
    provenance.write_data_readme(out)

    def _dir_size(d: Path) -> str:
        total = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
        return f"{total / 1e6:.1f} MB"

    print(f"\nDone in {time.time() - t0:.1f}s.")
    for sub in ("forcing", "ais", "sar"):
        print(f"  {sub:8s} {_dir_size(out / sub)}")
    print(f"  {'total':8s} {_dir_size(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
