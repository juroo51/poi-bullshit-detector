import asyncio
import time
import httpx
from app.config import settings
from app.models.schemas import AuthConfig, LoadResult, LatencyStats
from app.services.target_client import build_headers


def _percentile(sorted_ms: list[float], pct: float) -> float:
    if not sorted_ms:
        return 0.0
    k = (len(sorted_ms) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(sorted_ms) - 1)
    return sorted_ms[lo] + (sorted_ms[hi] - sorted_ms[lo]) * (k - lo)


async def run(
    endpoint: str,
    method: str,
    auth: AuthConfig,
    payload: dict,
) -> LoadResult:
    headers = build_headers(auth)
    latencies_ms: list[float] = []
    error_count = 0
    total = 0
    deadline = time.monotonic() + settings.crowd_duration_s
    sem = asyncio.Semaphore(settings.crowd_concurrency)

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=settings.crowd_concurrency * 2)
    ) as client:

        async def one_call():
            nonlocal error_count, total
            async with sem:
                start = time.monotonic()
                try:
                    resp = await client.request(
                        method, endpoint, json=payload, headers=headers,
                        timeout=settings.crowd_request_timeout_s,
                    )
                    status = resp.status_code
                except httpx.HTTPError:
                    status = 599  # treat transport failures as server-side errors
                elapsed_ms = (time.monotonic() - start) * 1000.0
                latencies_ms.append(elapsed_ms)
                total += 1
                if status >= 500:
                    error_count += 1

        tasks: set[asyncio.Task] = set()
        while time.monotonic() < deadline:
            if len(tasks) < settings.crowd_concurrency:
                t = asyncio.create_task(one_call())
                tasks.add(t)
                t.add_done_callback(tasks.discard)
            else:
                await asyncio.sleep(0.001)  # at capacity; let in-flight calls drain
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    latencies_ms.sort()
    error_rate = (error_count / total) if total else 1.0
    stats = LatencyStats(
        p50_ms=round(_percentile(latencies_ms, 0.50), 2),
        p95_ms=round(_percentile(latencies_ms, 0.95), 2),
        p99_ms=round(_percentile(latencies_ms, 0.99), 2),
        max_ms=round(latencies_ms[-1], 2) if latencies_ms else 0.0,
    )

    reasons: list[str] = []
    if stats.p95_ms > settings.crowd_p95_ms:
        reasons.append(
            f"p95 latency {stats.p95_ms}ms exceeds {settings.crowd_p95_ms}ms"
        )
    if error_rate > settings.crowd_error_rate:
        reasons.append(
            f"5xx error rate {error_rate:.2%} exceeds "
            f"{settings.crowd_error_rate:.2%}"
        )

    return LoadResult(
        ran=True,
        total_requests=total,
        rps=round(total / settings.crowd_duration_s, 2) if settings.crowd_duration_s else 0.0,
        error_rate=round(error_rate, 4),
        latency=stats,
        passed=not reasons,
        reasons=reasons,
    )
