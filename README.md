# Navigation API Validator

An AI-assisted service that vets third-party navigation APIs before they're
admitted to a routing backend. A submission is **Approved** only if it returns
schema-valid, sane data **and** survives a high-concurrency burst within
latency/error budgets.

Three modules, run as a pipeline:

1. **Bullshit Detector** — hits the endpoint, validates the response against a
   strict JSON Schema, then checks data sanity (coordinate bounds + placeholder
   text via deterministic rules, plus an optional **Claude Opus 4.8** judge for
   hallucinated/degenerate routes). Acts as a gate.
2. **Crowd Tester** — fires a brief, high-concurrency load burst (async +
   `httpx`) and tracks RPS, 5xx error rate, and p50/p95/p99 latency. Fails on
   p95 > 300 ms or 5xx rate > 1%.
3. **Report Generator** — compiles a structured JSON verdict
   (`Approved` / `Rejected` + specific reasons).

## Quickstart

```bash
cd api-validator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optionally add ANTHROPIC_API_KEY
```

No Anthropic key? Set `ENABLE_LLM_SANITY=false` in `.env` (the deterministic
sanity rules still run). With a key, the LLM judge adds hallucination/placeholder
detection.

### Try it end-to-end with the mock target

Terminal 1 — the fake third-party API to validate:

```bash
uvicorn mock_target.main:app --port 9000
```

Terminal 2 — the validator service:

```bash
uvicorn app.main:app --port 8000
```

Terminal 3 — submit endpoints for validation:

```bash
# Approved: valid schema, sane data, fast
curl -s localhost:8000/validate -H 'content-type: application/json' \
  -d @examples/good.json | python -m json.tool

# Rejected: hallucinated coords + placeholder text (load test skipped by the gate)
curl -s localhost:8000/validate -H 'content-type: application/json' \
  -d @examples/bad_data.json | python -m json.tool

# Rejected: passes data checks but p95 latency blows the 300ms budget
curl -s localhost:8000/validate -H 'content-type: application/json' \
  -d @examples/slow.json | python -m json.tool
```

Interactive docs: http://localhost:8000/docs

## Request shape

```json
{
  "endpoint": "https://api.example.com/route",
  "method": "POST",
  "auth": { "type": "bearer", "token": "..." },
  "sample_payload": { "origin": [40.71, -74.0], "destination": [40.73, -73.93] },
  "response_schema": { "type": "object", "required": ["route"], "properties": {} }
}
```

`auth.type` is one of `none`, `bearer`, or `api_key_header` (with `header_name`).

## Configuration

All thresholds are env-driven (see `.env.example`): `CROWD_P95_MS`,
`CROWD_ERROR_RATE`, `CROWD_CONCURRENCY`, `CROWD_DURATION_S`, coordinate bounds,
and `ENABLE_LLM_SANITY`.

## Tests

```bash
pytest -q
```

## Project layout

```
app/
  main.py                  FastAPI app + /validate route
  config.py                env-driven settings & thresholds
  models/schemas.py        Pydantic: request, per-module results, Verdict
  core/orchestrator.py     runs the 3 modules, assembles the verdict
  modules/
    bullshit_detector.py   schema validation + data sanity (gate)
    crowd_tester.py        async load generator + metrics
    report_generator.py    Verdict assembly
  services/
    target_client.py       authed requests to the user's API
    schema_validator.py    jsonschema wrapper
    llm_judge.py           Claude Opus 4.8 sanity judge
mock_target/               a fake nav API to validate against
examples/                  ready-to-POST request bodies
tests/                     unit tests
```

## Production notes

- The Crowd Tester fires **real traffic** at a user-supplied URL. Before going
  live: verify the submitter owns the endpoint (so this can't be abused as a
  DDoS-by-proxy), and cap concurrency/duration server-side.
- A 10s synchronous load test ties up the worker. For production, move the
  Crowd Tester to a background job (e.g. `arq`/Celery) and have `/validate`
  return a `job_id` to poll.
- The deterministic sanity rules are free and instant; gate the LLM judge (or
  sample it) to control cost.
- The load generator is **closed-loop** (steady concurrency = "N simultaneous
  users"). For a fixed arrival rate regardless of latency, switch to a
  rate-paced spawner in `crowd_tester.run`.
```
