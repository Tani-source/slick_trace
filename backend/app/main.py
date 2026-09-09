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

# Optional static file serving for unified full-stack deployments (e.g. Hugging Face Spaces / Docker / Render)
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_dist_candidates = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "frontend_dist",
    Path("/app/frontend/dist"),
]

for _cand in _dist_candidates:
    if _cand.is_dir() and (_cand / "index.html").exists():
        if (_cand / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=str(_cand / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str, _dist=_cand):
            file_path = _dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(_dist / "index.html")
        break
