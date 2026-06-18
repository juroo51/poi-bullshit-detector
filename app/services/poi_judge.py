from ollama import AsyncClient
from pydantic import BaseModel

from app.config import settings

_SYSTEM = """You are a validator of point-of-interest (POI) name labels.
You are given a POI name (a public place label or category, e.g. "groceries",
"pharmacy", "Eiffel Tower", "Lidl") and optionally a list of existing nearby POI
names (candidates). You must produce two judgments.

1. Suitability — judge the NAME TEXT ALONE as a public label. Do NOT consider
location, geography, or whether such a place could plausibly exist anywhere —
those are irrelevant. Only decide whether the label itself is acceptable.
Set suitable=false ONLY when the name is:
- profane, offensive, or just expressive/vulgar words rather than a real label,
- total nonsense or gibberish (random characters, keyboard mashing, placeholder
  text like "asdf" or "lorem ipsum"),
- a clearly misspelled label (e.g. "pharmaci", "groceriez", "restraunt").
Otherwise — any correctly spelled, real, inoffensive place label or category —
set suitable=true. Do not reject a name for being unusual or unlikely; you are
only checking basic validity of the public label name, not its context.

2. Duplicate — does the name refer to the EXACT SAME point of interest as one of
the candidates? Be strict. A duplicate means the input name and a candidate name
the very same individual place, differing only in surface form. Treat as a
duplicate ONLY when they differ by:
- letter case, punctuation, spacing, or accents ("St. Mary's" vs "st marys"),
- a known abbreviation or alternate spelling/translation of the same proper name
  ("McDonald's" vs "McDonalds", "Eiffel Tower" vs "Tour Eiffel").

Do NOT mark a duplicate just because two names share a category or type. Different
places of the same kind are NOT duplicates: "groceries" vs "Supermarket",
"ATM" vs "Cash Machine", "Joe's Pizza" vs "Pizza Hut", "Pharmacy" vs "Apotheke"
are all DISTINCT — set duplicate=false for these. When unsure, prefer
duplicate=false.

If and only if the input names the same exact place as a candidate, set
duplicate=true and duplicate_of to that candidate's exact string; otherwise
duplicate=false and duplicate_of=null. If no candidates are given, duplicate is
always false.

Always give one concrete, short sentence as the reason. Respond with JSON only."""


class POIJudgment(BaseModel):
    suitable: bool
    reason: str
    duplicate: bool = False
    duplicate_of: str | None = None


_client: AsyncClient | None = None


def is_enabled() -> bool:
    return settings.enable_llm


def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(host=settings.ollama_host)
    return _client


async def judge(
    name: str, lat: float, lon: float, candidates: list[str] | None = None
) -> POIJudgment:
    candidates = candidates or []
    candidate_block = (
        "Existing nearby POI names (candidates):\n"
        + "\n".join(f"- {c}" for c in candidates)
        if candidates
        else "Existing nearby POI names (candidates): none"
    )
    resp = await _get_client().chat(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"POI name: {name}\n"
                    f"{candidate_block}\n\n"
                    "Is this a valid public POI label (correctly spelled, not offensive, "
                    "not gibberish), and does it name the EXACT SAME place as any candidate "
                    "(not merely the same category)?"
                ),
            },
        ],
        format=POIJudgment.model_json_schema(),   # constrain output to the schema
        options={"temperature": 0},
    )
    return POIJudgment.model_validate_json(resp.message.content)
