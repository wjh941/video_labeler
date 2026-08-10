from pathlib import Path

import pytest

from video_labeler.models import ClipRecord, ProjectMetadata
from video_labeler.project_io import ProjectState, read_project_manifest, write_project_manifest


def _record(
    *,
    output: str = "20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
    behaviors: tuple[str, ...] = ("dog_out",),
    polarity: str = "pos",
    lighting: str = "daytime",
    sequence: int = 1,
    status: str = "queued",
    error: str = "",
) -> ClipRecord:
    return ClipRecord(
        source="cam02_20260729.mp4",
        start_seconds=2.5,
        end_seconds=4.0,
        output=output,
        behaviors=behaviors,
        polarity=polarity,
        lighting=lighting,
        sequence=sequence,
        status=status,
        error=error,
    )


def test_project_manifest_round_trip_preserves_paths_metadata_and_records(tmp_path):
    state = ProjectState(
        source_path=Path("C:/videos/cam02.mp4"),
        output_dir=Path("C:/clips"),
        metadata=ProjectMetadata("20260729", "cam02", "panorama"),
        records=[_record(output="manual-review-01.mp4", status="fail", error="source missing")],
    )
    path = tmp_path / "project.json"

    write_project_manifest(path, state)

    assert read_project_manifest(path) == state


def test_read_project_manifest_rejects_unknown_version(tmp_path):
    path = tmp_path / "project.json"
    path.write_text('{"version": 99, "records": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="version"):
        read_project_manifest(path)


def test_read_project_manifest_rejects_non_list_behaviors_with_row_context(tmp_path):
    path = tmp_path / "project.json"
    path.write_text(
        '{"version": 1, "metadata": {"date": "20260729", "camera": "cam02", '
        '"view": "panorama"}, "records": [{"source": "cam02.mp4", '
        '"start": 1, "end": 2, "output": "clip.mp4", "behaviors": "dog_out", '
        '"polarity": "pos", "lighting": "daytime", "sequence": 1}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="record 1.*behaviors"):
        read_project_manifest(path)


def test_read_project_manifest_accepts_record_with_all_empty_labels(tmp_path):
    path = tmp_path / "project.json"
    path.write_text(
        '{"version": 1, "metadata": {"date": "20260729", "camera": "cam02", '
        '"view": "panorama"}, "records": [{"source": "cam02.mp4", '
        '"start": 1, "end": 2, "output": "clip.mp4", "behaviors": [], '
        '"polarity": "", "lighting": "", "sequence": 0}]}',
        encoding="utf-8",
    )

    assert read_project_manifest(path).records == [
        ClipRecord(
            source="cam02.mp4",
            start_seconds=1,
            end_seconds=2,
            output="clip.mp4",
            behaviors=(),
            polarity="",
            lighting="",
            sequence=0,
        )
    ]


def test_read_project_manifest_rejects_partial_labels(tmp_path):
    path = tmp_path / "project.json"
    path.write_text(
        '{"version": 1, "metadata": {"date": "20260729", "camera": "cam02", '
        '"view": "panorama"}, "records": [{"source": "cam02.mp4", '
        '"start": 1, "end": 2, "output": "clip.mp4", "behaviors": ["dog_out"], '
        '"polarity": "", "lighting": "daytime", "sequence": 1}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="record 1.*labels"):
        read_project_manifest(path)
