from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT = REPO_DIR / "scripts" / "tmux_reader.sh"


class ReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.socket_name = f"tmux-claude-status-reader-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["tmux", "-L", self.socket_name, "new-session", "-d", "-s", "reader"],
            check=True,
            capture_output=True,
            text=True,
        )

    def tearDown(self) -> None:
        subprocess.run(
            ["tmux", "-L", self.socket_name, "kill-server"],
            check=False,
            capture_output=True,
            text=True,
        )

    def tmux(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", "-L", self.socket_name, *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def run_reader(self, pane_id: str, with_prefix: bool) -> str:
        env = os.environ.copy()
        env["TMUX_SOCKET_NAME"] = self.socket_name
        args = [str(SCRIPT), pane_id]
        if with_prefix:
            args.append("--with-prefix")

        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return result.stdout

    def test_reader_returns_fresh_cached_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            pane_path = cache_dir / "panes" / "%1.txt"
            pane_path.parent.mkdir(parents=True, exist_ok=True)
            pane_path.write_text("hello", encoding="utf-8")

            self.tmux("set-option", "-gq", "@claude-status-cache-dir", str(cache_dir))
            self.tmux("set-option", "-gq", "@claude-status-max-age-seconds", "15")
            self.tmux("set-option", "-gq", "@claude-status-prefix", " | ")

            self.assertEqual(self.run_reader("%1", with_prefix=False), "hello")
            self.assertEqual(self.run_reader("%1", with_prefix=True), " | hello")

    def test_reader_suppresses_stale_and_missing_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            pane_path = cache_dir / "panes" / "%2.txt"
            pane_path.parent.mkdir(parents=True, exist_ok=True)
            pane_path.write_text("stale", encoding="utf-8")
            stale_time = time.time() - 60
            os.utime(pane_path, (stale_time, stale_time))

            self.tmux("set-option", "-gq", "@claude-status-cache-dir", str(cache_dir))
            self.tmux("set-option", "-gq", "@claude-status-max-age-seconds", "5")
            self.tmux("set-option", "-gq", "@claude-status-prefix", " | ")

            self.assertEqual(self.run_reader("%2", with_prefix=True), "")
            self.assertEqual(self.run_reader("%404", with_prefix=True), "")


if __name__ == "__main__":
    unittest.main()
