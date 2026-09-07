from pydantic import BaseModel, Field
from typing import List, Tuple

class SlickPolygon(BaseModel):
    polygon: List[Tuple[float, float]] = Field(description="List of [lat, lon] coordinates")
    detection_time: str = Field(description="ISO8601 timestamp")
    bbox: Tuple[float, float, float, float] = Field(description="[minLat, minLon, maxLat, maxLon]")
    area_km2: float
    elongation_ratio: float
    age_estimate_hours: float
