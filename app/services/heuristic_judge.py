"""Key-free fallback judge.

No AI and no map data, so it cannot assess geographic plausibility. It does a
cheap sanity check on the *name*: rejects placeholder text and obvious
gibberish, accepts anything that looks like a real POI label. Duplicate
detection is likewise name-only — normalized string equality against the
candidates, not the semantic matching the LLM judge does.
"""

import re

from app.services.poi_judge import POIJudgment

_PLACEHOLDERS = {
    "lorem", "ipsum", "example", "sample", "placeholder", "todo", "tbd",
    "foo", "bar", "baz", "test", "testing", "dummy", "asdf", "qwerty",
    "string", "none", "null", "n/a", "na", "xxx", "untitled", "unknown",
}
_VOWELS = set("aeiouy")


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", name.lower())).strip()


def find_duplicate(name: str, candidates: list[str]) -> str | None:
    """Return the candidate whose normalized form equals `name`'s, if any."""
    target = _normalize(name)
    if not target:
        return None
    return next((c for c in candidates if _normalize(c) == target), None)


def judge(name: str, lat: float, lon: float, candidates: list[str] | None = None) -> POIJudgment:
    candidates = candidates or []
    cleaned = name.strip()
    lowered = cleaned.lower()
    words = set(re.findall(r"[a-z]+", lowered))

    duplicate_of = find_duplicate(name, candidates)
    dup_fields = {"duplicate": duplicate_of is not None, "duplicate_of": duplicate_of}

    if words & _PLACEHOLDERS or lowered in _PLACEHOLDERS:
        return POIJudgment(suitable=False, reason="Name looks like placeholder text, not a real POI.", **dup_fields)

    if not re.search(r"[a-z]", lowered):
        return POIJudgment(suitable=False, reason="Name has no letters; not a usable POI label.", **dup_fields)

    if re.fullmatch(r"(.)\1+", lowered):
        return POIJudgment(suitable=False, reason="Name is a single repeated character; not a real POI.", **dup_fields)

    # A long all-consonant word (and not a short acronym) reads as gibberish.
    longest = max(words, key=len, default="")
    is_acronym = cleaned.isupper() and len(cleaned) <= 5
    if len(longest) >= 5 and not (_VOWELS & set(longest)) and not is_acronym:
        return POIJudgment(suitable=False, reason=f"'{cleaned}' looks like gibberish, not a real POI name.", **dup_fields)

    if duplicate_of is not None:
        return POIJudgment(
            suitable=True,
            reason=f"Name looks plausible but duplicates existing POI '{duplicate_of}' (heuristic name match only).",
            **dup_fields,
        )

    return POIJudgment(
        suitable=True,
        reason="Name looks like a plausible POI label (heuristic check only — no AI or map verification).",
        **dup_fields,
    )
