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
            judgment = await poi_judge.judge(req.name, req.lat, req.lon, req.candidates)
            return _to_response(judgment, req, model=poi_judge.settings.llm_model)
        except _LLM_FAILURES:
            pass  # Ollama unavailable — degrade to the key-free heuristic.

    judgment = heuristic_judge.judge(req.name, req.lat, req.lon, req.candidates)
    return _to_response(judgment, req, model="heuristic")


def _to_response(judgment, req: POICheckRequest, model: str) -> POICheckResponse:
    suitable, reason = judgment.suitable, judgment.reason
    duplicate, duplicate_of = judgment.duplicate, judgment.duplicate_of

    # Deterministic backstop: small local models don't recognize offensive words
    # outside English, so a blocklisted term forces suitable=false regardless of
    # what the LLM said (e.g. Slovak "kokot" that llama3.2 passes as clean).
    if suitable and heuristic_judge.find_profanity(req.name) is not None:
        suitable = False
        reason = "Name contains offensive or explicit language."

    # Deterministic backstop: small local models miss even exact matches, so an
    # exact/normalized duplicate is forced true regardless of what the LLM said.
    exact = heuristic_judge.find_duplicate(req.name, req.candidates)
    if exact is not None and not duplicate:
        duplicate, duplicate_of = True, exact

    return POICheckResponse(
        suitable=suitable,
        reason=reason,
        model=model,
        duplicate=duplicate,
        duplicate_of=duplicate_of,
    )
