# POI Bullshit Detector

An AI service that vets **points of interest**. You POST a POI name, a
coordinate, and optionally a list of existing nearby POI names; the service asks
a **free, locally-run LLM** (via [Ollama](https://ollama.com)) whether that name
is a suitable, plausible label for a place at that location, and whether it
duplicates one of the supplied names. It returns a `true` / `false` suitability
verdict with a short reason plus a duplicate flag. No API key, no cloud.

```
POST /check  { "name": "groceries", "lat": 48.143890, "lon": 17.283289, "candidates": ["Pharmacy"] }
        ↓
{ "suitable": true, "reason": "These coordinates fall in urban Bratislava, where a grocery store is entirely plausible.", "model": "llama3.2", "duplicate": false, "duplicate_of": null }
```

## How it works

The model judges **plausibility**, not exact presence — it has no live map
data. Given the name and the coordinate it reasons from its knowledge of world
geography (country, city, urban vs rural, land vs water) about whether such a
POI could reasonably exist there, and whether the name is a real POI label
rather than gibberish or placeholder text. The output is constrained to a typed
shape via Ollama's JSON-schema structured output.

If Ollama isn't running (or `ENABLE_LLM=false`), `/check` transparently falls
back to a key-free **heuristic judge** that sanity-checks the name only — it
rejects placeholder text and gibberish but can't assess whether the place fits
the coordinates. The `model` field in the response tells you which ran
(`llama3.2` vs `heuristic`).

### Duplicate detection

When you pass `candidates` (existing nearby POI names), the service also reports
whether `name` duplicates one of them via `duplicate` and `duplicate_of`. These
are **independent of `suitable`** — a name can be a plausible label yet still
duplicate an existing entry. Two layers run:

- A **deterministic match** (always on) flags exact/normalized duplicates —
  case, punctuation, whitespace, and accents are ignored (`"Lidl"` vs `"lidl"`).
  This never misses an exact match, regardless of which judge ran.
- The **LLM judge** additionally catches *semantic* same-place duplicates (e.g.
  `"Eiffel Tower"` vs `"Tour Eiffel"`). It is strict: different places of the
  same category (`"groceries"` vs `"Supermarket"`) are **not** duplicates.

## Quickstart

```bash
cd poi-bullshit-detector
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Install and start the free local model (one-time):

```bash
# https://ollama.com/download
ollama serve            # start the local server (often already running)
ollama pull llama3.2    # download the model (~2 GB)
```

No GPU required — `llama3.2` (3B) runs on CPU. Swap in any model you've pulled
via `LLM_MODEL`.

### Run it

```bash
uvicorn app.main:app --port 8000
```

```bash
# Suitable
curl -s localhost:8000/check -H 'content-type: application/json' \
  -d '{"name": "groceries", "lat": 48.143890, "lon": 17.283289}' | python -m json.tool

# Not suitable — a landmark nowhere near its real location
curl -s localhost:8000/check -H 'content-type: application/json' \
  -d '{"name": "Eiffel Tower", "lat": 48.143890, "lon": 17.283289}' | python -m json.tool

# Not suitable — placeholder text
curl -s localhost:8000/check -H 'content-type: application/json' \
  -d '{"name": "lorem ipsum", "lat": 48.143890, "lon": 17.283289}' | python -m json.tool

# Duplicate — name already exists in the supplied candidates
curl -s localhost:8000/check -H 'content-type: application/json' \
  -d '{"name": "Lidl", "lat": 48.143890, "lon": 17.283289, "candidates": ["lidl", "Pharmacy"]}' | python -m json.tool
```

Interactive docs: http://localhost:8000/docs

## Request shape

```json
{
  "name": "groceries",
  "lat": 48.143890,
  "lon": 17.283289,
  "candidates": ["Pharmacy", "Bakery"]
}
```

`name` must be non-empty; `lat`/`lon` are validated against the configured
bounds (default full globe) and a 422 is returned if out of range. `candidates`
is an optional list of existing nearby POI names to check `name` against for
duplicates — it defaults to `[]` (no duplicate checking).

## Response shape

```json
{
  "suitable": true,
  "reason": "Urban Bratislava; a grocery store is plausible.",
  "model": "llama3.2",
  "duplicate": false,
  "duplicate_of": null
}
```

| Field          | Type            | Meaning                                                        |
| -------------- | --------------- | -------------------------------------------------------------- |
| `suitable`     | `bool`          | Whether the name suits a POI at this location                  |
| `reason`       | `string`        | Short explanation of the verdict                               |
| `model`        | `string`        | Which judge ran — `llama3.2` or `heuristic`                    |
| `duplicate`    | `bool`          | Whether `name` duplicates one of the `candidates`              |
| `duplicate_of` | `string`/`null` | The candidate that `name` duplicates, or `null` if none        |

## Configuration

Env-driven (see `.env.example`): `ENABLE_LLM` (default `true`), `LLM_MODEL`
(default `llama3.2`), `OLLAMA_HOST` (default `http://localhost:11434`), and the
coordinate bounds `LAT_MIN`/`LAT_MAX`/`LON_MIN`/`LON_MAX`.

## Tests

```bash
pytest -q
```

The tests stub the Ollama call, so they run offline and need nothing installed.

## Project layout

```
app/
  main.py                      FastAPI app + /check route
  config.py                    env-driven settings
  models/schemas.py            Pydantic: POICheckRequest, POICheckResponse
  core/checker.py              picks a judge by availability, backstops dedup, builds the response
  services/poi_judge.py        Ollama suitability + semantic duplicate judge (structured output)
  services/heuristic_judge.py  key-free fallback (name sanity) + normalized duplicate match
tests/                         unit tests (Ollama call stubbed)
```
