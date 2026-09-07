from pydantic import BaseModel


class SlickPolygon(BaseModel):
    polygon: list[list[float]]  # [[lat, lon], ...]
    detection_time: str  # ISO8601
    bbox: list[float]  # [minLat, minLon, maxLat, maxLon]
    area_km2: float
    elongation_ratio: float
    age_estimate_hours: float
    weathering_validity: bool  # False if age > 72h (low-confidence downstream)
    age_confidence: str = "high"
    fallback_used: bool = False
