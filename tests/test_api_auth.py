"""API token authentication tests."""

import asyncio
from unittest.mock import patch

import httpx

from infocepo_mcp.sse_server import router


def _get(path: str, headers: dict | None = None):
    async def request():
        transport = httpx.ASGITransport(app=router)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(request())


def test_api_token_protects_endpoints_but_not_health():
    with patch.dict("os.environ", {"API_TOKEN": "secret"}):
        assert _get("/health").status_code == 200
        response = _get("/openapi.json")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_bearer_and_api_key_authentication():
    with patch.dict("os.environ", {"API_TOKEN": "secret"}):
        assert _get("/openapi.json", {"Authorization": "Bearer secret"}).status_code == 200
        assert _get("/openapi.json", {"X-API-Key": "secret"}).status_code == 200
