from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.pipeline_status import empty_pipeline_status
from ..services import run_store

router = APIRouter(prefix="/pipeline", tags=["status"])


def _require_run(run_id: str) -> None:
    if not run_store.run_exists(run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")


@router.get("/status")
async def pipeline_status(run_id: str) -> dict:
    _require_run(run_id)
    stored = run_store.load_pipeline_status(run_id)
    if stored is None:
        return empty_pipeline_status(run_id).model_dump(mode="json")
    return stored


@router.get("/slick")
async def slick_polygon(run_id: str) -> dict:
    _require_run(run_id)
    payload = run_store.load_stage_output(run_id, "slick_polygon")
    if payload is None:
        raise HTTPException(status_code=404, detail="perception stage not complete for this run")
    return payload


@router.get("/shortlist")
async def shortlist(run_id: str) -> dict:
    _require_run(run_id)
    payload = run_store.load_stage_output(run_id, "shortlist")
    if payload is None:
        return {"run_id": run_id, "candidates": []}
    return payload
