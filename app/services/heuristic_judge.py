"""Key-free fallback judge.

No AI and no map data, so it cannot assess geographic plausibility. It does a
cheap sanity check on the *name*: rejects placeholder text and obvious
gibberish, accepts anything that looks like a real POI label. Duplicate
detection is likewise name-only — normalized string equality against the
candidates, not the semantic matching the LLM judge does.
"""

import re
import unicodedata

from app.services.poi_judge import POIJudgment

_PLACEHOLDERS = {
    "lorem", "ipsum", "example", "sample", "placeholder", "todo", "tbd",
    "foo", "bar", "baz", "test", "testing", "dummy", "asdf", "qwerty",
    "string", "none", "null", "n/a", "na", "xxx", "untitled", "unknown",
}
_VOWELS = set("aeiouy")

# Deterministic multilingual profanity backstop. Small local models (llama3.2)
# don't recognize offensive words outside English, so an exact instruction in the
# prompt can't catch e.g. Slovak "kokot". This curated blocklist forces a reject
# regardless of what the model says. Entries are accent-stripped lowercase roots;
# matching is done against the de-obfuscated (leetspeak-folded) name.
_PROFANITY = {
    # English
    "fuck", "shit", "cunt", "bitch", "asshole", "dick", "pussy", "bastard",
    "whore", "slut", "nigger", "faggot", "wank", "twat", "bollocks", "prick",
    # Slovak / Czech
    "kokot", "pica", "kurva", "jebat", "mrdat", "hovno", "sracka", "chuj",
    "debil", "kunda", "curak", "prdel", "zmrd",
    # German
    "scheisse", "arschloch", "fotze", "wichser", "schlampe", "hurensohn",
    # Spanish
    "mierda", "puta", "cono", "joder", "cabron", "gilipollas", "polla",
    # French
    "merde", "putain", "salope", "connard", "encule", "enfoire", "pute",
    # Italian
    "cazzo", "stronzo", "vaffanculo", "troia", "puttana", "coglione",
    # Polish
    "pierdol", "chujnia", "skurwysyn", "spierdalaj",
    # Russian / Ukrainian (transliterated)
    "blyat", "suka", "pizda", "ebat", "huy", "mudak", "yebat",
    # Portuguese
    "caralho", "foda", "merda", "buceta", "porra",
    # Romanian / Hungarian / Dutch
    "pula", "fasz", "kut", "lul",
    # Arabic / Hindi (transliterated)
    "kus", "sharmuta", "chutiya", "bhenchod", "madarchod", "lund", "gandu",
}
# Leetspeak / common symbol substitutions used to disguise the words above.
_LEET = str.maketrans({"4": "a", "@": "a", "3": "e", "1": "i", "!": "i",
                       "0": "o", "5": "s", "$": "s", "7": "t"})


def _strip_accents(text: str) -> str:
    """Fold accented characters to ASCII (e.g. "piča" -> "pica")."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def find_profanity(name: str) -> str | None:
    """Return a blocklisted offensive word in `name`, if any.

    De-obfuscates first (accent-fold + leetspeak), then matches on word
    boundaries: a blocklisted word counts when it equals one of the name's tokens
    OR equals the whole name with separators removed. This catches "kokot",
    "Piča", "KOKOT bar", and obfuscated single words ("k0k0t", "k.o.k.o.t")
    without the substring false positives that flag innocent names like
    "Scunthorpe" or "Essex".
    """
    folded = _strip_accents(name.replace("ß", "ss")).lower().translate(_LEET)
    tokens = set(re.findall(r"[a-z]+", folded))
    tokens.add(re.sub(r"[^a-z]", "", folded))  # collapsed form for spaced-out words
    return next((w for w in _PROFANITY if w in tokens), None)


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

    bad_word = find_profanity(cleaned)
    if bad_word is not None:
        return POIJudgment(suitable=False, reason="Name contains offensive or explicit language.", **dup_fields)

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
