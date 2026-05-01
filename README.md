# tmux-claude-status

Show Claude Code's status line in your tmux status bar.

This plugin uses the same Claude `statusLine` command for both places:

- Claude renders the line in its own UI
- the script also caches that line per tmux pane
- tmux reads the cache for the active pane

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
    "command": "~/.tmux/plugins/tmux-claude-status/scripts/claude_statusline.py",
    "padding": 0
  },
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.tmux/plugins/tmux-claude-status/scripts/claude_session_end.py"
          }
        ]
      }
    ]
  }
}
```

If you installed the plugin somewhere other than `~/.tmux/plugins/tmux-claude-status`, update both script paths.

## tmux options

```tmux
set -g @claude-status-position 'right'
set -g @claude-status-prefix ' | '
set -g @claude-status-max-age-seconds '15'
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
  Default: `15`

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
- otherwise it will disappear after `@claude-status-max-age-seconds`

If your theme fights the plugin:

- use `@claude-status-position 'manual'`
- place `#{E:@claude_status_segment}` exactly where you want it

## How it works

- `scripts/claude_statusline.py` reads Claude's status payload from stdin
- it renders a compact line like `[Opus] project | main | $0.12 | 1m 5s`
- when Claude is inside tmux, that line is cached for the current pane
- `scripts/tmux_reader.sh` reads the cache for the active pane
- `scripts/claude_session_end.py` removes the cache when Claude exits
