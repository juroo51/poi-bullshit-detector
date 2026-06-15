import os
from anthropic import AsyncAnthropic
from pydantic import BaseModel
from app.config import settings

_SYSTEM = """You are a data-sanity auditor for a navigation routing backend.
You are given a request payload (origin/destination) and the API's JSON response.
Flag the response ONLY for concrete, navigation-relevant problems:
- placeholder / static text ("lorem ipsum", "example", "TODO", "string", "foo")
- coordinates that are obviously hallucinated or inconsistent with the request
- a "route" that is empty, degenerate, or doesn't connect origin to destination
- nonsensical units, durations, or distances (negative, zero, absurd)
Do NOT flag stylistic preferences or anything you cannot justify concretely."""


class SanityJudgment(BaseModel):
    is_legitimate: bool
    issues: list[str]


_client: AsyncAnthropic | None = None


def has_credentials() -> bool:
    return bool(settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def judge_response(payload: dict, response_body: dict) -> SanityJudgment:
    msg = await _get_client().messages.parse(
        model="claude-opus-4-8",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"REQUEST PAYLOAD:\n{payload}\n\n"
                    f"API RESPONSE:\n{response_body}\n\n"
                    "Audit the response."
                ),
            }
        ],
        output_format=SanityJudgment,
    )
    return msg.parsed_output
