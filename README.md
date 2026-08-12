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
