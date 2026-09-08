"""Validated persistence for multi-video label project documents."""

from __future__ import annotations

import ctypes
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from video_labeler.models import BEHAVIOR_LABELS, ClipRecord, EventRecord
from video_labeler.naming import normalize_label_token


PROJECT_VERSION = 1
PROJECT_SUFFIX = ".labelproj"
TAG_PRESET_VERSION = 1
TAG_PRESET_SUFFIX = ".tagpreset.json"
EXPORT_QUEUE_VERSION = 1


@dataclass
class ProjectVideo:
    id: str
    path: Path
    segments: list[ClipRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LabelProject:
    videos: list[ProjectVideo] = field(default_factory=list)
    active_video_id: str | None = None
    global_settings: dict[str, str] = field(default_factory=dict)
    custom_behavior_tags: list[str] = field(default_factory=list)
    custom_behavior_tag_colors: dict[str, str] = field(default_factory=dict)


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
        "custom_behavior_tag_colors": dict(project.custom_behavior_tag_colors),
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
        custom_behavior_tag_colors=validated["custom_behavior_tag_colors"],
    )


def save_project(path: Path, project: LabelProject) -> Path:
    target = _project_path(path)
    _write_json_atomic(target, project_to_dict(project))
    return target


def load_project(path: Path) -> LabelProject:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("project JSON is invalid") from error
    if isinstance(document, dict) and document.get("version") == 2:
        from .project_v2 import project_from_v2_dict
        if document.get("format") != "video-labeler-project":
            raise ValueError("project version or format is invalid")
        return project_from_v2_dict(document, source)
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
    from .project_v2 import save_project_v2
    save_project_v2(backup_path, project, relative_to=project_target)
    _keep_newest_backups(backup_dir, project_target.stem, retention)
    return backup_path


def create_version_snapshot(
    project_path: Path,
    project: LabelProject,
    *,
    now: datetime | None = None,
) -> Path:
    target = _project_path(project_path)
    versions_dir = target.parent / ".versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    _mark_hidden_on_windows(versions_dir)
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    snapshot = versions_dir / f"{target.stem}_{timestamp}{PROJECT_SUFFIX}"
    while snapshot.exists():
        snapshot = snapshot.with_name(f"{snapshot.stem}_{uuid4().hex[:8]}{PROJECT_SUFFIX}")
    from .project_v2 import save_project_v2
    save_project_v2(snapshot, project, relative_to=target)
    return snapshot


def list_version_snapshots(project_path: Path) -> list[Path]:
    target = _project_path(project_path)
    versions_dir = target.parent / ".versions"
    if not versions_dir.is_dir():
        return []
    return sorted(
        versions_dir.glob(f"{target.stem}_*{PROJECT_SUFFIX}"),
        key=lambda snapshot: snapshot.name,
        reverse=True,
    )


def restore_version_snapshot(project_path: Path, snapshot_path: Path) -> LabelProject:
    target = _project_path(project_path)
    expected_dir = (target.parent / ".versions").resolve()
    snapshot = Path(snapshot_path).resolve()
    if snapshot.parent != expected_dir or not snapshot.name.startswith(
        f"{target.stem}_"
    ):
        raise ValueError("version snapshot does not belong to this project")
    from .project_v2 import project_from_v2_dict, save_project_v2
    try:
        snapshot_document = json.loads(snapshot.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("snapshot JSON is invalid") from error
    if snapshot_document.get("version") == 2:
        project = project_from_v2_dict(snapshot_document, target)
    else:
        project = project_from_dict(snapshot_document)
    save_project_v2(target, project)
    return project


def save_tag_preset(
    path: Path,
    tags: list[str],
    colors: dict[str, str],
) -> Path:
    document = _validated_tag_preset(
        {
            "version": TAG_PRESET_VERSION,
            "custom_behavior_tags": list(tags),
            "custom_behavior_tag_colors": dict(colors),
        }
    )
    target = _tag_preset_path(path)
    _write_json_atomic(target, document)
    return target


def load_tag_preset(path: Path) -> tuple[list[str], dict[str, str]]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("tag preset JSON is invalid") from error
    validated = _validated_tag_preset(document)
    return validated["custom_behavior_tags"], validated["custom_behavior_tag_colors"]


def save_export_queue_state(
    project_path: Path,
    output_dir: Path | None,
    items: list[tuple[Path, ClipRecord]],
) -> Path:
    target = _export_queue_state_path(project_path)
    normalized_output = (
        str(Path(output_dir).expanduser().resolve(strict=False))
        if output_dir is not None
        else None
    )
    project_target = _project_path(project_path).resolve(strict=False)
    document = {
        "version": 2,
        "output_dir": _queue_path_value(output_dir, project_target.parent),
        "output_dir_base": "project" if output_dir is not None else None,
        "items": [
            {
                "id": str(uuid5(NAMESPACE_URL, f"{source.resolve()}:{record.source}:{record.start_seconds}:{record.end_seconds}:{record.output}")),
                "source_path": _queue_path_value(Path(source), project_target.parent),
                "source_path_base": "project",
                "record": _record_to_dict(record),
            }
            for source, record in items
        ],
    }
    _validated_export_queue_state(document, project_target.parent)
    _write_json_atomic(target, document)
    return target


def _queue_path_value(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return Path(os.path.relpath(Path(path).resolve(strict=False), base)).as_posix()
    except ValueError:
        return str(Path(path).resolve(strict=False))


def _resolve_queue_path(value: str | None, path_base: str, base: Path) -> Path | None:
    if value is None:
        return None
    candidate = Path(value)
    if path_base == "project" and not candidate.is_absolute():
        return (base / candidate).resolve(strict=False)
    return candidate.expanduser().resolve(strict=False)


def load_export_queue_state(
    project_path: Path,
) -> tuple[Path | None, list[tuple[Path, ClipRecord]]]:
    state_path = _export_queue_state_path(project_path)
    if not state_path.is_file():
        return None, []
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("export queue JSON is invalid") from error
    validated = _validated_export_queue_state(document, state_path.parent)
    output_dir = validated["output_dir"]
    return (
        Path(output_dir) if output_dir is not None else None,
        [
            (Path(item["source_path"]), _record_from_dict(item["record"]))
            for item in validated["items"]
        ],
    )


def _project_path(path: Path) -> Path:
    selected = Path(path)
    if selected.suffix.lower() == PROJECT_SUFFIX:
        return selected
    return selected.with_suffix(PROJECT_SUFFIX)


def _tag_preset_path(path: Path) -> Path:
    selected = Path(path)
    if selected.name.endswith(TAG_PRESET_SUFFIX):
        return selected
    return selected.with_name(f"{selected.name}{TAG_PRESET_SUFFIX}")


def _export_queue_state_path(project_path: Path) -> Path:
    target = _project_path(project_path)
    return target.with_name(f"{target.name}.export-queue.json")


def _write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    serialized = json.dumps(document, ensure_ascii=False, indent=2)
    try:
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _record_to_dict(record: ClipRecord, *, include_review: bool = False) -> dict[str, Any]:
    document = {
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
        "note": record.note,
        "data_stratum": record.data_stratum,
        "events": [
            {
                "event_type": event.event_type,
                "start_time_ms": event.start_time_ms,
                "end_time_ms": event.end_time_ms,
            }
            for event in record.events
        ],
        "age": record.age,
        "face_familiarity": record.face_familiarity,
        "reid_familiarity": record.reid_familiarity,
        "person_count": record.person_count,
    }
    if include_review:
        document["review_status"] = record.review_status
    return document



def _events_from_dicts(items: Any) -> list[EventRecord]:
    """Parse a validated list of event objects into EventRecord values."""
    events: list[EventRecord] = []
    if not isinstance(items, list):
        return events
    for item in items:
        if not isinstance(item, dict):
            continue
        events.append(
            EventRecord(
                event_type=str(item.get("event_type", "")),
                start_time_ms=int(item.get("start_time_ms", 0) or 0),
                end_time_ms=int(item.get("end_time_ms", 0) or 0),
            )
        )
    return events


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
        note=document.get("note", ""),
        review_status=document.get("review_status", "pending"),
        reviewer=document.get("reviewer", ""),
        reviewed_at=document.get("reviewed_at", ""),
        review_comment=document.get("review_comment", ""),
        rejection_reason=document.get("rejection_reason", ""),
        review_history=[dict(item) for item in document.get("review_history", [])],
        data_stratum=document.get("data_stratum", ""),
        events=_events_from_dicts(document.get("events", [])),
        age=document.get("age", ""),
        face_familiarity=document.get("face_familiarity", ""),
        reid_familiarity=document.get("reid_familiarity", ""),
        person_count=int(document.get("person_count", 0) or 0),
    )


def _validated_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("project root must be an object")
    if not _is_int(document.get("version")) or document["version"] != PROJECT_VERSION:
        raise ValueError(f"project version must be {PROJECT_VERSION}")
    legacy_keys = {"version", "active_video_id", "global_settings", "videos"}
    optional_keys = {"custom_behavior_tags", "custom_behavior_tag_colors"}
    if not legacy_keys.issubset(document) or set(document) - (
        legacy_keys | optional_keys
    ):
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
    custom_behavior_tag_colors = _validated_custom_behavior_tag_colors(
        document.get("custom_behavior_tag_colors", {}), custom_behavior_tags
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
        "custom_behavior_tag_colors": custom_behavior_tag_colors,
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


def _validated_custom_behavior_tag_colors(
    value: Any, custom_behavior_tags: list[str]
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("custom behavior tag colors must be an object")
    colors = {}
    for tag, color in value.items():
        if tag not in custom_behavior_tags:
            raise ValueError("custom behavior tag colors must reference custom tags")
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise ValueError("custom behavior tag color must be a hex color")
        colors[tag] = color.upper()
    return colors


def _validated_tag_preset(document: Any) -> dict[str, Any]:
    required = {"version", "custom_behavior_tags", "custom_behavior_tag_colors"}
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("tag preset keys are invalid")
    if not _is_int(document["version"]) or document["version"] != TAG_PRESET_VERSION:
        raise ValueError(f"tag preset version must be {TAG_PRESET_VERSION}")
    tags = _validated_custom_behavior_tags(document["custom_behavior_tags"])
    return {
        "version": TAG_PRESET_VERSION,
        "custom_behavior_tags": tags,
        "custom_behavior_tag_colors": _validated_custom_behavior_tag_colors(
            document["custom_behavior_tag_colors"], tags
        ),
    }


def _validated_export_queue_state(document: Any, base: Path | None = None) -> dict[str, Any]:
    required = {"version", "output_dir", "items"}
    if not isinstance(document, dict):
        raise ValueError("export queue keys are invalid")
    if document.get("version") == 2:
        allowed = {"version", "output_dir", "output_dir_base", "items"}
        if set(document) != allowed:
            raise ValueError("export queue keys are invalid")
        base = Path(base or Path.cwd()).expanduser().resolve(strict=False)
        output = _resolve_queue_path(document["output_dir"], str(document.get("output_dir_base", "project")), base)
        normalized = []
        for item in document["items"]:
            if not isinstance(item, dict) or set(item) != {"id", "source_path", "source_path_base", "record"}:
                raise ValueError("export queue item is invalid")
            source = _resolve_queue_path(item["source_path"], item["source_path_base"], base)
            normalized.append({"source_path": str(source), "record": _validated_record(item["record"])})
        return {"version": 1, "output_dir": str(output) if output is not None else None, "items": normalized}
    if set(document) != required:
        raise ValueError("export queue keys are invalid")
    if not _is_int(document["version"]) or document["version"] not in (EXPORT_QUEUE_VERSION, 2):
        raise ValueError(f"export queue version must be {EXPORT_QUEUE_VERSION} or 2")
    output_dir = document["output_dir"]
    if output_dir is not None and (
        not isinstance(output_dir, str) or not Path(output_dir).is_absolute()
    ):
        raise ValueError("export queue output_dir must be an absolute path or null")
    if not isinstance(document["items"], list):
        raise ValueError("export queue items must be a list")
    items = []
    for item in document["items"]:
        if not isinstance(item, dict) or set(item) != {"source_path", "record"}:
            raise ValueError("export queue item is invalid")
        source_path = item["source_path"]
        if not isinstance(source_path, str) or not Path(source_path).is_absolute():
            raise ValueError("export queue source_path must be absolute")
        items.append(
            {
                "source_path": str(Path(source_path)),
                "record": _validated_record(item["record"]),
            }
        )
    return {
        "version": EXPORT_QUEUE_VERSION,
        "output_dir": output_dir,
        "items": items,
    }


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
    optional_keys = {
        "note", "review_status", "reviewer", "reviewed_at",
        "review_comment", "rejection_reason", "review_history",
        "data_stratum", "events",
        "age", "face_familiarity", "reid_familiarity", "person_count",
    }
    if (
        not isinstance(document, dict)
        or not required_keys.issubset(document)
        or set(document) - (required_keys | optional_keys)
    ):
        raise ValueError("segment record is invalid")
    for key in (
        "source",
        "output",
        "polarity",
        "lighting",
        "status",
        "error",
        "note",
        "review_status",
        "reviewer",
        "reviewed_at",
        "review_comment",
        "rejection_reason",
        "data_stratum",
        "age",
        "face_familiarity",
        "reid_familiarity",
    ):
        history = document.get("review_history", [])
        if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
            raise ValueError("segment review_history must be a list of objects")
        if not isinstance(document.get(key, ""), str):
            raise ValueError(f"segment {key} must be a string")
    for key in ("start_seconds", "end_seconds"):
        if not _is_number(document[key]):
            raise ValueError(f"segment {key} must be a finite number")
    if float(document["end_seconds"]) <= float(document["start_seconds"]):
        raise ValueError("segment end_seconds must be greater than start_seconds")
    if not isinstance(document["behaviors"], list) or not all(
        isinstance(behavior, str) for behavior in document["behaviors"]
    ):
        raise ValueError("segment behaviors must be a list of strings")
    if not _is_int(document["sequence"]):
        raise ValueError("segment sequence must be an integer")
    if not _is_int(document.get("person_count", 0)):
        raise ValueError("segment person_count must be an integer")
    review_status = document.get("review_status", "pending")
    if review_status not in {"pending", "approved", "needs_fix", "rejected"}:
        raise ValueError("segment review_status is invalid")
    events = document.get("events", [])
    if not isinstance(events, list) or not all(
        isinstance(event, dict) for event in events
    ):
        raise ValueError("segment events must be a list of objects")
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
        "note": document.get("note", ""),
        "review_status": review_status,
        "data_stratum": document.get("data_stratum", ""),
        "events": [dict(event) for event in events],
        "age": document.get("age", ""),
        "face_familiarity": document.get("face_familiarity", ""),
        "reid_familiarity": document.get("reid_familiarity", ""),
        "person_count": int(document.get("person_count", 0) or 0),
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
