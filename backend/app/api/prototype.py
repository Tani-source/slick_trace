from fastapi import APIRouter

router = APIRouter()

@router.get("/prototype/dark-ship")
async def dark_ship():
    # Stub
    return {"status": "success", "detections": []}

@router.get("/prototype/oil-type")
async def oil_type():
    # Stub
    return {"status": "success", "classification": "Crude"}
