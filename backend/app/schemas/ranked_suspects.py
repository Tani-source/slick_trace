from __future__ import annotations

from pydantic import BaseModel


class RankedSuspect(BaseModel):
    mmsi: str
    vessel_name: str
    match_score: float
    iou: float
    centroid_distance_km: float
    orientation_match: float
    rank: int


class RankedSuspects(BaseModel):
    run_id: str
    ranking: list[RankedSuspect]
