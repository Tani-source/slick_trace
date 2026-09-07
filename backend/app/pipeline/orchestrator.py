from __future__ import annotations

from . import stage0_perception, stage1_backward_drift
from ..services import run_store
from ..schemas.pipeline_status import PipelineStatus, PipelineStage

def empty_pipeline_status(run_id: str) -> PipelineStatus:
    return PipelineStatus(
        run_id=run_id,
        stages=[
            PipelineStage(name="perception", status="pending", progress_pct=0, detail=""),
            PipelineStage(name="ais_ingestion", status="pending", progress_pct=0, detail=""),
            PipelineStage(name="candidate_filtering", status="pending", progress_pct=0, detail=""),
            PipelineStage(name="anomaly_scoring", status="pending", progress_pct=0, detail=""),
            PipelineStage(name="drift_simulation", status="pending", progress_pct=0, detail=""),
            PipelineStage(name="verification_matching", status="pending", progress_pct=0, detail=""),
        ]
    )

def _persist(run_id: str, status: PipelineStatus) -> None:
    run_store.save_pipeline_status(run_id, status.model_dump(mode="json"))

class Stage1Error(Exception):
    pass

def run_pipeline(run_id: str) -> dict:
    """Execute all pipeline stages in sequence, halting on upstream failure."""
    # Load pipeline status
    status = empty_pipeline_status(run_id)
    
    # Stage 0: Perception (already implemented)
    if status.stages[0].status == "pending":
        # Check if SAR dataset is available
        inputs = run_store.all_datasets(run_id)
        if inputs.get("sar", {}).get("status") == "uploaded":
            # Run Stage 0
            result = stage0_perception.run_stage0(run_id)
            if result["status"] == "success":
                status.stages[0].status = "done"
                status.stages[0].detail = f"Stage 0 complete: {result['data']['area_km2']} km²"
                run_store.save_stage_output(run_id, "slick_polygon", result["data"])
            else:
                status.stages[0].status = "failed"
                status.stages[0].detail = result["reason"]
                _persist(run_id, status)
                return {"status": "failed", "stage": "perception", "reason": result["reason"]}
        else:
            status.stages[0].detail = "Upload data first"
    
    # Stage 1: Backward Drift (Phase 1)
    if status.stages[1].status == "pending":
        try:
            stage1 = stage1_backward_drift.Stage1(run_id)
            stage1.run_backward_drift()
            # Update status after Stage 1 completes
            status.stages[1].status = "done"
            status.stages[1].detail = "Backward drift completed successfully"
            _persist(run_id, status)
        except Stage1Error as e:
            status.stages[1].status = "failed"
            status.stages[1].detail = str(e)
            _persist(run_id, status)
            return {"status": "failed", "stage": "backward_drift", "reason": str(e)}
    
    # Stages 2-6: Not implemented in Phase 1
    for i in range(2, len(status.stages)):
        stage = status.stages[i]
        if stage.status == "pending":
            stage.detail = "Available in a later build phase"
    
    _persist(run_id, status)
    return {"status": "success", "run_id": run_id, "stages_completed": 2}