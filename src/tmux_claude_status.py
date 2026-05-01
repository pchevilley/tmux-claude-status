#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


DEFAULT_CACHE_ROOT = "tmux-claude-status"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[([0-9;]*)m")


def default_cache_dir() -> Path:
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / DEFAULT_CACHE_ROOT
    return Path.home() / ".local" / "state" / DEFAULT_CACHE_ROOT


def pane_cache_path(cache_dir: Path, pane_id: str) -> Path:
    return cache_dir / "panes" / f"{pane_id}.txt"


def session_cache_path(cache_dir: Path, session_id: str) -> Path:
    return cache_dir / "sessions" / f"{session_id}.json"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def basename(path_value: str | None) -> str:
    if not path_value:
        return ""
    normalized = path_value.rstrip("/")
    if not normalized:
        return path_value
    return Path(normalized).name or normalized


def detect_git_branch(directory: str | None) -> str:
    if not directory:
        return ""

    try:
        result = subprocess.run(
            ["git", "-C", directory, "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=0.5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def format_cost(cost_value: Any) -> str:
    if cost_value in (None, ""):
        return ""

    try:
        cost = float(cost_value)
    except (TypeError, ValueError):
        return ""

    if cost <= 0:
        return ""
    if cost < 0.01:
        return "<$0.01"
    return f"${cost:.2f}"


def format_duration(duration_ms: Any) -> str:
    if duration_ms in (None, ""):
        return ""

    try:
        total_seconds = max(0, int(round(float(duration_ms) / 1000)))
    except (TypeError, ValueError):
        return ""

    if total_seconds == 0:
        return ""

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []

    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not hours:
        parts.append(f"{seconds}s")

    if hours and not minutes and not seconds:
        return parts[0]
    return " ".join(parts)


def build_status_line(payload: dict[str, Any]) -> str:
    model = payload.get("model", {}) if isinstance(payload.get("model"), dict) else {}
    workspace = payload.get("workspace", {}) if isinstance(payload.get("workspace"), dict) else {}
    cost = payload.get("cost", {}) if isinstance(payload.get("cost"), dict) else {}

    model_name = str(model.get("display_name") or model.get("id") or "Claude")
    project_dir = (
        workspace.get("project_dir")
        or workspace.get("current_dir")
        or payload.get("cwd")
        or ""
    )
    project_name = basename(str(project_dir)) if project_dir else ""
    branch = detect_git_branch(str(project_dir) if project_dir else None)

    head = f"[{model_name}]"
    if project_name:
        head = f"{head} {project_name}"

    segments = [head]
    if branch:
        segments.append(branch)

    formatted_cost = format_cost(cost.get("total_cost_usd"))
    if formatted_cost:
        segments.append(formatted_cost)

    formatted_duration = format_duration(cost.get("total_duration_ms"))
    if formatted_duration:
        segments.append(formatted_duration)

    return " | ".join(segment for segment in segments if segment)


def sgr_state_to_tmux(state: dict[str, Any]) -> str:
    parts: list[str] = []
    if state.get("bold"):
        parts.append("bold")
    if state.get("dim"):
        parts.append("dim")
    if state.get("italic"):
        parts.append("italics")
    if state.get("underscore"):
        parts.append("underscore")
    fg = state.get("fg")
    if fg:
        parts.append(f"fg={fg}")

    if not parts:
        return "#[default]"
    return "#[" + ",".join(parts) + "]"


def ansi_code_to_color(code: int) -> str | None:
    mapping = {
        30: "black",
        31: "red",
        32: "green",
        33: "yellow",
        34: "blue",
        35: "magenta",
        36: "cyan",
        37: "white",
        90: "brightblack",
        91: "brightred",
        92: "brightgreen",
        93: "brightyellow",
        94: "brightblue",
        95: "brightmagenta",
        96: "brightcyan",
        97: "brightwhite",
    }
    return mapping.get(code)


def ansi_to_tmux_styles(text: str) -> str:
    state = {
        "bold": False,
        "dim": False,
        "italic": False,
        "underscore": False,
        "fg": None,
    }
    result: list[str] = []
    cursor = 0

    for match in ANSI_ESCAPE_RE.finditer(text):
        result.append(text[cursor:match.start()])
        cursor = match.end()

        code_string = match.group(1)
        codes = [0] if code_string == "" else [int(part) for part in code_string.split(";") if part]

        for code in codes:
            if code == 0:
                state = {
                    "bold": False,
                    "dim": False,
                    "italic": False,
                    "underscore": False,
                    "fg": None,
                }
            elif code == 1:
                state["bold"] = True
            elif code == 2:
                state["dim"] = True
            elif code == 3:
                state["italic"] = True
            elif code == 4:
                state["underscore"] = True
            elif code == 22:
                state["bold"] = False
                state["dim"] = False
            elif code == 23:
                state["italic"] = False
            elif code == 24:
                state["underscore"] = False
            elif code == 39:
                state["fg"] = None
            else:
                color = ansi_code_to_color(code)
                if color:
                    state["fg"] = color

        result.append(sgr_state_to_tmux(state))

    result.append(text[cursor:])
    converted = "".join(result)

    if "#[" not in converted:
        return converted

    if not converted.endswith("#[default]"):
        converted += "#[default]"
    return converted


def normalize_ansi_sequences(text: str) -> str:
    normalized = re.sub(r"\\+033\[", "\x1b[", text)
    normalized = re.sub(r"\\+e\[", "\x1b[", normalized)
    normalized = re.sub(r"\\+x1b\[", "\x1b[", normalized)
    return normalized


def default_passthrough_script() -> Path:
    return Path.home() / ".claude" / "statusline-command.sh"


def select_passthrough_script() -> Path | None:
    if os.environ.get("TMUX_CLAUDE_STATUS_DISABLE_PASSTHROUGH") == "1":
        return None

    script = default_passthrough_script()
    if not script.exists():
        return None

    current_script = Path(__file__).resolve()
    if script.resolve() == current_script:
        return None

    return script


def render_via_passthrough(raw_payload: str) -> str | None:
    script = select_passthrough_script()
    if script is None:
        return None

    try:
        result = subprocess.run(
            ["sh", str(script)],
            input=raw_payload,
            capture_output=True,
            check=False,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    output_lines = result.stdout.splitlines()
    if not output_lines:
        return ""
    return normalize_ansi_sequences(output_lines[0])


def write_status_cache(
    payload: dict[str, Any],
    rendered_line: str,
    cache_dir: Path,
    pane_id: str | None,
) -> None:
    if not pane_id:
        return

    atomic_write_text(pane_cache_path(cache_dir, pane_id), rendered_line)

    session_id = payload.get("session_id")
    if session_id:
        atomic_write_text(
            session_cache_path(cache_dir, str(session_id)),
            json.dumps({"pane_id": pane_id}),
        )


def resolve_session_pane_id(
    payload: dict[str, Any],
    cache_dir: Path,
    pane_id: str | None = None,
) -> str | None:
    if pane_id:
        return pane_id

    session_id = payload.get("session_id")
    if not session_id:
        return None

    mapping_path = session_cache_path(cache_dir, str(session_id))
    if not mapping_path.exists():
        return None

    try:
        session_data = load_json(mapping_path)
    except (OSError, json.JSONDecodeError):
        return None

    resolved = session_data.get("pane_id")
    return str(resolved) if resolved else None


def cleanup_session_cache(
    payload: dict[str, Any],
    cache_dir: Path,
    pane_id: str | None,
) -> None:
    session_id = str(payload.get("session_id") or "")
    resolved_pane_id = resolve_session_pane_id(payload, cache_dir, pane_id)

    if resolved_pane_id:
        pane_path = pane_cache_path(cache_dir, resolved_pane_id)
        try:
            pane_path.unlink()
        except FileNotFoundError:
            pass

    if session_id:
        mapping_path = session_cache_path(cache_dir, session_id)
        try:
            mapping_path.unlink()
        except FileNotFoundError:
            pass


def read_pane_status(
    pane_id: str,
    cache_dir: Path,
    max_age_seconds: int,
    prefix: str = "",
) -> str:
    if not pane_id:
        return ""

    cache_path = pane_cache_path(cache_dir, pane_id)
    if not cache_path.exists():
        return ""

    try:
        age_seconds = time.time() - cache_path.stat().st_mtime
    except OSError:
        return ""

    if age_seconds > max_age_seconds:
        return ""

    try:
        cached_text = cache_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    rendered_line = cached_text.splitlines()[0].strip() if cached_text else ""
    if not rendered_line:
        return ""

    return f"{prefix}{rendered_line}" if prefix else rendered_line


def tmux_command_prefix() -> list[str]:
    socket_name = os.environ.get("TMUX_SOCKET_NAME")
    if socket_name:
        return ["tmux", "-L", socket_name]
    return ["tmux"]


def refresh_tmux() -> None:
    if not os.environ.get("TMUX") and not os.environ.get("TMUX_SOCKET_NAME"):
        return

    try:
        subprocess.run(
            [*tmux_command_prefix(), "refresh-client", "-S"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=0.25,
        )
    except (OSError, subprocess.SubprocessError):
        return


def parse_statusline_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=str(default_cache_dir()))
    return parser.parse_args(argv)


def parse_session_end_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=str(default_cache_dir()))
    return parser.parse_args(argv)


def parse_read_pane_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pane-id", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--max-age-seconds", required=True, type=int)
    parser.add_argument("--prefix", default="")
    return parser.parse_args(argv)


def main_statusline(argv: list[str] | None = None) -> int:
    args = parse_statusline_args(argv)
    raw_payload = sys.stdin.read()
    payload = json.loads(raw_payload)
    cache_dir = Path(args.cache_dir)
    passthrough_line = render_via_passthrough(raw_payload)
    rendered_line = passthrough_line if passthrough_line is not None else build_status_line(payload)
    tmux_line = ansi_to_tmux_styles(rendered_line)
    write_status_cache(payload, tmux_line, cache_dir, os.environ.get("TMUX_PANE"))
    sys.stdout.write(rendered_line)
    refresh_tmux()
    return 0


def main_session_end(argv: list[str] | None = None) -> int:
    args = parse_session_end_args(argv)
    payload = json.load(sys.stdin)
    cleanup_session_cache(payload, Path(args.cache_dir), os.environ.get("TMUX_PANE"))
    refresh_tmux()
    return 0


def main_read_pane(argv: list[str] | None = None) -> int:
    args = parse_read_pane_args(argv)
    rendered = read_pane_status(
        pane_id=args.pane_id,
        cache_dir=Path(args.cache_dir),
        max_age_seconds=args.max_age_seconds,
        prefix=args.prefix,
    )
    sys.stdout.write(rendered)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("statusline")
    subparsers.add_parser("session-end")
    subparsers.add_parser("read-pane")

    parsed, remaining = parser.parse_known_args(argv)

    if parsed.command == "statusline":
        return main_statusline(remaining)
    if parsed.command == "session-end":
        return main_session_end(remaining)
    if parsed.command == "read-pane":
        return main_read_pane(remaining)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
