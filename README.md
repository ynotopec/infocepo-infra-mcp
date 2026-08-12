# infocepo-infra-mcp

MCP server for infocepo infrastructure services. The HTTP server exposes the
current, stateless **Streamable HTTP** transport at `/mcp`, legacy SSE at `/sse`,
and an OpenAPI facade for diagnostics and direct tool calls.

## Requirements

- Linux
- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)

The same installation works on x86_64 H100/DGX and aarch64 DGX Spark hosts.
This project does not install or pin CUDA drivers.

## Install and run

```bash
./install.sh                         # safe to repeat; also upgrades dependencies
cp .env.example .env
# Edit .env, then export it into the process environment:
set -a; source .env; set +a
./run.sh 0.0.0.0 8085               # omit PORT to select a free port
```

The virtual environment is stored at `~/venv/infocepo-infra-mcp`, or at
`$VENV_DIR` when that variable is set. `run.sh` stays in the foreground and
handles termination normally. It starts `infocepo_mcp.sse_server`, not the
stdio entry point.

Confirm that the server is running:

```bash
curl http://localhost:8085/health
```

When `API_TOKEN` is configured, connect an MCP client with either supported
authentication header:

```text
URL: http://localhost:8085/mcp
Authorization: Bearer <API_TOKEN>
```

`X-API-Key: <API_TOKEN>` is accepted as an alternative. The health endpoint is
always public. If `API_TOKEN` is unset, all endpoints are public; this is useful
for local development but is not recommended on an exposed interface.

### systemd example

Because `.env` is loaded by the Python process but shell variables in it are not
automatically exported, use systemd's `EnvironmentFile` support:

```ini
[Service]
WorkingDirectory=/path/to/infocepo-infra-mcp
EnvironmentFile=/path/to/infocepo-infra-mcp/.env
ExecStart=/bin/bash /path/to/infocepo-infra-mcp/run.sh 127.0.0.1 8085
Restart=on-failure
```

## Configuration

The two API keys have different purposes:

- `API_TOKEN` optionally protects this server's MCP, SSE, and OpenAPI routes.
- `INFOCEPO_API_KEY` authenticates calls from tools to the upstream infocepo
  LLM, audio, image, and diarization services. Tools that do not use those
  services can run without it.

Additional credentials enable service-specific tools:

| Variable | Used by | Required |
| --- | --- | --- |
| `INFOCEPO_CHROMA_TOKEN` | `chromadb_*` | For ChromaDB tools |
| `INFOCEPO_S3_ACCESS_KEY` | `s3_*` | For S3 tools |
| `INFOCEPO_S3_SECRET_KEY` | `s3_*` | For S3 tools |
| `INFOCEPO_REGISTRY_USER` | `registry_list` | Optional; defaults to `user` |
| `INFOCEPO_REGISTRY_PASSWORD` | `registry_list` | For registry access |
| `INFOCEPO_CREDENTIALS_FILE` | All upstream credentials | Optional JSON alternative to environment variables |
| `MCP_HOST` | HTTP listener | Optional; defaults to `0.0.0.0` |
| `MCP_PORT` | HTTP listener | Optional; defaults to `8085` when launching the module directly |
| `VENV_DIR` | Installer and run script | Optional virtual-environment location |

The credentials JSON file accepts `api_key`, `chroma_token`, `s3_access_key`,
`s3_secret_key`, `registry_user`, and `registry_password` keys. Environment
variables are loaded first; values present in the JSON file override them.

## HTTP endpoints

| Endpoint | Methods | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Public liveness response and tool count |
| `/mcp` | `GET`, `POST`, `DELETE` | Stateless Streamable HTTP MCP transport |
| `/sse` | `GET` | Legacy SSE MCP connection |
| `/messages` | `POST` | Legacy SSE client messages |
| `/openapi.json` | `GET` | OpenAPI description of direct tool routes |
| `/sse/openapi.json` | `GET` | Redirect used by Open WebUI probes |
| `/tools/{tool_name}` | `POST` | Invoke one tool through the OpenAPI facade |

Except for `/health` and CORS preflight requests, all endpoints require
`API_TOKEN` when it is configured.

## Tools

The server currently publishes 19 tools:

| Area | Tools |
| --- | --- |
| Wiki discovery | `infra_list_services`, `infra_refresh_discovery`, `infra_read_wiki`, `infra_parse_wiki` |
| LLM and vision | `llm_chat`, `llm_vision` |
| Audio | `stt_transcribe`, `tts_speech`, `diarize_audio` |
| Images and embeddings | `image_generate`, `embeddings_create` |
| ChromaDB | `chromadb_collections`, `chromadb_search`, `chromadb_upsert` |
| Summary | `summary_text` |
| Registry | `registry_list` |
| S3 | `s3_list`, `s3_upload`, `s3_download` |

The four discovery tools all use the same MediaWiki API. A failure reported by
all four therefore normally identifies one shared wiki upstream/path problem;
it does **not** show that the LLM, audio, image, ChromaDB, registry, or S3 tools
are unavailable. Discovery responses include an `upstream` object containing
the failing URL, HTTP status when available, and failure kind.

## Open WebUI and MCPO

MCPO operations have names such as `call_infra_list_services`. The `call_`
prefix belongs to MCPO's generated OpenAPI operation and is not part of the MCP
tool name (`infra_list_services`).

Start the provided bridge with:

```bash
docker compose -f docker-compose.mcpo.yml up -d
docker compose -f docker-compose.mcpo.yml logs -f mcpo
```

The sample compose file exposes MCPO at `http://localhost:8000`; its OpenAPI
document is at `/openapi.json` and Swagger UI is at `/docs`. The checked-in
`mcpo-config/config.json` connects MCPO to `http://host.docker.internal:8085/mcp`.
If the MCP server has `API_TOKEN` set, add the same bearer token to that file's
`headers` object, for example:

```json
"headers": {
  "Authorization": "Bearer replace-me"
}
```

`MCPO_API_KEY` is conceptually separate from `API_TOKEN`: it protects MCPO's
generated OpenAPI API and is configured on the MCPO process/client. The sample
compose file currently passes its MCPO key directly with `--api-key`.

Check each layer independently:

```bash
curl http://localhost:8085/health
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8085/openapi.json
curl -H "Authorization: Bearer $MCPO_API_KEY" http://localhost:8000/openapi.json
curl "https://infocepo.com/wiki/api.php?action=query&titles=Main_Page&format=json"
```

## Other entry points

The package also installs `infocepo-mcp`, the stdio transport implemented by
`infocepo_mcp.server`, and `infocepo-mcp-http`, an alias for the HTTP server.
For normal network operation, prefer `run.sh` or `infocepo-mcp-http`.

## Tests

```bash
uv run pytest
```
