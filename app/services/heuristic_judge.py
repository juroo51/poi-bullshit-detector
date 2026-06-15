"""Key-free fallback judge.

No AI and no map data, so it cannot assess geographic plausibility. It does a
cheap sanity check on the *name*: rejects placeholder text and obvious
gibberish, accepts anything that looks like a real POI label.
"""

import re

from app.services.poi_judge import POIJudgment

_PLACEHOLDERS = {
    "lorem", "ipsum", "example", "sample", "placeholder", "todo", "tbd",
    "foo", "bar", "baz", "test", "testing", "dummy", "asdf", "qwerty",
    "string", "none", "null", "n/a", "na", "xxx", "untitled", "unknown",
}
_VOWELS = set("aeiouy")


def judge(name: str, lat: float, lon: float) -> POIJudgment:
    cleaned = name.strip()
    lowered = cleaned.lower()
    words = set(re.findall(r"[a-z]+", lowered))

    if words & _PLACEHOLDERS or lowered in _PLACEHOLDERS:
        return POIJudgment(suitable=False, reason="Name looks like placeholder text, not a real POI.")

    if not re.search(r"[a-z]", lowered):
        return POIJudgment(suitable=False, reason="Name has no letters; not a usable POI label.")

    if re.fullmatch(r"(.)\1+", lowered):
        return POIJudgment(suitable=False, reason="Name is a single repeated character; not a real POI.")

    # A long all-consonant word (and not a short acronym) reads as gibberish.
    longest = max(words, key=len, default="")
    is_acronym = cleaned.isupper() and len(cleaned) <= 5
    if len(longest) >= 5 and not (_VOWELS & set(longest)) and not is_acronym:
        return POIJudgment(suitable=False, reason=f"'{cleaned}' looks like gibberish, not a real POI name.")

    return POIJudgment(
        suitable=True,
        reason="Name looks like a plausible POI label (heuristic check only — no AI or map verification).",
    )
