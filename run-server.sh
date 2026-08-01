#!/bin/bash
# Wrapper for infocepo-infra MCP server
# Injects API key from ~/.infocepo-credentials or INFOCEPO_API_KEY env var

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Try ~/.infocepo-credentials first, then fall back to env var
if [ -f "$HOME/.infocepo-credentials" ]; then
    KEY=$(python3 -c "import json; print(json.load(open('$HOME/.infocepo-credentials'))['api_key'])" 2>/dev/null)
    if [ -n "$KEY" ]; then
        export INFOCEPO_API_KEY="$KEY"
    fi
fi

# If still no key, try env var directly
if [ -z "$INFOCEPO_API_KEY" ]; then
    export INFOCEPO_API_KEY="${INFOCEPO_API_KEY:-}"
fi

exec "$SCRIPT_DIR/.venv/bin/python" -m infocepo_mcp.server "$@"
