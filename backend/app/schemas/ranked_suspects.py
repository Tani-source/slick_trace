from pydantic import BaseModel
from typing import List

class RankedSuspect(BaseModel):
    mmsi: str
    vessel_name: str
    match_score: float
    iou: float
    centroid_distance_km: float
    orientation_match: float
    rank: int

class RankedSuspects(BaseModel):
    ranking: List[RankedSuspect]
