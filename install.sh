#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$HOME/venv/$(basename "$PROJECT_DIR")}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

mkdir -p "$(dirname "$VENV_DIR")"
# Reusing the environment and syncing the project makes install and upgrade
# runs idempotent on both x86_64 (H100/DGX) and aarch64 (DGX Spark).
uv venv --python "${PYTHON_VERSION:-3.11}" --allow-existing "$VENV_DIR"
VIRTUAL_ENV="$VENV_DIR" uv sync --active --upgrade

printf 'Installed %s in %s\n' "$(basename "$PROJECT_DIR")" "$VENV_DIR"
