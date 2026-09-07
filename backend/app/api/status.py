from fastapi import APIRouter
from app.schemas.pipeline_status import PipelineStatus, StageStatus

router = APIRouter()

@router.get("/pipeline/status")
async def get_status(run_id: str) -> PipelineStatus:
    # Stub: returns static pipeline status
    return PipelineStatus(
        stages=[
            StageStatus(name="perception", status="pending", progress_pct=0, detail="Waiting to start"),
            StageStatus(name="ais_ingestion", status="pending", progress_pct=0, detail="Waiting to start"),
            StageStatus(name="candidate_filtering", status="pending", progress_pct=0, detail="Waiting to start"),
            StageStatus(name="anomaly_scoring", status="pending", progress_pct=0, detail="Waiting to start"),
            StageStatus(name="drift_simulation", status="pending", progress_pct=0, detail="Waiting to start"),
            StageStatus(name="verification_matching", status="pending", progress_pct=0, detail="Waiting to start"),
        ]
    )
