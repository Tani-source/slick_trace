"""Download 1-2 Sentinel-1 GRD scenes of the demo region from Copernicus.

NOTE: Copernicus Open Access Hub was retired in 2025. Its successor is the
Copernicus Data Space Ecosystem, which is what this script talks to. A free
account is required: register at https://dataspace.copernicus.eu/ (use a normal
email + password; the portal calls this "EO Free").

Runbook (Person A, task A4):
    1.  Register at https://dataspace.copernicus.eu/ and activate the account.
    2.  Put those credentials into backend/.env:
            COPERNICUS_USERNAME=your.email@example.com
            COPERNICUS_PASSWORD=your-password
    3.  From backend/:
            python scripts/download_sentinel1.py \
                --bbox "-97.0,27.0,-94.0,30.0" \
                --start 2024-01-01 --end 2024-03-01 --top 2
    4.  Products (GRD IW, VV+VH) land in backend/data/sentinel1/ as .zip.

Search is served by the Data Space OData API; downloads stream the full product
bundle with Basic auth and resume support. The S1A/S1B_IW_GRDH_1SDV name prefix
selects IW mode, ground-range-detected, dual polarization (VV+VH) scenes, which
is what Stage 0 and the Zenodo training imagery assume.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path

try:
    import requests
    from requests import Response
except ImportError:
    sys.exit("requests is required:  pip install requests")

CATALOGUE = "https://catalogue.dataspace.copernicus.eu/odata/v1"


def basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def search_products(bbox: str, start: str, end: str, top: int, headers: dict[str, str]) -> list[dict]:
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox.split(","))
    polygon = f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"
    filters = (
        "(startswith(Name,'S1A_IW_GRDH_1SDV') or startswith(Name,'S1B_IW_GRDH_1SDV')) "
        f"and OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') "
        f"and ContentDate/Start gt {start}T00:00:00.000Z "
        f"and ContentDate/Start lt {end}T00:00:00.000Z"
    )
    params = {
        "$filter": filters,
        "$orderby": "ContentDate/Start desc",
        "$top": top,
        "$select": "Id,Name,ContentDate,Footprint",
    }
    resp: Response = requests.get(f"{CATALOGUE}/Products", params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["value"]


def download_product(uuid: str, dest: Path, headers: dict[str, str]) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{CATALOGUE}/Products('{uuid}')/$value"
    headers = dict(headers)
    mode = "wb"
    if dest.exists() and dest.stat().st_size > 0:
        headers["Range"] = f"bytes={dest.stat().st_size}-"
        mode = "ab"
    with requests.get(url, headers=headers, stream=True, timeout=120) as resp:
        if resp.status_code == 416:
            print(f"    already complete: {dest.name}")
            return dest
        if resp.status_code not in (200, 206):
            raise RuntimeError(f"download failed ({resp.status_code}): {resp.text[:300]}")
        if resp.status_code == 200 and mode == "ab":
            mode = "wb"
        done = dest.stat().st_size if mode == "ab" else 0
        with open(dest, mode) as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                print(f"\r    {done / 1e9:6.2f} GB", end="", flush=True)
        print()
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", help='"minLon,minLat,maxLon,maxLat" of the demo region')
    parser.add_argument("--start", default="2024-01-01", help="acquisition start date (ISO)")
    parser.add_argument("--end", default="2024-03-01", help="acquisition end date (ISO)")
    parser.add_argument("--top", type=int, default=2, help="number of scenes to download")
    parser.add_argument("--uuid", help="skip search and download a known product UUID directly")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "sentinel1")
    args = parser.parse_args()

    username = os.environ.get("COPERNICUS_USERNAME") or ""
    password = os.environ.get("COPERNICUS_PASSWORD") or ""
    if not username or not password:
        sys.exit("set COPERNICUS_USERNAME and COPERNICUS_PASSWORD in backend/.env "
                 "(register at https://dataspace.copernicus.eu/ first)")
    headers = basic_auth_header(username, password)

    if args.uuid:
        products = [{"Id": args.uuid, "Name": args.uuid}]
    else:
        if not args.bbox:
            sys.exit("--bbox is required unless --uuid is given")
        products = search_products(args.bbox, args.start, args.end, args.top, headers)
        if not products:
            sys.exit("no matching Sentinel-1 GRD scenes found; widen --bbox/--start/--end")
        for p in products:
            print(f"  {p['Name']}  {p['ContentDate']['Start']}")

    for p in products:
        safe = "".join(c for c in p["Name"] if c.isalnum() or c in "-_")
        dest = args.out / f"{safe}.zip"
        print(f"downloading {p['Name']} -> {dest}")
        download_product(p["Id"], dest, headers)
        time.sleep(1)

    print("\nDone. Hand-off: point Stage 0 at one of these scenes (or a sub-crop) for the"
          " demo slick, and keep the other as a look-alike test case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())