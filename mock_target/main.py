"""A fake third-party navigation API to validate against.

Run it on a separate port:
    uvicorn mock_target.main:app --port 9000

Endpoints:
    POST /route/good      -> schema-valid, sane route (should be Approved)
    POST /route/bad-data  -> hallucinated coords + placeholder text (Rejected)
    POST /route/slow      -> adds ~400ms latency (fails the p95 budget)
    POST /route/flaky     -> returns 500 ~10% of the time (fails error budget)
"""
import asyncio
import random
from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="Mock Navigation Target")


class RouteRequest(BaseModel):
    origin: list[float]
    destination: list[float]


def _good_route(req: RouteRequest) -> dict:
    return {
        "route": {
            "distance_m": 4200,
            "duration_s": 540,
            "geometry": [req.origin, [40.71, -74.00], req.destination],
        }
    }


@app.post("/route/good")
async def good(req: RouteRequest):
    return _good_route(req)


@app.post("/route/bad-data")
async def bad_data(req: RouteRequest):
    return {
        "route": {
            "distance_m": -1,
            "duration_s": 0,
            "summary": "example placeholder route",  # static text
            "geometry": [[412.7, -999.0], [0.0, 0.0]],  # hallucinated coords
        }
    }


@app.post("/route/slow")
async def slow(req: RouteRequest):
    await asyncio.sleep(0.4)  # 400ms -> blows the 300ms p95 budget
    return _good_route(req)


@app.post("/route/flaky")
async def flaky(req: RouteRequest):
    if random.random() < 0.10:
        return Response(status_code=500)
    return _good_route(req)
