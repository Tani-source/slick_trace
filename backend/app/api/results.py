from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..services import run_store

router = APIRouter(prefix="/results", tags=["results"])


def _require_run(run_id: str) -> None:
    if not run_store.run_exists(run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")


@router.get("/{run_id}")
async def results(run_id: str) -> dict:
    _require_run(run_id)
    payload = run_store.load_stage_output(run_id, "ranked_suspects")
    if payload is None:
        return {"run_id": run_id, "ranking": []}
    return payload


@router.get("/{run_id}/export")
async def export_results(run_id: str) -> Response:
    _require_run(run_id)
    names = ("slick_polygon", "shortlist", "ranked_suspects", "pipeline_status")
    payloads = {name: run_store.load_stage_output(run_id, name) for name in names}
    present = {name: payload for name, payload in payloads.items() if payload is not None}
    if not present:
        raise HTTPException(status_code=404, detail="no results to export for this run")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in present.items():
            archive.writestr(f"{name}.json", __import__("json").dumps(payload, indent=2))
        slick = payloads.get("slick_polygon")
        if slick and slick.get("polygon"):
            archive.writestr(
                "slick_polygon.geojson",
                __import__("json").dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[lon, lat] for lat, lon in slick["polygon"]]],
                                },
                                "properties": {
                                    "area_km2": slick.get("area_km2"),
                                    "age_estimate_hours": slick.get("age_estimate_hours"),
                                },
                            }
                        ],
                    }
                ),
            )
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="slicktrace-results-{run_id}.zip"'},
    )
