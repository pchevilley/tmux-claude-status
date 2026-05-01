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
                "model": {"display_name": "Opus"},
                "workspace": {
                    "project_dir": str(repo_dir),
                    "current_dir": str(repo_dir),
                },
                "cost": {
                    "total_cost_usd": 0.12,
                    "total_duration_ms": 65_000,
                },
            }

            self.assertEqual(
                build_status_line(payload),
                "[Opus] demo-project | main | $0.12 | 1m 5s",
            )

    def test_build_status_line_omits_empty_fields(self) -> None:
        payload = {
            "model": {"display_name": "Sonnet"},
            "workspace": {"project_dir": "/tmp/example"},
            "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        }

        self.assertEqual(build_status_line(payload), "[Sonnet] example")

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

            result = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps(payload),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.stdout, "[Haiku] hello")
            panes_dir = cache_root / "tmux-claude-status" / "panes"
            self.assertFalse(panes_dir.exists())


if __name__ == "__main__":
    unittest.main()
