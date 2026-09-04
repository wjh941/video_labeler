"""Version 2 project serialization with relocatable media paths.

The legacy v1 reader remains untouched; this module provides an explicit v2
format and a loss-preserving migration boundary for callers that opt in.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .project_io import LabelProject, project_from_dict, project_to_dict

PROJECT_V2_VERSION = 2
PROJECT_V2_FORMAT = "video-labeler-project"


class MigrationReport:
    """Non-destructive information produced while upgrading a v1 project."""

    def __init__(self, source_version: int, target_version: int, warnings: list[str]):
        self.source_version = source_version
        self.target_version = target_version
        self.warnings = tuple(warnings)

    @property
    def changed(self) -> bool:
        return self.source_version != self.target_version


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative_or_absolute(path: Path, project_dir: Path) -> tuple[str, str]:
    source = Path(path).expanduser().resolve(strict=False)
    base = Path(project_dir).expanduser().resolve(strict=False)
    try:
        relative = os.path.relpath(source, base)
    except ValueError:
        return str(source), "absolute"
    return Path(relative).as_posix(), "project"


def _resolve_media_path(value: str, path_base: str, project_dir: Path) -> Path:
    path = Path(value)
    if path_base == "project" and not path.is_absolute():
        return (Path(project_dir) / path).resolve(strict=False)
    return path.expanduser().resolve(strict=False)


def project_to_v2_dict(
    project: LabelProject,
    project_path: Path,
    *,
    now: str | None = None,
    relative_to: Path | None = None,
) -> dict[str, Any]:
    """Convert the in-memory project to the relocatable v2 document."""
    target = Path(project_path).expanduser().resolve(strict=False)
    base_target = Path(relative_to or target).expanduser().resolve(strict=False)
    legacy = project_to_dict(project)
    timestamp = now or _utc_now()
    videos: list[dict[str, Any]] = []
    for video, source_video in zip(legacy["videos"], project.videos):
        path, path_base = _relative_or_absolute(Path(video["path"]), base_target.parent)
        segments = []
        for index, segment in enumerate(video["segments"]):
            item = dict(segment)
            item["id"] = str(uuid5(NAMESPACE_URL, f"{video['id']}:{index}"))
            item["review_status"] = getattr(source_video.segments[index], "review_status", "pending")
            segments.append(item)
        videos.append({
            "id": video["id"],
            "path": path,
            "path_base": path_base,
            "missing": not Path(video["path"]).is_file(),
            "metadata": dict(source_video.metadata),
            "segments": segments,
        })
    settings = dict(legacy["global_settings"])
    output_dir = settings.get("output_dir")
    if output_dir:
        settings["output_dir"], settings["output_dir_base"] = _relative_or_absolute(
            Path(output_dir), base_target.parent
        )
    return {
        "format": PROJECT_V2_FORMAT,
        "version": PROJECT_V2_VERSION,
        "created_at": timestamp,
        "updated_at": timestamp,
        "settings": settings,
        "custom_behavior_tags": legacy["custom_behavior_tags"],
        "custom_behavior_tag_colors": legacy["custom_behavior_tag_colors"],
        "active_video_id": legacy["active_video_id"],
        "videos": videos,
        "extensions": {},
    }


def migrate_v1_to_v2(document: Any, project_path: Path, *, now: str | None = None) -> dict[str, Any]:
    """Validate and migrate a v1 document without mutating its input."""
    project = project_from_dict(document)
    return project_to_v2_dict(project, project_path, now=now)


def migrate_v1_to_v2_with_report(
    document: Any, project_path: Path, *, now: str | None = None
) -> tuple[dict[str, Any], MigrationReport]:
    """Migrate v1 and return explicit, non-destructive migration diagnostics."""
    migrated = migrate_v1_to_v2(document, project_path, now=now)
    warnings: list[str] = []
    for video in migrated.get("videos", []):
        if video.get("missing"):
            warnings.append(f"视频文件不存在：{video.get('path', '')}")
    return migrated, MigrationReport(1, PROJECT_V2_VERSION, warnings)


def _load_v2_settings(document: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    settings = dict(document.get("settings", {}))
    output_dir = settings.get("output_dir")
    if output_dir:
        settings["output_dir"] = str(_resolve_media_path(
            str(output_dir), str(settings.get("output_dir_base", "project")), project_dir
        ))
    settings.pop("output_dir_base", None)
    return settings


def project_from_v2_dict(document: Any, project_path: Path) -> LabelProject:
    """Read v2 while resolving media paths relative to the project file."""
    if not isinstance(document, dict) or document.get("format") != PROJECT_V2_FORMAT:
        raise ValueError("project format is invalid")
    if document.get("version") != PROJECT_V2_VERSION:
        raise ValueError(f"project version must be {PROJECT_V2_VERSION}")
    if not isinstance(document.get("videos"), list):
        raise ValueError("videos must be a list")
    videos: list[dict[str, Any]] = []
    for video in document["videos"]:
        if not isinstance(video, dict):
            raise ValueError("video entry is invalid")
        path = _resolve_media_path(str(video.get("path", "")), str(video.get("path_base", "project")), Path(project_path).parent)
        segments = []
        for segment in video.get("segments", []):
            item = dict(segment)
            item.pop("id", None)
            item.pop("review_status", None)
            segments.append(item)
        videos.append({"id": video["id"], "path": str(path), "segments": segments})
    legacy = {
        "version": 1,
        "active_video_id": document.get("active_video_id"),
        "global_settings": _load_v2_settings(document, Path(project_path).parent),
        "custom_behavior_tags": document.get("custom_behavior_tags", []),
        "custom_behavior_tag_colors": document.get("custom_behavior_tag_colors", {}),
        "videos": videos,
    }
    result = project_from_dict(legacy)
    for target_video, source_video in zip(result.videos, document["videos"]):
        target_video.metadata = dict(source_video.get("metadata", {}))
        for target_segment, source_segment in zip(target_video.segments, source_video.get("segments", [])):
            target_segment.review_status = source_segment.get("review_status", "pending")
    return result


def save_project_v2(
    path: Path,
    project: LabelProject,
    *,
    now: str | None = None,
    relative_to: Path | None = None,
) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".labelproj":
        target = target.with_suffix(".labelproj")
    target.parent.mkdir(parents=True, exist_ok=True)
    document = project_to_v2_dict(
        project, target, now=now, relative_to=relative_to
    )
    temporary = target.with_name(f".{target.name}.v2.tmp")
    try:
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def load_project_v2(path: Path) -> LabelProject:
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("project JSON is invalid") from error
    if isinstance(document, dict) and document.get("version") == 1:
        document = migrate_v1_to_v2(document, target)
    return project_from_v2_dict(document, target)
