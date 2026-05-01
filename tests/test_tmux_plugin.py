from __future__ import annotations

import subprocess
import unittest
import uuid
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
PLUGIN = REPO_DIR / "claude-status.tmux"


class TmuxPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.socket_name = f"tmux-claude-status-plugin-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["tmux", "-L", self.socket_name, "new-session", "-d", "-s", "test"],
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

    def show(self, option: str) -> str:
        return self.tmux("show-option", "-gqv", option).stdout.strip()

    def run_plugin(self) -> None:
        self.tmux("run-shell", str(PLUGIN))

    def test_plugin_appends_to_existing_status_right_without_duplicate(self) -> None:
        self.tmux("set-option", "-gq", "status-right", "THEME")
        self.tmux("set-option", "-gq", "status-left", "LEFT")

        self.run_plugin()
        first_value = self.show("status-right")
        self.assertEqual(first_value, "THEME#{@claude_status_auto_segment}")

        self.run_plugin()
        second_value = self.show("status-right")
        self.assertEqual(second_value, "THEME#{@claude_status_auto_segment}")

    def test_manual_mode_leaves_status_options_untouched(self) -> None:
        self.tmux("set-option", "-gq", "@claude-status-position", "manual")
        self.tmux("set-option", "-gq", "status-right", "THEME")
        self.tmux("set-option", "-gq", "status-left", "LEFT")

        self.run_plugin()

        self.assertEqual(self.show("status-right"), "THEME")
        self.assertEqual(self.show("status-left"), "LEFT")
        self.assertEqual(
            self.show("@claude-status-segment"),
            f'#({REPO_DIR / "scripts" / "tmux_reader.sh"} "#{{pane_id}}" --with-prefix)',
        )

    def test_left_mode_appends_to_status_left(self) -> None:
        self.tmux("set-option", "-gq", "@claude-status-position", "left")
        self.tmux("set-option", "-gq", "status-right", "THEME")
        self.tmux("set-option", "-gq", "status-left", "LEFT")

        self.run_plugin()

        self.assertEqual(self.show("status-left"), "LEFT#{@claude_status_auto_segment}")
        self.assertEqual(self.show("status-right"), "THEME")


if __name__ == "__main__":
    unittest.main()
