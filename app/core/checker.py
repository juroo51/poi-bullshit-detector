import httpx
from ollama import ResponseError
from pydantic import ValidationError

from app.models.schemas import POICheckRequest, POICheckResponse
from app.services import heuristic_judge, poi_judge

# Raised when Ollama isn't running, the model is missing, or output is malformed.
_LLM_FAILURES = (ConnectionError, httpx.HTTPError, ResponseError, ValidationError)


async def check(req: POICheckRequest) -> POICheckResponse:
    if poi_judge.is_enabled():
        try:
            judgment = await poi_judge.judge(req.name, req.lat, req.lon)
            return POICheckResponse(
                suitable=judgment.suitable,
                reason=judgment.reason,
                model=poi_judge.settings.llm_model,
            )
        except _LLM_FAILURES:
            pass  # Ollama unavailable — degrade to the key-free heuristic.

    judgment = heuristic_judge.judge(req.name, req.lat, req.lon)
    return POICheckResponse(suitable=judgment.suitable, reason=judgment.reason, model="heuristic")
