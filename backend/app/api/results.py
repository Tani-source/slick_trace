from fastapi import APIRouter
from app.schemas.ranked_suspects import RankedSuspects

router = APIRouter()

@router.get("/results/{run_id}")
async def get_results(run_id: str) -> RankedSuspects:
    # Stub: returns empty ranking
    return RankedSuspects(ranking=[])

@router.get("/results/{run_id}/export")
async def export_results(run_id: str):
    # Stub: returns a dummy file response
    return {"message": "Export bundle would be returned here"}
