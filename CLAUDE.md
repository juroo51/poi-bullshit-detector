# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A FastAPI service that vets **points of interest**. A caller POSTs a POI name, a coordinate, and optionally a list of existing nearby POI names (`candidates`) to `/check`; the service decides whether that name is a suitable, plausible label for a place at that location, and whether it duplicates one of the candidates, returning a `{suitable, reason, model, duplicate, duplicate_of}` verdict. It uses a **free, locally-run LLM via [Ollama](https://ollama.com)** (no API key, no cloud); if Ollama is unreachable it falls back to a key-free **heuristic judge** (name sanity + normalized duplicate match), so the service always runs.

## Commands

```bash
source .venv/bin/activate              # venv exists (Python 3.14)
pip install -r requirements.txt

pytest -q                              # all tests (Ollama call is stubbed — runs offline)
pytest tests/test_units.py::test_check_returns_verdict   # single test

uvicorn app.main:app --port 8000       # the service; docs at /docs
```

Using the real LLM needs Ollama running with the model pulled: `ollama serve` then `ollama pull llama3.2` (see README). The test suite stubs the Ollama call, so it needs nothing installed.

Smoke test: with the server running, POST `{"name": "groceries", "lat": 48.143890, "lon": 17.283289}` to `localhost:8000/check`. The response `model` field is `llama3.2` when Ollama answered, `heuristic` when it fell back.

## Architecture

A single LLM call wrapped in thin layers — no pipeline, no outbound probing of third-party APIs.

1. **Request** ([app/models/schemas.py](app/models/schemas.py)) — `POICheckRequest` validates `name` (non-empty) and `lat`/`lon` against the configured bounds; out-of-range coords yield a 422 before any model call. `candidates` is an optional `list[str]` of existing nearby POI names (defaults to `[]`).
2. **LLM judge** ([app/services/poi_judge.py](app/services/poi_judge.py)) — the primary. Calls Ollama's `chat(...)` with `format=POIJudgment.model_json_schema()` (structured output) and `temperature=0` on `settings.llm_model` (default `llama3.2`), then validates the JSON into `POIJudgment{suitable, reason, duplicate, duplicate_of}`. It judges both suitability and **semantic** same-place duplicates against `candidates` in the one call; the prompt is strict — same-category-different-place is *not* a duplicate.
3. **Heuristic judge** ([app/services/heuristic_judge.py](app/services/heuristic_judge.py)) — key-free fallback returning the same `POIJudgment`. No AI/map data, so it sanity-checks the *name* only (placeholder + gibberish rejection) and detects duplicates via `find_duplicate` (normalized string equality: case/punctuation/whitespace/accents ignored). Don't let it claim geographic verification — the reason string says "heuristic check only".
4. **Checker** ([app/core/checker.py](app/core/checker.py)) — if `poi_judge.is_enabled()` (`ENABLE_LLM`), tries the LLM judge and **catches `_LLM_FAILURES`** (Ollama down, model missing, malformed output) to fall back to the heuristic. Sets `model` to `llama3.2` or `"heuristic"`. In `_to_response` it applies a **deterministic dedup backstop**: `heuristic_judge.find_duplicate` forces `duplicate=true` for exact/normalized matches the LLM missed (small local models drop even identical strings), then builds `POICheckResponse`. `duplicate` is reported independently of `suitable`.
5. **Endpoint** ([app/main.py](app/main.py)) — `/check` always returns 200; the fallback is handled in the checker, so the route stays trivial.

Layering: `core/` orchestrates, `services/` holds the two judges. The LLM judge judges **plausibility from geographic knowledge**, not live map presence — keep that framing in the system prompt.

### poi_judge specifics
This is a deliberately provider-neutral, **non-Anthropic** integration — it talks to a local Ollama server via the `ollama` Python client. Do not reintroduce the Anthropic SDK or the `claude-api` patterns here. Structured output is done with Ollama's `format=<json schema>`; keep `temperature=0` for stable verdicts. To use a different local model, change `LLM_MODEL` to anything you've `ollama pull`ed. The duplicate rule in `_SYSTEM` is intentionally strict (exact-same-place only); the checker's deterministic backstop is what guarantees exact matches, so don't loosen the prompt to compensate for a weak model.

## Conventions

- **All bounds and model settings are env-driven** via [app/config.py](app/config.py) (`pydantic-settings`, reads `.env`). Env var names are the upper-cased field names (`ENABLE_LLM`, `LLM_MODEL`, `OLLAMA_HOST`, `LAT_MIN`, …); see `.env.example`. Don't hardcode coordinate limits, the model ID, or the host — reference `settings.<name>`.
- **Typed Pydantic models end to end** ([app/models/schemas.py](app/models/schemas.py), `POIJudgment` in the judge). Add new output fields to the relevant model, not loose dicts.
- The `/check` call is a single awaited model call — fast enough to run inline in the request.
