# Synthetic Demo Data — SlickTrace

This directory contains **fully synthetic** data for the SlickTrace demo.
Everything is generated programmatically by `backend/scripts/generate_synthetic/`.

## Licence / acquisition
- No third-party copyright material.
- No downloads, no accounts, no licence acceptance.
- `python scripts/generate_all.py` reproduces exact files (deterministic seed).

## Why synthetic (documented tradeoff, per rules.md §3.1)
The plan calls for real Sentinel-1 / CMEMS / ERA5 / MarineCadastre data. Those sources each require free accounts and licence acceptance (hours–days of waiting) and the SAR training archive alone is ~40–97 GB. For a hackathon time budget the team chose **synthetic** data, clearly labelled, trading real-world coverage for a fast, deterministic, internally-consistent demo.
The physical model is simplified but motivated: the slick is advected through the same (synthetic) current+wind fields, and the culprit vessel's AIS track has a transponder blackout centred on the release.

## Files
- `forcing/currents.nc`, `forcing/wind.nc` — OpenDrift-compatible NetCDF
- `ais/tracks.csv` — MarineCadastre-format vessel tracks (~30 vessels)
- `sar/demo_scene.tif(.png)` — geolocated demo slick scene + mask
- `sar/oil_spill|no_oil|mask/` — U-Net training set (2-band VV/VH)
- `scenario.json` — ground truth tying all datasets together
- `provenance.json` — machine-readable provenance (served to Input tab)
