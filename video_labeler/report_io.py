"""Portable JSON reporting for project review statistics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .project_io import LabelProject
from .project_statistics import calculate_project_statistics


def project_statistics_to_dict(project: LabelProject) -> dict[str, Any]:
    stats = calculate_project_statistics(project)
    return {
        "format": "video-labeler-statistics",
        "version": 1,
        "video_count": stats.video_count,
        "segment_count": stats.segment_count,
        "total_duration": stats.total_duration,
        "positive_count": stats.positive_count,
        "negative_count": stats.negative_count,
        "unlabeled_count": stats.unlabeled_count,
        "status_counts": stats.status_counts,
        "behavior_counts": stats.behavior_counts,
        "behavior_durations": stats.behavior_durations,
        "review_status_counts": stats.review_status_counts,
        "review_completion_rate": stats.review_completion_rate,
        "review_approval_rate": stats.review_approval_rate,
    }


def write_project_statistics_report(path: Path, project: LabelProject) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(project_statistics_to_dict(project), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
