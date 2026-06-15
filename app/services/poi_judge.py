from ollama import AsyncClient
from pydantic import BaseModel

from app.config import settings

_SYSTEM = """You are a geographic point-of-interest (POI) validator.
You are given a POI name (a place label or category, e.g. "groceries",
"pharmacy", "Eiffel Tower") and a geographic coordinate (latitude, longitude).
Decide whether that name is a suitable, plausible label for a real point of
interest at or near that location.

Use your knowledge of world geography — what country, city, and kind of area
the coordinates fall in (urban vs rural, on land vs water, region) — to judge
plausibility. Consider:
- Is the name a real, sensible POI type or name, not gibberish or placeholder text?
- Could such a place plausibly exist at this location given the surrounding area?
- A named landmark (e.g. "Eiffel Tower") should match the actual place it names.

You do not have live map data, so judge plausibility, not exact presence.
Return suitable=true if the name is a reasonable POI label for that place,
false otherwise. Always give one concrete, short sentence as the reason.
Respond with JSON only."""


class POIJudgment(BaseModel):
    suitable: bool
    reason: str


_client: AsyncClient | None = None


def is_enabled() -> bool:
    return settings.enable_llm


def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(host=settings.ollama_host)
    return _client


async def judge(name: str, lat: float, lon: float) -> POIJudgment:
    resp = await _get_client().chat(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"POI name: {name}\n"
                    f"Coordinates: latitude {lat}, longitude {lon}\n\n"
                    "Is this name suitable for a point of interest at this precise GPS coordinates location?"
                ),
            },
        ],
        format=POIJudgment.model_json_schema(),   # constrain output to the schema
        options={"temperature": 0},
    )
    return POIJudgment.model_validate_json(resp.message.content)
