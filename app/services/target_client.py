import httpx
from app.models.schemas import AuthConfig, AuthType


def build_headers(auth: AuthConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if auth.type == AuthType.bearer and auth.token:
        headers["Authorization"] = f"Bearer {auth.token}"
    elif auth.type == AuthType.api_key_header and auth.token:
        headers[auth.header_name] = auth.token
    return headers


async def single_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    payload: dict,
    headers: dict[str, str],
    timeout: float,
) -> httpx.Response:
    return await client.request(
        method, url, json=payload, headers=headers, timeout=timeout
    )
