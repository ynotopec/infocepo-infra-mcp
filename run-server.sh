#!/bin/bash
# Wrapper for infocepo-infra MCP server with API key
INFOCEPO_API_KEY='AntonioPacheco$999' exec /home/ai-agent/work/infocepo-infra-mcp/.venv/bin/python -m infocepo_mcp.server "$@"
