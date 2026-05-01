#!/usr/bin/env bash

set -eu

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
. "$CURRENT_DIR/scripts/helpers.sh"

PUBLIC_SEGMENT="#($CURRENT_DIR/scripts/tmux_reader.sh \"#{pane_id}\" --with-prefix)"
AUTO_SEGMENT="#($CURRENT_DIR/scripts/tmux_reader.sh \"#{pane_id}\" --with-prefix)"
AUTO_SEGMENT_BARE="#($CURRENT_DIR/scripts/tmux_reader.sh \"#{pane_id}\")"

set_default_option() {
  local option="$1"
  local default_value="$2"
  local current_value
  current_value="$(get_tmux_option "$option")"

  if [ -z "$current_value" ]; then
    tmux_cmd set-option -gq "$option" "$default_value"
  fi
}

remove_auto_segment_refs() {
  local option="$1"
  local current_value
  current_value="$(get_tmux_option "$option")"

  current_value="${current_value//\#\{E:@claude_status_auto_segment\}/}"
  current_value="${current_value//\#\{E:@claude_status_auto_segment_bare\}/}"
  current_value="${current_value//\#\{E:@claude-status-auto-segment\}/}"
  current_value="${current_value//\#\{E:@claude-status-auto-segment-bare\}/}"
  current_value="${current_value//\#\{@claude_status_auto_segment\}/}"
  current_value="${current_value//\#\{@claude_status_auto_segment_bare\}/}"
  current_value="${current_value//\#\{@claude-status-auto-segment\}/}"
  current_value="${current_value//\#\{@claude-status-auto-segment-bare\}/}"

  tmux_cmd set-option -gq "$option" "$current_value"
}

contains_any_segment_ref() {
  local value="$1"

  printf '%s' "$value" | grep -Fq '#{E:@claude_status_segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{E:@claude-status-segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{E:@claude_status_auto_segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{E:@claude-status-auto-segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{E:@claude_status_auto_segment_bare}' && return 0
  printf '%s' "$value" | grep -Fq '#{E:@claude-status-auto-segment-bare}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude_status_segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude-status-segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude_status_auto_segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude-status-auto-segment}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude_status_auto_segment_bare}' && return 0
  printf '%s' "$value" | grep -Fq '#{@claude-status-auto-segment-bare}' && return 0
  return 1
}

status_has_manual_segment() {
  local right_value left_value
  right_value="$(get_tmux_option "status-right")"
  left_value="$(get_tmux_option "status-left")"

  contains_any_segment_ref "$right_value" || contains_any_segment_ref "$left_value"
}

append_auto_segment() {
  local option="$1"
  local current_value append_value
  current_value="$(get_tmux_option "$option")"

  if [ -n "$current_value" ]; then
    append_value='#{E:@claude_status_auto_segment}'
  else
    append_value='#{E:@claude_status_auto_segment_bare}'
  fi

  tmux_cmd set-option -gq "$option" "${current_value}${append_value}"
}

configure_options() {
  set_default_option "@claude-status-position" "right"
  set_default_option "@claude-status-prefix" " | "
  set_default_option "@claude-status-cache-dir" "$(default_cache_dir)"
  set_default_option "@claude-status-max-age-seconds" "0"

  tmux_cmd set-option -gq "@claude-status-segment" "$PUBLIC_SEGMENT"
  tmux_cmd set-option -gq "@claude_status_segment" "$PUBLIC_SEGMENT"
  tmux_cmd set-option -gq "@claude-status-auto-segment" "$AUTO_SEGMENT"
  tmux_cmd set-option -gq "@claude_status_auto_segment" "$AUTO_SEGMENT"
  tmux_cmd set-option -gq "@claude-status-auto-segment-bare" "$AUTO_SEGMENT_BARE"
  tmux_cmd set-option -gq "@claude_status_auto_segment_bare" "$AUTO_SEGMENT_BARE"
}

apply_position() {
  local position
  position="$(get_tmux_option "@claude-status-position")"

  remove_auto_segment_refs "status-right"
  remove_auto_segment_refs "status-left"

  if status_has_manual_segment; then
    return 0
  fi

  case "$position" in
    manual)
      return 0
      ;;
    left)
      append_auto_segment "status-left"
      ;;
    right|"")
      append_auto_segment "status-right"
      ;;
    *)
      append_auto_segment "status-right"
      ;;
  esac
}

configure_options
apply_position
