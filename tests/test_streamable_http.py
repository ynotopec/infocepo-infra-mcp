"""Integration tests for the Streamable HTTP MCP transport."""

import asyncio

import httpx

from infocepo_mcp.sse_server import router, streamable_http


def test_streamable_http_initialization():
    async def exercise_transport():
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "api-mcp-openai", "version": "test"},
            },
        }

        async with streamable_http.run():
            transport = httpx.ASGITransport(app=router)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post(
                    "/mcp",
                    headers={"Accept": "application/json, text/event-stream"},
                    json=request,
                )

    response = asyncio.run(exercise_transport())
    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == 1
    assert payload["result"]["serverInfo"]["name"] == "infocepo-infra"
