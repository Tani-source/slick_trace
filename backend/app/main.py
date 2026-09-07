from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import datasets, pipeline, prototype, results, status
from .config import ensure_dirs

app = FastAPI(
    title="SlickTrace API",
    version="0.1.0",
    description="Oil Spill Source Attribution System - pipeline backend (SIH26143 NTRO)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "SlickTrace API"}


app.include_router(datasets.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(prototype.router, prefix="/api")

ensure_dirs()
