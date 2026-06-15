import re
import httpx
from app.config import settings
from app.models.schemas import AuthConfig, SchemaResult, SanityResult
from app.services.target_client import build_headers, single_request
from app.services.schema_validator import validate_schema
from app.services import llm_judge

_PLACEHOLDER_RE = re.compile(
    r"\b(lorem ipsum|todo|tbd|placeholder|example|foo|bar|baz|dummy)\b", re.I
)


def _coords_sane(obj) -> list[str]:
    """Walk the response, sanity-check anything shaped like [lat, lon]."""
    issues: list[str] = []

    def walk(node):
        if (
            isinstance(node, (list, tuple))
            and len(node) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in node)
        ):
            lat, lon = node
            if not (settings.lat_min <= lat <= settings.lat_max):
                issues.append(f"latitude out of range: {lat}")
            if not (settings.lon_min <= lon <= settings.lon_max):
                issues.append(f"longitude out of range: {lon}")
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return issues


def _deterministic_sanity(body) -> list[str]:
    issues = _coords_sane(body)
    if _PLACEHOLDER_RE.search(str(body)):
        issues.append("response contains placeholder/static text")
    return issues


async def run(
    endpoint: str,
    method: str,
    auth: AuthConfig,
    payload: dict,
    response_schema: dict,
) -> tuple[SchemaResult, SanityResult, dict | None]:
    headers = build_headers(auth)
    async with httpx.AsyncClient() as client:
        try:
            resp = await single_request(
                client, method, endpoint, payload, headers,
                settings.crowd_request_timeout_s,
            )
        except httpx.HTTPError as exc:
            err = f"probe request failed: {exc!r}"
            return (
                SchemaResult(passed=False, errors=[err]),
                SanityResult(passed=False, issues=[err]),
                None,
            )

    try:
        body = resp.json()
    except ValueError:
        err = "response body is not valid JSON"
        return (
            SchemaResult(passed=False, errors=[err]),
            SanityResult(passed=False, issues=[err]),
            None,
        )

    # --- schema ---
    schema_errors = validate_schema(body, response_schema)
    schema_result = SchemaResult(passed=not schema_errors, errors=schema_errors)

    # --- sanity: deterministic rules first, then optional LLM judge ---
    issues = _deterministic_sanity(body)
    notes: list[str] = []
    llm_used = False

    if settings.enable_llm_sanity:
        if not llm_judge.has_credentials():
            notes.append(
                "LLM sanity skipped: no ANTHROPIC_API_KEY "
                "(set ENABLE_LLM_SANITY=false to silence)"
            )
        else:
            try:
                judgment = await llm_judge.judge_response(payload, body)
                llm_used = True
                if not judgment.is_legitimate:
                    issues.extend(judgment.issues)
            except Exception as exc:  # degrade gracefully — don't reject on judge error
                notes.append(f"LLM sanity unavailable: {exc!r}")

    sanity_result = SanityResult(
        passed=not issues, issues=issues, llm_used=llm_used, notes=notes
    )
    return schema_result, sanity_result, body
