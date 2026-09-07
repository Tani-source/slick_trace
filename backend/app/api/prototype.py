from __future__ import annotations

import json

from fastapi import APIRouter

from ..config import PROTOTYPE_CACHE_DIR

router = APIRouter(prefix="/prototype", tags=["prototype"])

_NOTE = (
    "Prototype — architecture below. Pre-computed example only; this endpoint never "
    "touches the live pipeline run_id (architecture.md §2.2)."
)


def _cached(name: str) -> dict:
    path = PROTOTYPE_CACHE_DIR / f"{name}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["prototype_label"] = _NOTE
        return payload
    return {
        "status": "prototype",
        "available": False,
        "prototype_label": _NOTE,
        "detail": "Pre-computed example not bundled in this build; no live inference is run.",
    }


@router.get("/dark-ship")
async def dark_ship() -> dict:
    return _cached("dark_ship")


@router.get("/oil-type")
async def oil_type() -> dict:
    return _cached("oil_type")
