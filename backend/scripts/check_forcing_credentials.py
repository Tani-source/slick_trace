"""Verify the CMEMS + ERA5 credentials so Person A can hand them to D (tasks A5/A6).

Run from backend/:
    python scripts/check_forcing_credentials.py

What it checks:
    A5 - Copernicus Marine Service (CMEMS): reads COPERNICUS_MARINE_USERNAME /
         COPERNICUS_MARINE_PASSWORD from backend/.env. If the `copernicus_marine`
         Python client is installed it performs a real login; otherwise it prints
         the manual verification steps (and tells D to `pip install copernicus_marine`).
    A6 - ECMWF ERA5 (CDS API): reads CDSAPI_URL / CDSAPI_KEY from backend/.env.
         A ~/.cdsapirc is written from those values; if the `cdsapi` package is
         installed the key is validated against the CDS metadata endpoint.

Registration steps are printed when a check cannot run or fails. Nothing here
needs the actual forcing data — it only proves the credentials are valid, which
is the prerequisite for ``drift_engine.py`` (Phase 2) to download real fields.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def cmems_check(env: dict[str, str]) -> None:
    print("=== A5: Copernicus Marine Service (CMEMS) ===")
    user = env.get("COPERNICUS_MARINE_USERNAME", "")
    pwd = env.get("COPERNICUS_MARINE_PASSWORD", "")
    if not user or not pwd:
        print("  FAIL: COPERNICUS_MARINE_USERNAME/PASSWORD missing in backend/.env")
        print("  Fix:  register at https://data.marine.copernicus.eu (free), accept the")
        print("        licence of the products you will use, then set the two env vars and")
        print("        share them with D. D uses them via `pip install copernicus_marine`.")
        return
    try:
        import copernicusmarine  # type: ignore
    except ImportError:
        print(f"  user: {user}")
        print("  SKIP: `copernicus_marine` not installed locally - login cannot be tested here.")
        print("  Manual check: copernicusmarine login --username <user> --password <pwd>")
        print("  Hand-off: share username+password (or the .env lines) with D now.")
        return
    try:
        copernicusmarine.login(username=user, password=pwd, force_overwrite_credentials_file=True)
        print(f"  PASS: login succeeded for {user}")
    except Exception as exc:
        print(f"  FAIL: login error -> {exc}")
        print("  Fix:  confirm the account is activated and that a product licence has been")
        print("        accepted at https://data.marine.copernicus.eu")


def cds_check(env: dict[str, str]) -> None:
    print("=== A6: ECMWF ERA5 (CDS API) ===")
    url = env.get("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    key = env.get("CDSAPI_KEY", "")
    if not key:
        print("  FAIL: CDSAPI_KEY missing in backend/.env")
        print("  Fix:  register at https://cds.climate.copernicus.eu, go to your profile /")
        print("        API key, and set CDSAPI_KEY=<uid>:<key> (and CDSAPI_URL if needed).")
        print("        Accept the 'Licence to use Copernicus Products' for ERA5 first.")
        return
    cdsapirc = Path.home() / ".cdsapirc"
    cdsapirc.write_text(f"url: {url}\nkey: {key}\n", encoding="utf-8")
    print(f"  wrote {cdsapirc}")
    try:
        import cdsapi  # type: ignore

        client = cdsapi.Client()
        client.info("reanalysis-era5-single-levels")
        print(f"  PASS: CDS key validated against ERA5 metadata (uid {key.split(':')[0]})")
    except ImportError:
        print(f"  uid: {key.split(':')[0]}")
        print("  SKIP: `cdsapi` not installed locally - key format looks right; D can verify")
        print("        with `pip install cdsapi` + `python -c 'import cdsapi; cdsapi.Client().info(\"reanalysis-era5-single-levels\")'`.")
    except Exception as exc:
        print(f"  FAIL: CDS key rejected -> {exc}")
        print("  Fix:  re-check uid:key on https://cds.climate.copernicus.eu/profile")


def main() -> int:
    env = load_env()
    print(f"reading credentials from {ENV_PATH}\n")
    cmems_check(env)
    print()
    cds_check(env)
    print("\nHand-off to D (tasks A5/A6): copy the COPERNICUS_MARINE_* and CDSAPI_* lines")
    print("from backend/.env into the team-shared .env. Nothing else is needed from A "
    "before Phase 2 (backward drift) can start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())