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

    # run_store.update_stage writes stages as a dict keyed by stage name.
    # Normalize to list[StageStatus] shape before returning to the frontend.
    raw_stages = stored.get("stages", {})
    if isinstance(raw_stages, dict):
        from ..schemas.pipeline_status import STAGE_NAMES
        stages_list = []
        for name in STAGE_NAMES:
            entry = raw_stages.get(name, {})
            stages_list.append({
                "name": name,
                "status": entry.get("status", "pending"),
                # on-disk key is 'progress'; schema key is 'progress_pct'
                "progress_pct": entry.get("progress_pct", entry.get("progress", 0)),
                # on-disk key is 'message'; schema key is 'detail'
                "detail": entry.get("detail", entry.get("message", "")),
            })
        return {"run_id": stored.get("run_id", run_id), "stages": stages_list}

    # Already list-shaped (e.g. written by a future migration) — return as-is
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
