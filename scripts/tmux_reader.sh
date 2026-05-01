#!/usr/bin/env bash

set -eu

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$CURRENT_DIR/.." && pwd)"

# shellcheck source=/dev/null
. "$CURRENT_DIR/helpers.sh"

PANE_ID="${1:-}"
WITH_PREFIX=0

if [ "${2:-}" = "--with-prefix" ]; then
  WITH_PREFIX=1
fi

CACHE_DIR="$(get_tmux_option "@claude-status-cache-dir")"
MAX_AGE_SECONDS="$(get_tmux_option "@claude-status-max-age-seconds")"
PREFIX=""

if [ -z "$CACHE_DIR" ]; then
  CACHE_DIR="$(default_cache_dir)"
fi

if [ -z "$MAX_AGE_SECONDS" ]; then
  MAX_AGE_SECONDS="15"
fi

if [ "$WITH_PREFIX" -eq 1 ]; then
  PREFIX="$(get_tmux_option "@claude-status-prefix")"
fi

python3 "$REPO_DIR/src/tmux_claude_status.py" read-pane \
  --pane-id "$PANE_ID" \
  --cache-dir "$CACHE_DIR" \
  --max-age-seconds "$MAX_AGE_SECONDS" \
  --prefix "$PREFIX"
