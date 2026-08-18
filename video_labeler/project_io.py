"""Validated persistence for multi-video label project documents."""

from __future__ import annotations

import ctypes
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from video_labeler.models import BEHAVIOR_LABELS, ClipRecord
from video_labeler.naming import normalize_label_token


PROJECT_VERSION = 1
PROJECT_SUFFIX = ".labelproj"


@dataclass
class ProjectVideo:
    id: str
    path: Path
    segments: list[ClipRecord] = field(default_factory=list)


@dataclass
class LabelProject:
    videos: list[ProjectVideo] = field(default_factory=list)
    active_video_id: str | None = None
    global_settings: dict[str, str] = field(default_factory=dict)
    custom_behavior_tags: list[str] = field(default_factory=list)


def new_project() -> LabelProject:
    return LabelProject()


def add_or_activate_video(project: LabelProject, path: Path) -> ProjectVideo:
    absolute_path = Path(path).expanduser().resolve(strict=False)
    for video in project.videos:
        if video.path == absolute_path:
            project.active_video_id = video.id
            return video

    video = ProjectVideo(id=str(uuid4()), path=absolute_path)
    project.videos.append(video)
    project.active_video_id = video.id
    return video


def project_to_dict(project: LabelProject) -> dict[str, Any]:
    videos = []
    for video in project.videos:
        _validate_video_id(video.id)
        absolute_path = Path(video.path).expanduser().resolve(strict=False)
        if not absolute_path.is_absolute():
            raise ValueError("video path must be absolute")
        videos.append(
            {
                "id": video.id,
                "path": str(absolute_path),
                "segments": [_record_to_dict(record) for record in video.segments],
            }
        )

    document = {
        "version": PROJECT_VERSION,
        "active_video_id": project.active_video_id,
        "global_settings": dict(project.global_settings),
        "custom_behavior_tags": list(project.custom_behavior_tags),
        "videos": videos,
    }
    return _validated_document(document)


def project_from_dict(document: Any) -> LabelProject:
    validated = _validated_document(document)
    videos = [
        ProjectVideo(
            id=video["id"],
            path=Path(video["path"]),
            segments=[_record_from_dict(segment) for segment in video["segments"]],
        )
        for video in validated["videos"]
    ]
    return LabelProject(
        videos=videos,
        active_video_id=validated["active_video_id"],
        global_settings=validated["global_settings"],
        custom_behavior_tags=validated["custom_behavior_tags"],
    )


def save_project(path: Path, project: LabelProject) -> Path:
    target = _project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    serialized = json.dumps(project_to_dict(project), ensure_ascii=False, indent=2)
    try:
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def load_project(path: Path) -> LabelProject:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("project JSON is invalid") from error
    return project_from_dict(document)


def create_backup(
    project_path: Path,
    project: LabelProject,
    *,
    now: datetime | None = None,
    retention: int = 10,
) -> Path:
    if retention < 1:
        raise ValueError("backup retention must be at least one")

    project_target = _project_path(project_path)
    backup_dir = project_target.parent / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    _mark_hidden_on_windows(backup_dir)

    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{project_target.stem}_{timestamp}{PROJECT_SUFFIX}"
    save_project(backup_path, project)
    _keep_newest_backups(backup_dir, project_target.stem, retention)
    return backup_path


def _project_path(path: Path) -> Path:
    selected = Path(path)
    if selected.suffix.lower() == PROJECT_SUFFIX:
        return selected
    return selected.with_suffix(PROJECT_SUFFIX)


def _record_to_dict(record: ClipRecord) -> dict[str, Any]:
    return {
        "source": record.source,
        "start_seconds": record.start_seconds,
        "end_seconds": record.end_seconds,
        "output": record.output,
        "behaviors": list(record.behaviors),
        "polarity": record.polarity,
        "lighting": record.lighting,
        "sequence": record.sequence,
        "status": record.status,
        "error": record.error,
    }


def _record_from_dict(document: dict[str, Any]) -> ClipRecord:
    return ClipRecord(
        source=document["source"],
        start_seconds=float(document["start_seconds"]),
        end_seconds=float(document["end_seconds"]),
        output=document["output"],
        behaviors=tuple(document["behaviors"]),
        polarity=document["polarity"],
        lighting=document["lighting"],
        sequence=document["sequence"],
        status=document["status"],
        error=document["error"],
    )


def _validated_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("project root must be an object")
    if not _is_int(document.get("version")) or document["version"] != PROJECT_VERSION:
        raise ValueError(f"project version must be {PROJECT_VERSION}")
    legacy_keys = {"version", "active_video_id", "global_settings", "videos"}
    current_keys = {*legacy_keys, "custom_behavior_tags"}
    if set(document) not in (legacy_keys, current_keys):
        raise ValueError("project keys are invalid")

    videos = document["videos"]
    if not isinstance(videos, list):
        raise ValueError("videos must be a list")
    if not isinstance(document["global_settings"], dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in document["global_settings"].items()
    ):
        raise ValueError("global_settings must contain string keys and values")
    custom_behavior_tags = _validated_custom_behavior_tags(
        document.get("custom_behavior_tags", [])
    )

    validated_videos = [_validated_video(video) for video in videos]
    ids = [video["id"] for video in validated_videos]
    if len(ids) != len(set(ids)):
        raise ValueError("video ids must not be duplicate")

    active_video_id = document["active_video_id"]
    if videos:
        if not isinstance(active_video_id, str) or active_video_id not in ids:
            raise ValueError("active_video_id must identify a video")
    elif active_video_id is not None:
        raise ValueError("active_video_id must be null without videos")

    return {
        "version": PROJECT_VERSION,
        "active_video_id": active_video_id,
        "global_settings": dict(document["global_settings"]),
        "custom_behavior_tags": custom_behavior_tags,
        "videos": validated_videos,
    }


def _validated_custom_behavior_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("custom behavior tags must be a list")

    normalized_tags = []
    seen = set()
    for tag in value:
        if not isinstance(tag, str):
            raise ValueError("custom behavior tags must contain strings")
        normalized = normalize_label_token(tag, "custom behavior tag")
        if normalized in BEHAVIOR_LABELS:
            raise ValueError("custom behavior tag cannot duplicate a built-in label")
        if normalized in seen:
            raise ValueError("custom behavior tags must not contain duplicates")
        seen.add(normalized)
        normalized_tags.append(normalized)
    return normalized_tags


def _validated_video(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {"id", "path", "segments"}:
        raise ValueError("video entry is invalid")
    _validate_video_id(document["id"])
    path = document["path"]
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise ValueError("video path must be absolute")
    segments = document["segments"]
    if not isinstance(segments, list):
        raise ValueError("video segments must be a list")
    return {
        "id": document["id"],
        "path": str(Path(path)),
        "segments": [_validated_record(segment) for segment in segments],
    }


def _validated_record(document: Any) -> dict[str, Any]:
    required_keys = {
        "source",
        "start_seconds",
        "end_seconds",
        "output",
        "behaviors",
        "polarity",
        "lighting",
        "sequence",
        "status",
        "error",
    }
    if not isinstance(document, dict) or set(document) != required_keys:
        raise ValueError("segment record is invalid")
    for key in ("source", "output", "polarity", "lighting", "status", "error"):
        if not isinstance(document[key], str):
            raise ValueError(f"segment {key} must be a string")
    for key in ("start_seconds", "end_seconds"):
        if not _is_number(document[key]):
            raise ValueError(f"segment {key} must be a finite number")
    if not isinstance(document["behaviors"], list) or not all(
        isinstance(behavior, str) for behavior in document["behaviors"]
    ):
        raise ValueError("segment behaviors must be a list of strings")
    if not _is_int(document["sequence"]):
        raise ValueError("segment sequence must be an integer")
    return {
        "source": document["source"],
        "start_seconds": float(document["start_seconds"]),
        "end_seconds": float(document["end_seconds"]),
        "output": document["output"],
        "behaviors": list(document["behaviors"]),
        "polarity": document["polarity"],
        "lighting": document["lighting"],
        "sequence": document["sequence"],
        "status": document["status"],
        "error": document["error"],
    }


def _validate_video_id(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("video id must be a non-empty string")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _keep_newest_backups(backup_dir: Path, project_stem: str, retention: int) -> None:
    backups = sorted(
        backup_dir.glob(f"{project_stem}_*{PROJECT_SUFFIX}"),
        key=lambda backup: backup.name,
        reverse=True,
    )
    for outdated in backups[retention:]:
        outdated.unlink()


def _mark_hidden_on_windows(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)
    except (AttributeError, OSError):
        pass
