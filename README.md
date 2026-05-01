# tmux-claude-status

Show Claude Code's status line in your tmux status bar.

This plugin uses the same Claude `statusLine` command for both places:

- Claude renders the line in its own UI
- the script also caches that line per tmux pane
- tmux reads the cache for the active pane

- <img width="741" height="38" alt="image" src="https://github.com/user-attachments/assets/529504db-6b6e-4630-bac8-ee00c8d754ad" />

## Requirements

- `tmux 3.1+`
- [TPM](https://github.com/tmux-plugins/tpm)
- Python 3
- Claude Code with `statusLine` support

Tested locally with `tmux 3.5a`.

## Install

Add the plugin after your theme in `~/.config/tmux/tmux.conf`:

```tmux
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'janoamaral/tokyo-night-tmux'
set -g @plugin 'pchevilley/tmux-claude-status'
```

Reload tmux, then install with TPM:

```sh
tmux source-file ~/.config/tmux/tmux.conf
```

Press `prefix + I`.

## Claude config

Add this to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.config/tmux/plugins/tmux-claude-status/scripts/claude_statusline.py",
    "padding": 0
  },
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.config/tmux/plugins/tmux-claude-status/scripts/claude_session_end.py"
          }
        ]
      }
    ]
  }
}
```

Use your real plugin install path in both script entries.

Common locations:

- `~/.config/tmux/plugins/tmux-claude-status`
- `~/.tmux/plugins/tmux-claude-status`

If you use Claude's `/statusline` command, keep `statusLine.command` pointing at this plugin script.
The plugin will automatically pick up `~/.claude/statusline-command.sh`, mirror its output into tmux, and still keep the tmux cache in sync.

## tmux options

```tmux
set -g @claude-status-position 'right'
set -g @claude-status-prefix ' | '
set -g @claude-status-max-age-seconds '0'
```

Available options:

- `@claude-status-position`
  Values: `right`, `left`, `manual`
  Default: `right`

- `@claude-status-prefix`
  Default: ` | `

- `@claude-status-cache-dir`
  Default: `${XDG_STATE_HOME:-$HOME/.local/state}/tmux-claude-status`

- `@claude-status-max-age-seconds`
  Default: `0`
  Use `0` to keep the status visible until `SessionEnd` clears it

## Themes

By default the plugin appends itself to the current `status-right` instead of replacing it. That makes it work well with themes like `tokyo-night-tmux`.

If a theme still rewrites the status bar after this plugin loads, switch to manual mode:

```tmux
set -g @claude-status-position 'manual'
set -g status-right '#{status-right}#{E:@claude_status_segment}'
```

You can also place it on the left:

```tmux
set -g status-left '#{status-left}#{E:@claude_status_segment}'
```

## Troubleshooting

If Claude shows the status line but tmux does not:

- make sure Claude is running inside tmux
- make sure the Claude script paths in `~/.claude/settings.json` are correct
- make sure the plugin is loaded after your theme

If stale status sticks around:

- confirm the `SessionEnd` hook is installed
- if you want time-based expiry instead, set `@claude-status-max-age-seconds` to a positive number

If your theme fights the plugin:

- use `@claude-status-position 'manual'`
- place `#{E:@claude_status_segment}` exactly where you want it

## How it works

- `scripts/claude_statusline.py` reads Claude's status payload from stdin
- by default it renders a full fallback line with project, branch, cost, context, usage, and duration
- when Claude is inside tmux, that line is cached for the current pane
- `scripts/tmux_reader.sh` reads the cache for the active pane
- `scripts/claude_session_end.py` removes the cache when Claude exits
