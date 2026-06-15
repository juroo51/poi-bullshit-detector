from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AuthType(str, Enum):
    none = "none"
    bearer = "bearer"
    api_key_header = "api_key_header"


class AuthConfig(BaseModel):
    type: AuthType = AuthType.none
    token: str | None = None              # bearer token, or api-key value
    header_name: str = "Authorization"    # used for api_key_header


class ValidationRequest(BaseModel):
    endpoint: str = Field(..., description="Full URL of the target API")
    method: str = "POST"
    auth: AuthConfig = AuthConfig()
    sample_payload: dict[str, Any] = Field(
        ..., description="e.g. {'origin': [lat, lon], 'destination': [lat, lon]}"
    )
    response_schema: dict[str, Any] = Field(
        ..., description="JSON Schema the response must satisfy"
    )


# ---- Per-module results ----------------------------------------------------

class SchemaResult(BaseModel):
    passed: bool
    errors: list[str] = []


class SanityResult(BaseModel):
    passed: bool
    issues: list[str] = []
    llm_used: bool = False
    notes: list[str] = []


class LatencyStats(BaseModel):
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


class LoadResult(BaseModel):
    ran: bool                              # False if gated out
    total_requests: int = 0
    rps: float = 0.0
    error_rate: float = 0.0                # fraction of 5xx
    latency: LatencyStats | None = None
    passed: bool = False
    reasons: list[str] = []


# ---- Final verdict ---------------------------------------------------------

class Status(str, Enum):
    approved = "Approved"
    rejected = "Rejected"


class Verdict(BaseModel):
    status: Status
    failure_reasons: list[str] = []
    schema_check: SchemaResult
    sanity_check: SanityResult
    load_test: LoadResult
