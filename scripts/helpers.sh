#!/usr/bin/env bash

set -eu

tmux_cmd() {
  if [ -n "${TMUX_SOCKET_NAME:-}" ]; then
    tmux -L "$TMUX_SOCKET_NAME" "$@"
  else
    tmux "$@"
  fi
}

get_tmux_option() {
  local option="$1"
  tmux_cmd show-option -gqv "$option"
}

default_cache_dir() {
  if [ -n "${XDG_STATE_HOME:-}" ]; then
    printf '%s/tmux-claude-status' "$XDG_STATE_HOME"
  else
    printf '%s/.local/state/tmux-claude-status' "$HOME"
  fi
}
