"""Deterministic dataset statistics for project review and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .project_io import LabelProject


@dataclass(frozen=True)
class ProjectStatistics:
    video_count: int
    segment_count: int
    total_duration: float
    positive_count: int
    negative_count: int
    unlabeled_count: int
    status_counts: dict[str, int]
    behavior_counts: dict[str, int]
    behavior_durations: dict[str, float]


def calculate_project_statistics(project: LabelProject) -> ProjectStatistics:
    status = Counter()
    behaviors = Counter()
    behavior_durations: dict[str, float] = {}
    total_duration = 0.0
    positive = negative = unlabeled = segments = 0
    for video in project.videos:
        for record in video.segments:
            segments += 1
            duration = max(0.0, float(record.end_seconds) - float(record.start_seconds))
            total_duration += duration
            status[record.status] += 1
            if record.polarity == "pos":
                positive += 1
            elif record.polarity == "neg":
                negative += 1
            else:
                unlabeled += 1
            for behavior in record.behaviors:
                behaviors[behavior] += 1
                behavior_durations[behavior] = behavior_durations.get(behavior, 0.0) + duration
    return ProjectStatistics(
        video_count=len(project.videos),
        segment_count=segments,
        total_duration=total_duration,
        positive_count=positive,
        negative_count=negative,
        unlabeled_count=unlabeled,
        status_counts=dict(sorted(status.items())),
        behavior_counts=dict(sorted(behaviors.items())),
        behavior_durations=dict(sorted(behavior_durations.items())),
    )
