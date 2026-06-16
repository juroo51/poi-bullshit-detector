import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.schemas import POICheckRequest
from app.services import heuristic_judge, poi_judge
from app.services.poi_judge import POIJudgment

client = TestClient(app)


def test_request_accepts_valid_coords():
    req = POICheckRequest(name="groceries", lat=48.143890, lon=17.283289)
    assert req.name == "groceries"


def test_request_rejects_out_of_range_latitude():
    with pytest.raises(ValidationError):
        POICheckRequest(name="groceries", lat=412.7, lon=17.0)


def test_request_rejects_out_of_range_longitude():
    with pytest.raises(ValidationError):
        POICheckRequest(name="groceries", lat=48.0, lon=-999.0)


def test_request_rejects_empty_name():
    with pytest.raises(ValidationError):
        POICheckRequest(name="", lat=48.0, lon=17.0)


def test_check_falls_back_to_heuristic_when_llm_disabled(monkeypatch):
    monkeypatch.setattr(poi_judge, "is_enabled", lambda: False)
    resp = client.post("/check", json={"name": "groceries", "lat": 48.14, "lon": 17.28})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suitable"] is True
    assert body["model"] == "heuristic"


def test_check_returns_verdict(monkeypatch):
    monkeypatch.setattr(poi_judge, "is_enabled", lambda: True)

    async def fake_judge(name, lat, lon, candidates=None):
        return POIJudgment(suitable=True, reason="Urban Bratislava area; groceries are plausible.")

    monkeypatch.setattr(poi_judge, "judge", fake_judge)

    resp = client.post("/check", json={"name": "groceries", "lat": 48.14, "lon": 17.28})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suitable"] is True
    assert "groceries" in body["reason"].lower()
    assert body["duplicate"] is False
    assert body["duplicate_of"] is None


def test_check_reports_duplicate_from_llm(monkeypatch):
    monkeypatch.setattr(poi_judge, "is_enabled", lambda: True)
    seen = {}

    async def fake_judge(name, lat, lon, candidates=None):
        seen["candidates"] = candidates
        return POIJudgment(
            suitable=True,
            reason="Same place as the existing McDonald's listing.",
            duplicate=True,
            duplicate_of="McDonald's",
        )

    monkeypatch.setattr(poi_judge, "judge", fake_judge)

    resp = client.post(
        "/check",
        json={"name": "McDonalds", "lat": 48.14, "lon": 17.28, "candidates": ["McDonald's", "Pharmacy"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["duplicate"] is True
    assert body["duplicate_of"] == "McDonald's"
    assert seen["candidates"] == ["McDonald's", "Pharmacy"]


def test_check_backstops_exact_duplicate_when_llm_misses(monkeypatch):
    monkeypatch.setattr(poi_judge, "is_enabled", lambda: True)

    async def fake_judge(name, lat, lon, candidates=None):
        # Small model wrongly reports no duplicate for an exact match.
        return POIJudgment(suitable=True, reason="Lidl is a real retail chain.")

    monkeypatch.setattr(poi_judge, "judge", fake_judge)

    resp = client.post(
        "/check",
        json={"name": "lidl", "lat": 48.14, "lon": 17.28, "candidates": ["lidl"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["duplicate"] is True
    assert body["duplicate_of"] == "lidl"


def test_request_defaults_candidates_to_empty():
    req = POICheckRequest(name="groceries", lat=48.14, lon=17.28)
    assert req.candidates == []


def test_check_rejects_bad_coords_with_422():
    resp = client.post("/check", json={"name": "groceries", "lat": 999, "lon": 17.28})
    assert resp.status_code == 422


def test_check_falls_back_when_llm_errors(monkeypatch):
    monkeypatch.setattr(poi_judge, "is_enabled", lambda: True)

    async def boom(name, lat, lon, candidates=None):
        raise ConnectionError("ollama not running")

    monkeypatch.setattr(poi_judge, "judge", boom)

    resp = client.post("/check", json={"name": "groceries", "lat": 48.14, "lon": 17.28})
    assert resp.status_code == 200
    assert resp.json()["model"] == "heuristic"


def test_heuristic_accepts_real_name():
    assert heuristic_judge.judge("groceries", 48.14, 17.28).suitable is True


def test_heuristic_accepts_acronym():
    assert heuristic_judge.judge("KFC", 48.14, 17.28).suitable is True


def test_heuristic_rejects_placeholder():
    assert heuristic_judge.judge("lorem ipsum", 48.14, 17.28).suitable is False


def test_heuristic_rejects_gibberish():
    assert heuristic_judge.judge("xkcdz", 48.14, 17.28).suitable is False


def test_heuristic_detects_normalized_duplicate():
    result = heuristic_judge.judge("Groceries!", 48.14, 17.28, ["pharmacy", "  groceries  "])
    assert result.duplicate is True
    assert result.duplicate_of == "  groceries  "


def test_heuristic_no_duplicate_when_no_match():
    result = heuristic_judge.judge("groceries", 48.14, 17.28, ["pharmacy", "bakery"])
    assert result.duplicate is False
    assert result.duplicate_of is None

