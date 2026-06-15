from fastapi import FastAPI

from app.core.checker import check
from app.models.schemas import POICheckRequest, POICheckResponse
from app.services import poi_judge

app = FastAPI(title="POI Bullshit Detector", version="2.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "llm_enabled": poi_judge.is_enabled()}


@app.post("/check", response_model=POICheckResponse)
async def check_endpoint(req: POICheckRequest) -> POICheckResponse:
    # Uses the local Ollama model when enabled; otherwise (or if Ollama is
    # unreachable) falls back to the key-free heuristic, so /check always works.
    return await check(req)
