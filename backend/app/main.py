from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import datasets, pipeline, status, results, prototype

app = FastAPI(title="SlickTrace API", description="Oil Spill Source Attribution System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For hackathon demo purposes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(pipeline.router, prefix="/api", tags=["pipeline"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(results.router, prefix="/api", tags=["results"])
app.include_router(prototype.router, prefix="/api/prototype", tags=["prototype"])

@app.get("/")
def read_root():
    return {"message": "SlickTrace API is running"}
