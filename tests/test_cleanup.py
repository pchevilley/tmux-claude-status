from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "claude_session_end.py"


class CleanupTests(unittest.TestCase):
    def test_session_end_removes_cached_pane_via_session_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "state"
            cache_dir = cache_root / "tmux-claude-status"
            pane_path = cache_dir / "panes" / "%99.txt"
            session_path = cache_dir / "sessions" / "session-abc.json"

            pane_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            pane_path.write_text("cached status", encoding="utf-8")
            session_path.write_text(json.dumps({"pane_id": "%99"}), encoding="utf-8")

            env = os.environ.copy()
            env["XDG_STATE_HOME"] = str(cache_root)
            env.pop("TMUX_PANE", None)

            subprocess.run(
                [str(SCRIPT)],
                input=json.dumps({"session_id": "session-abc"}),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertFalse(pane_path.exists())
            self.assertFalse(session_path.exists())

    def test_session_end_uses_tmux_pane_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "state"
            pane_path = cache_root / "tmux-claude-status" / "panes" / "%7.txt"
            pane_path.parent.mkdir(parents=True, exist_ok=True)
            pane_path.write_text("cached status", encoding="utf-8")

            env = os.environ.copy()
            env["XDG_STATE_HOME"] = str(cache_root)
            env["TMUX_PANE"] = "%7"

            subprocess.run(
                [str(SCRIPT)],
                input=json.dumps({"session_id": "no-map"}),
                capture_output=True,
                check=True,
                text=True,
                env=env,
            )

            self.assertFalse(pane_path.exists())


if __name__ == "__main__":
    unittest.main()
