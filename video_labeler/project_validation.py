"""Project-level validation and quality diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ClipRecord
from .project_io import LabelProject
from .naming import validate_output_filename


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    video_id: str = ""
    segment_index: int | None = None
    severity: str = "error"


def validate_project(project: LabelProject) -> list[ValidationIssue]:
    """Return deterministic, non-destructive quality issues for a project."""
    issues: list[ValidationIssue] = []
    output_names: dict[str, tuple[str, int]] = {}
    for video in project.videos:
        if not video.path.is_file():
            issues.append(ValidationIssue("missing_source", f"视频源不存在: {video.path}", video.id))
        previous: list[tuple[int, ClipRecord]] = []
        for index, record in enumerate(video.segments):
            prefix = {"video_id": video.id, "segment_index": index}
            if record.start_seconds < 0 or record.end_seconds <= record.start_seconds:
                issues.append(ValidationIssue("invalid_time_range", "片段时间范围无效", **prefix))
            duration = video.metadata.get("duration")
            if isinstance(duration, (int, float)) and record.end_seconds > duration:
                issues.append(ValidationIssue("out_of_bounds", "片段结束时间超过视频时长", **prefix))
            try:
                validate_output_filename(record.output)
            except ValueError as error:
                issues.append(ValidationIssue("invalid_output", str(error), **prefix))
            if not record.behaviors:
                issues.append(ValidationIssue("missing_behavior", "片段未设置行为标签", **prefix, severity="warning"))
            if record.output in output_names:
                other_video, other_index = output_names[record.output]
                issues.append(ValidationIssue("duplicate_output", f"输出文件名重复（{other_video}:{other_index + 1}）", **prefix))
            else:
                output_names[record.output] = (video.id, index)
            for previous_index, previous_record in previous:
                if record.start_seconds < previous_record.end_seconds and previous_record.start_seconds < record.end_seconds:
                    issues.append(ValidationIssue("overlapping_segments", f"与片段 {previous_index + 1} 时间重叠", **prefix, severity="warning"))
            previous.append((index, record))
    return issues


def export_quality_issues(project: LabelProject, *, require_approved: bool = False) -> list[ValidationIssue]:
    issues = validate_project(project)
    if require_approved:
        for video in project.videos:
            for index, record in enumerate(video.segments):
                if record.review_status != "approved":
                    issues.append(ValidationIssue("not_approved", "片段尚未审核通过", video.id, index, "warning"))
    return issues
