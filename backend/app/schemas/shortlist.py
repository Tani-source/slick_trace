from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

VesselType = Literal["tanker", "cargo", "bunkering"]


class PositionAtEvent(BaseModel):
    lat: float
    lon: float
    time: datetime


class AnomalyBreakdown(BaseModel):
    blackout: float
    speed: float
    route: float
    draft: float


class CandidateReleasePoint(BaseModel):
    lat: float
    lon: float
    time: datetime


class ShortlistCandidate(BaseModel):
    mmsi: str
    vessel_name: str
    vessel_type: VesselType
    operator: str
    flag: str
    destination: str
    position_at_event: PositionAtEvent
    anomaly_score: float
    anomaly_breakdown: AnomalyBreakdown
    candidate_release_points: list[CandidateReleasePoint]


class Shortlist(BaseModel):
    run_id: str
    candidates: list[ShortlistCandidate]
