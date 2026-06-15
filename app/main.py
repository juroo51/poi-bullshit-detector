from fastapi import FastAPI
from app.models.schemas import ValidationRequest, Verdict
from app.core.orchestrator import validate

app = FastAPI(title="Navigation API Validator", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/validate", response_model=Verdict)
async def validate_endpoint(req: ValidationRequest) -> Verdict:
    return await validate(req)
