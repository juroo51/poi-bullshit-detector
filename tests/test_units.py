from app.services.schema_validator import validate_schema
from app.modules.bullshit_detector import _coords_sane, _deterministic_sanity
from app.modules.crowd_tester import _percentile
from app.models.schemas import SchemaResult, SanityResult, LoadResult, LatencyStats, Status
from app.modules import report_generator


SCHEMA = {
    "type": "object",
    "required": ["route"],
    "properties": {"route": {"type": "object"}},
}


def test_schema_valid():
    assert validate_schema({"route": {}}, SCHEMA) == []


def test_schema_invalid_reports_missing_field():
    errors = validate_schema({"not_route": 1}, SCHEMA)
    assert errors and "route" in errors[0]


def test_coords_out_of_range_flagged():
    issues = _coords_sane({"geometry": [[412.7, -999.0]]})
    assert any("latitude" in i for i in issues)
    assert any("longitude" in i for i in issues)


def test_coords_in_range_clean():
    assert _coords_sane({"geometry": [[40.71, -74.0]]}) == []


def test_placeholder_text_flagged():
    issues = _deterministic_sanity({"summary": "example placeholder route"})
    assert any("placeholder" in i for i in issues)


def test_percentile_basic():
    data = [float(x) for x in range(1, 101)]  # 1..100
    assert _percentile(data, 0.50) == 50.5
    assert _percentile(data, 0.95) == 95.05
    assert _percentile(data, 0.99) == 99.01


def test_verdict_approved_when_all_pass():
    verdict = report_generator.build(
        SchemaResult(passed=True),
        SanityResult(passed=True),
        LoadResult(
            ran=True, passed=True, total_requests=100, rps=10.0, error_rate=0.0,
            latency=LatencyStats(p50_ms=50, p95_ms=120, p99_ms=200, max_ms=250),
        ),
    )
    assert verdict.status == Status.approved
    assert verdict.failure_reasons == []


def test_verdict_rejected_collects_reasons():
    verdict = report_generator.build(
        SchemaResult(passed=False, errors=["<root>: missing route"]),
        SanityResult(passed=False, issues=["latitude out of range: 412.7"]),
        LoadResult(ran=False),
    )
    assert verdict.status == Status.rejected
    assert any("schema:" in r for r in verdict.failure_reasons)
    assert any("sanity:" in r for r in verdict.failure_reasons)
    assert any("skipped" in r for r in verdict.failure_reasons)
