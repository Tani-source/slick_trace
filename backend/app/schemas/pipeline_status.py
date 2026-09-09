from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StageName = Literal[
    "perception",
    "backward_drift",
    "ais_ingestion",
    "candidate_filtering",
    "anomaly_scoring",
    "drift_simulation",
    "verification_matching",
]
StageStatusValue = Literal["pending", "running", "done", "failed"]

STAGE_NAMES: list[StageName] = [
    "perception",
    "backward_drift",
    "ais_ingestion",
    "candidate_filtering",
    "anomaly_scoring",
    "drift_simulation",
    "verification_matching",
]


class StageStatus(BaseModel):
    name: StageName
    status: StageStatusValue = "pending"
    progress_pct: int = Field(0, ge=0, le=100)
    detail: str = ""


class PipelineStatus(BaseModel):
    run_id: str
    stages: list[StageStatus]


def empty_pipeline_status(run_id: str) -> PipelineStatus:
    stages = [StageStatus(name=name) for name in STAGE_NAMES]
    return PipelineStatus(run_id=run_id, stages=stages)
