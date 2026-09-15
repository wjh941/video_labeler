"""Persist the last working session so a new run can offer to restore it.

The session snapshot records the project file, the active video and the
playhead so annotators returning to a multi-hour video can continue where
they left off. Writes are atomic; readers never raise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

SESSION_VERSION = 1


def session_path() -> Path:
    root = Path(os.environ.get("APPDATA", str(Path.home())))
    return root / "VideoSegmentLabeler" / "session.json"


def save_session(
    *,
    project_path: Path | str | None,
    video_path: Path | str | None,
    position_ms: int,
    autosave: bool = False,
) -> None:
    document = {
        "version": SESSION_VERSION,
        "project_path": str(project_path) if project_path else None,
        "video_path": str(video_path) if video_path else None,
        "position_ms": max(0, int(position_ms or 0)),
        "autosave": bool(autosave),
    }
    target = session_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def load_session() -> dict:
    source = session_path()
    if not source.is_file():
        return {}
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict) or document.get("version") != SESSION_VERSION:
        return {}
    return {
        "version": SESSION_VERSION,
        "project_path": document.get("project_path") or None,
        "video_path": document.get("video_path") or None,
        "position_ms": max(0, int(document.get("position_ms") or 0)),
        "autosave": bool(document.get("autosave", False)),
    }


def clear_session() -> None:
    session_path().unlink(missing_ok=True)
