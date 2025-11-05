#!/usr/bin/env bash

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <tool-script> [args...]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "docker-compose.yml not found: $COMPOSE_FILE" >&2
  exit 1
fi

TOOL_SCRIPT=$1
shift

# Use exec instead of run for faster execution (connects to running container)
docker compose -f "$COMPOSE_FILE" exec -T mcp-python-tool \
  python -m tools.runner "$TOOL_SCRIPT" "$@"
