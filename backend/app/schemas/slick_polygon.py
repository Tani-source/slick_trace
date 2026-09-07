from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AgeConfidence = Literal["high", "low"]


class SlickPolygon(BaseModel):
    polygon: list[list[float]]
    detection_time: datetime
    bbox: list[float]
    area_km2: float
    elongation_ratio: float
    age_estimate_hours: float | None
    weathering_validity: bool
    age_confidence: AgeConfidence
