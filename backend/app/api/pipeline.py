from __future__ import annotations

import threading
from fastapi import APIRouter, BackgroundTasks, HTTPException

from pydantic import BaseModel

from ..pipeline import orchestrator
from ..services import run_store

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Track in-flight runs to reject re-submissions before completion.
_active_runs: set[str] = set()
_active_lock = threading.Lock()


class RunRequest(BaseModel):
    run_id: str


def _mark_active(run_id: str) -> bool:
    """Returns True if successfully marked active; False if already running."""
    with _active_lock:
        if run_id in _active_runs:
            return False
        _active_runs.add(run_id)
        return True


def _mark_done(run_id: str) -> None:
    with _active_lock:
        _active_runs.discard(run_id)


@router.post("/run")
async def run_pipeline(request: RunRequest, background: BackgroundTasks) -> dict:
    if not run_store.run_exists(request.run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {request.run_id}")
    if not _mark_active(request.run_id):
        raise HTTPException(status_code=409, detail="pipeline already running for this run_id")

    async def _run_and_release() -> None:
        try:
            orchestrator.run_pipeline(request.run_id)
        finally:
            _mark_done(request.run_id)

    background.add_task(_run_and_release)
    return {"run_id": request.run_id, "status": "started"}


@router.post("/simulate")
async def simulate_pipeline(request: RunRequest, background: BackgroundTasks) -> dict:
    if not run_store.run_exists(request.run_id):
        raise HTTPException(status_code=404, detail=f"unknown run_id {request.run_id}")
    if not _mark_active(request.run_id):
        raise HTTPException(status_code=409, detail="simulation already running for this run_id")

    async def _simulate_and_release() -> None:
        try:
            orchestrator.simulate_pipeline(request.run_id)
        finally:
            _mark_done(request.run_id)

    background.add_task(_simulate_and_release)
    return {"run_id": request.run_id, "status": "started"}
