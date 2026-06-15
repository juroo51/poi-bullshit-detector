# POI Bullshit Detector

An AI service that vets **points of interest**. You POST a POI name and a
coordinate; the service asks a **free, locally-run LLM** (via
[Ollama](https://ollama.com)) whether that name is a suitable, plausible label
for a place at that location, and returns a `true` / `false` verdict with a
short reason. No API key, no cloud.

```
POST /check  { "name": "groceries", "lat": 48.143890, "lon": 17.283289 }
        ↓
{ "suitable": true, "reason": "These coordinates fall in urban Bratislava, where a grocery store is entirely plausible.", "model": "llama3.2" }
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
```

Interactive docs: http://localhost:8000/docs

## Request shape

```json
{
  "name": "groceries",
  "lat": 48.143890,
  "lon": 17.283289
}
```

`name` must be non-empty; `lat`/`lon` are validated against the configured
bounds (default full globe) and a 422 is returned if out of range.

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
  core/checker.py              picks a judge by availability, builds the response
  services/poi_judge.py        Ollama suitability judge (structured output)
  services/heuristic_judge.py  key-free fallback (name sanity only)
tests/                         unit tests (Ollama call stubbed)
```
