from pydantic import BaseModel, Field
from typing import List

class StageStatus(BaseModel):
    name: str
    status: str = Field(description="pending|running|done|failed")
    progress_pct: int
    detail: str

class PipelineStatus(BaseModel):
    stages: List[StageStatus]
