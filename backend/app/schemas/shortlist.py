from pydantic import BaseModel, Field
from typing import List

class PositionAtEvent(BaseModel):
    lat: float
    lon: float
    time: str = Field(description="ISO8601 timestamp")

class AnomalyBreakdown(BaseModel):
    blackout: float
    speed: float
    route: float
    draft: float

class CandidateReleasePoint(BaseModel):
    lat: float
    lon: float
    time: str = Field(description="ISO8601 timestamp")

class Candidate(BaseModel):
    mmsi: str
    vessel_name: str
    vessel_type: str = Field(description="tanker|cargo|bunkering")
    operator: str
    flag: str
    destination: str
    position_at_event: PositionAtEvent
    anomaly_score: float
    anomaly_breakdown: AnomalyBreakdown
    candidate_release_points: List[CandidateReleasePoint]

class Shortlist(BaseModel):
    candidates: List[Candidate]
