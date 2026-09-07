from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from app.schemas.slick_polygon import SlickPolygon
from app.schemas.shortlist import Shortlist, Candidate, PositionAtEvent, AnomalyBreakdown, CandidateReleasePoint
from app.services.ais_loader import load_and_filter

router = APIRouter()

# Path to the AIS data file (synthetic fallback, per Person B hand-off)
_AIS_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "ais_2023_11_15_synthetic.csv"


@router.post("/pipeline/run")
async def run_pipeline() -> Dict[str, str]:
    # Stub: returns run_id immediately; background task wiring comes in Phase 1
    return {"run_id": "demo-run-123"}


@router.get("/pipeline/slick")
async def get_slick(run_id: str) -> SlickPolygon:
    # Stub fixture — will be replaced by Stage 1 SAR output in Phase 1
    return SlickPolygon(
        polygon=[[29.3, -88.7], [29.35, -88.65], [29.25, -88.6], [29.3, -88.7]],
        detection_time="2023-11-16T12:00:00Z",
        bbox=(29.2, -88.8, 29.4, -88.5),
        area_km2=45.2,
        elongation_ratio=3.1,
        age_estimate_hours=12.5,
    )


@router.get("/pipeline/shortlist")
async def get_shortlist(run_id: str) -> Shortlist:
    """
    Stage 2/3: Load AIS data and return candidate vessel shortlist.
    Uses the synthetic AIS fallback (Person B decision, PRD §9).
    """
    if not _AIS_CSV.exists():
        raise HTTPException(
            status_code=503,
            detail=f"AIS data not found at {_AIS_CSV}. Drop ais_2023_11_15_synthetic.csv into backend/data/uploads/.",
        )

    result = load_and_filter(_AIS_CSV)

    if result["status"] == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"AIS filter failed — stage: {result.get('stage')}, reason: {result.get('reason')}",
        )

    candidates: List[Candidate] = []
    for c in result["data"]:
        pos = c["position_at_event"]
        ab = c["anomaly_breakdown"]
        release_pts = [
            CandidateReleasePoint(lat=p["lat"], lon=p["lon"], time=p["time"])
            for p in c.get("candidate_release_points", [])
        ]
        candidates.append(
            Candidate(
                mmsi=c["mmsi"],
                vessel_name=c["vessel_name"],
                vessel_type=c["vessel_type"],
                operator=c.get("operator", ""),
                flag=c.get("flag", ""),
                destination=c.get("destination", ""),
                position_at_event=PositionAtEvent(lat=pos["lat"], lon=pos["lon"], time=pos["time"]),
                anomaly_score=c.get("anomaly_score", 0.0),
                anomaly_breakdown=AnomalyBreakdown(
                    blackout=ab.get("blackout", 0.0),
                    speed=ab.get("speed", 0.0),
                    route=ab.get("route", 0.0),
                    draft=ab.get("draft", 0.0),
                ),
                candidate_release_points=release_pts,
            )
        )

    return Shortlist(candidates=candidates)


@router.post("/pipeline/simulate")
async def simulate(run_id: str) -> Dict[str, str]:
    # Stub: drift simulation wiring comes in Phase 3
    return {"status": "started", "run_id": run_id}
