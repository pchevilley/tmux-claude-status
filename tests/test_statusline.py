from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "claude_statusline.py"
SRC_DIR = REPO_DIR / "src"

sys.path.insert(0, str(SRC_DIR))

from tmux_claude_status import build_status_line


class StatuslineTests(unittest.TestCase):
    def test_build_status_line_includes_branch_cost_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "demo-project"
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(repo_dir)],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = {
                "model": {"display_name": "Opus 4.7 (1M context)"},
                "workspace": {
                    "project_dir": str(repo_dir),
                    "current_dir": str(repo_dir),
                },
                "context_window": {"used_percentage": 12},
                "cost": {
                    "total_cost_usd": 0.12,
                    "total_duration_ms": 65_000,
                },
            }

            self.assertEqual(
                build_status_line(payload),
                "[Opus 4.7] demo-project | main | $0.12 | 1M ctx | 12% | 1m 5s",
            )

    def test_build_status_line_omits_empty_fields(self) -> None:
        payload = {
            "model": {"display_name": "Sonnet"},
            "workspace": {"project_dir": "/tmp/example"},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }

        self.assertEqual(build_status_line(payload), "[Sonnet] example | $0.00")

    def test_statusline_script_writes_cache_when_tmux_pane_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "state"
            repo_dir = Path(temp_dir) / "project"
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(repo_dir)],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = {
                "session_id": "session-123",
                "model": {"display_name": "Opus"},
                "workspace": {
                    "project_dir": str(repo_dir),
                    "current_dir": str(repo_dir),
                },
                "cost": {
                    "total_cost_usd": 0.23,
                    "total_duration_ms": 30_000,
                },
            }

            env = os.environ.copy()
            env["TMUX_PANE"] = "%42"
            env["XDG_STATE_HOME"] = str(cache_root)
            env["TMUX_CLAUDE_STATUS_DISABLE_PASSTHROUGH"] = "1"

            result = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.stdout, "[Opus] project | main | $0.23 | 30s")

            pane_path = cache_root / "tmux-claude-status" / "panes" / "%42.txt"
            session_path = cache_root / "tmux-claude-status" / "sessions" / "session-123.json"
            self.assertTrue(pane_path.exists())
            self.assertTrue(session_path.exists())
            self.assertEqual(pane_path.read_text(encoding="utf-8"), result.stdout)

    def test_statusline_script_still_prints_without_tmux(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "state"
            payload = {
                "model": {"display_name": "Haiku"},
                "workspace": {"project_dir": "/tmp/hello"},
                "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
            }

            env = os.environ.copy()
            env["XDG_STATE_HOME"] = str(cache_root)
            env.pop("TMUX_PANE", None)
            env["TMUX_CLAUDE_STATUS_DISABLE_PASSTHROUGH"] = "1"

            result = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.stdout, "[Haiku] hello | $0.00")
            panes_dir = cache_root / "tmux-claude-status" / "panes"
            self.assertFalse(panes_dir.exists())

    def test_statusline_script_uses_claude_generated_script_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            claude_dir = home_dir / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            passthrough_script = claude_dir / "statusline-command.sh"
            passthrough_script.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '\\033[1;36mproj\\033[0m  \\033[2mOpus\\033[0m'\n",
                encoding="utf-8",
            )

            cache_root = Path(temp_dir) / "state"
            payload = {
                "session_id": "session-ansi",
                "cwd": "/tmp/project",
                "model": {"display_name": "Fallback"},
                "context_window": {"used_percentage": 12},
            }

            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["XDG_STATE_HOME"] = str(cache_root)
            env["TMUX_PANE"] = "%5"

            result = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.stdout, "\x1b[1;36mproj\x1b[0m  \x1b[2mOpus\x1b[0m")
            pane_path = cache_root / "tmux-claude-status" / "panes" / "%5.txt"
            self.assertEqual(
                pane_path.read_text(encoding="utf-8"),
                "#[bold,fg=cyan]proj#[default]  #[dim]Opus#[default]",
            )

    def test_statusline_script_normalizes_literal_ansi_sequences_from_passthrough(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            claude_dir = home_dir / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            passthrough_script = claude_dir / "statusline-command.sh"
            passthrough_script.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "dir='\\\\033[1;36mproj\\\\033[0m'\n"
                "model='\\\\033[2mOpus\\\\033[0m'\n"
                "printf '%s  %s' \"$dir\" \"$model\"\n",
                encoding="utf-8",
            )

            cache_root = Path(temp_dir) / "state"
            payload = {
                "session_id": "session-literal-ansi",
                "cwd": "/tmp/project",
                "model": {"display_name": "Fallback"},
            }

            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["XDG_STATE_HOME"] = str(cache_root)
            env["TMUX_PANE"] = "%6"

            result = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.stdout, "\x1b[1;36mproj\x1b[0m  \x1b[2mOpus\x1b[0m")
            pane_path = cache_root / "tmux-claude-status" / "panes" / "%6.txt"
            self.assertEqual(
                pane_path.read_text(encoding="utf-8"),
                "#[bold,fg=cyan]proj#[default]  #[dim]Opus#[default]",
            )


if __name__ == "__main__":
    unittest.main()
