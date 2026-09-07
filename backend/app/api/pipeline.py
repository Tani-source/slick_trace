from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from pydantic import BaseModel

from ..pipeline import orchestrator
from ..services import run_store

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class RunRequest(BaseModel):
    run_id: str


@router.post("/run")
async def run_pipeline(request: RunRequest, background: BackgroundTasks) -> dict:
    if not run_store.run_exists(request.run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {request.run_id}")
    background.add_task(orchestrator.run_pipeline, request.run_id)
    return {"run_id": request.run_id, "status": "started"}


@router.post("/simulate")
async def simulate_pipeline(request: RunRequest, background: BackgroundTasks) -> dict:
    if not run_store.run_exists(request.run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {request.run_id}")
    background.add_task(orchestrator.simulate_pipeline, request.run_id)
    return {"run_id": request.run_id, "status": "started"}
