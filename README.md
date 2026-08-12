# infocepo-infra-mcp

Token-protected MCP server for infocepo infrastructure. Its primary API is the
current, widely supported **Streamable HTTP** transport at `/mcp`; legacy SSE is
also available at `/sse`.

## Start

Requires Linux, Python 3.11+ and [`uv`](https://docs.astral.sh/uv/). The same
install works on x86_64 H100/DGX hosts and aarch64 DGX Spark hosts; this project
does not install or pin CUDA drivers.

```bash
./install.sh                         # safe to repeat; also upgrades dependencies
cp .env.example .env                 # edit both required secrets
source run.sh 0.0.0.0 8085           # omit PORT to select a free port
```

The virtual environment is stored at `~/venv/infocepo-infra-mcp` (or
`$VENV_DIR`). Check it with `curl http://localhost:8085/health`, then connect a
client to `http://localhost:8085/mcp` using `Authorization: Bearer $API_TOKEN`
(the common `X-API-Key` header is accepted too).

`run.sh` stays in the foreground, handles termination normally, and is therefore
also suitable for a user unit:

```ini
[Service]
WorkingDirectory=/path/to/infocepo-infra-mcp
ExecStart=/bin/bash /path/to/infocepo-infra-mcp/run.sh 127.0.0.1 8085
Restart=on-failure
```

Run tests with `uv run pytest`.

## Open WebUI / MCPO diagnostics

Open WebUI exposes MCPO operations with names such as
`call_infra_list_services`; that `call_` prefix belongs to the generated
OpenAPI operation and is not an MCP tool name. The corresponding MCP tool is
`infra_list_services`.

The four discovery tools (`infra_list_services`, `infra_refresh_discovery`,
`infra_read_wiki`, and `infra_parse_wiki`) all use the same MediaWiki API.
Consequently, a 404 reported by all four tools normally identifies one shared
wiki upstream/path failure; it does **not** demonstrate that the LLM, audio,
image, ChromaDB, registry, or S3 tools are unavailable. Tool responses include
an `upstream` object with the failing URL, HTTP status, and failure kind so the
MCPO/Open WebUI result can distinguish a missing page from a missing API route.

Check each layer independently:

```bash
curl http://localhost:8085/health
curl -H "Authorization: Bearer $MCPO_API_KEY" http://localhost:8000/openapi.json
curl "https://infocepo.com/wiki/api.php?action=query&titles=Main_Page&format=json"
```

If `API_TOKEN` protects the MCP server, add the same bearer token to the
`headers` object in `mcpo-config/config.json`. `MCPO_API_KEY` is separate: it
protects MCPO's generated OpenAPI API and must be configured in Open WebUI.
