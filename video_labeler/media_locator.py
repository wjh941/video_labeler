"""Safe helpers for relocating missing project media."""

from __future__ import annotations

from pathlib import Path


def find_media_candidate(missing_path: Path, search_root: Path) -> Path | None:
    """Find a unique filename match below a directory, or return None."""
    name = missing_path.name.casefold()
    candidates = [
        path for path in Path(search_root).rglob("*")
        if path.is_file() and path.name.casefold() == name
    ]
    if len(candidates) == 1:
        return candidates[0].resolve()
    return None


def relocate_media_paths(paths: list[Path], search_root: Path) -> dict[Path, Path]:
    """Resolve missing paths only when every filename match is unambiguous."""
    result: dict[Path, Path] = {}
    for path in paths:
        if path.is_file():
            continue
        candidate = find_media_candidate(path, search_root)
        if candidate is not None:
            result[path] = candidate
    return result
