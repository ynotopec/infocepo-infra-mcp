#!/usr/bin/env bash

_infocepo_run() (
  set -euo pipefail
  local project_dir venv_dir host port
  project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  venv_dir="${VENV_DIR:-$HOME/venv/$(basename "$project_dir")}"
  host="${1:-${MCP_HOST:-0.0.0.0}}"
  port="${2:-${MCP_PORT:-}}"

  if [[ ! -x "$venv_dir/bin/python" ]]; then
    echo "Missing environment; run $project_dir/install.sh first." >&2
    return 1
  fi
  if [[ -z "$port" ]]; then
    port="$($venv_dir/bin/python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')"
  fi

  cd "$project_dir"
  export VIRTUAL_ENV="$venv_dir" MCP_HOST="$host" MCP_PORT="$port"
  export PATH="$venv_dir/bin:$PATH"
  echo "Starting on http://$host:$port/mcp" >&2
  python -m infocepo_mcp.sse_server
)

_infocepo_run "$@"
_infocepo_status=$?
unset -f _infocepo_run
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  exit "$_infocepo_status"
else
  return "$_infocepo_status"
fi
