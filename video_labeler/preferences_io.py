"""Small user-preference store for configurable shortcuts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4


DEFAULT_HOTKEYS = {
    "play_pause": "Space",
    "previous_frame": "A",
    "next_frame": "D",
    "set_start": "S",
    "set_end": "E",
    "delete_selected": "Del",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "save_project": "Ctrl+S",
}


def default_preferences_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home()))
    return root / "VideoSegmentLabeler" / "preferences.json"


def load_hotkey_preferences(path: Path | None = None) -> dict[str, str]:
    source = Path(path) if path is not None else default_preferences_path()
    if not source.is_file():
        return dict(DEFAULT_HOTKEYS)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        return _validated_hotkeys(document["hotkeys"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return dict(DEFAULT_HOTKEYS)


def save_hotkey_preferences(path: Path, hotkeys: dict[str, str]) -> None:
    validated = _validated_hotkeys(hotkeys)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps({"version": 1, "hotkeys": validated}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _validated_hotkeys(hotkeys: object) -> dict[str, str]:
    if not isinstance(hotkeys, dict) or set(hotkeys) != set(DEFAULT_HOTKEYS):
        raise ValueError("hotkey mapping is invalid")
    values = []
    for name in DEFAULT_HOTKEYS:
        value = hotkeys[name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("hotkeys must be non-empty strings")
        values.append(value.casefold())
    if len(values) != len(set(values)):
        raise ValueError("hotkeys must not duplicate")
    return {name: hotkeys[name].strip() for name in DEFAULT_HOTKEYS}
