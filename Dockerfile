FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY src/infocepo_mcp/__init__.py src/infocepo_mcp/__init__.py
COPY src/infocepo_mcp/server.py src/infocepo_mcp/server.py
COPY src/infocepo_mcp/config.py src/infocepo_mcp/config.py
COPY src/infocepo_mcp/services.py src/infocepo_mcp/services.py
COPY src/infocepo_mcp/tools.py src/infocepo_mcp/tools.py
COPY src/infocepo_mcp/wiki_fetcher.py src/infocepo_mcp/wiki_fetcher.py
COPY src/infocepo_mcp/sse_server.py src/infocepo_mcp/sse_server.py

RUN pip install --no-cache-dir -e ".[all]" && \
    pip install --no-cache-dir uvicorn starlette

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8085

EXPOSE 8085

CMD ["python3", "-m", "infocepo_mcp.sse_server"]
