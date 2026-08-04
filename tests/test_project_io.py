from datetime import datetime

import pytest

from video_labeler.models import ClipRecord


def test_project_round_trip_preserves_absolute_paths_segments_and_settings(tmp_path):
    from video_labeler.project_io import (
        add_or_activate_video,
        load_project,
        new_project,
        save_project,
    )

    project_path = tmp_path / "shift.labelproj"
    source = (tmp_path / "camera.mp4").resolve()
    project = new_project()
    entry = add_or_activate_video(project, source)
    entry.segments.append(
        ClipRecord(
            source=source.name,
            start_seconds=1.25,
            end_seconds=3.5,
            output="20260729-cam02_indoor-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
            status="completed",
            error="",
        )
    )
    project.global_settings = {"date": "20260729", "camera": "cam02"}

    save_project(project_path, project)
    loaded = load_project(project_path)

    assert loaded.active_video_id == entry.id
    assert loaded.videos[0].path == source
    assert loaded.videos[0].segments == entry.segments
    assert loaded.global_settings == project.global_settings


def test_save_normalizes_extension_without_changing_existing_backup_filename(tmp_path):
    from video_labeler.project_io import new_project, save_project

    project = new_project()
    selected_path = tmp_path / "shift"
    backup_path = tmp_path / "shift_20260804-100000.labelproj"

    assert save_project(selected_path, project) == tmp_path / "shift.labelproj"
    assert save_project(backup_path, project) == backup_path
    assert (tmp_path / "shift.labelproj").is_file()
    assert backup_path.is_file()


def test_create_backup_keeps_ten_newest_files(tmp_path):
    from video_labeler.project_io import create_backup, new_project, save_project

    project_path = tmp_path / "shift.labelproj"
    project = new_project()
    save_project(project_path, project)

    for second in range(12):
        create_backup(
            project_path,
            project,
            now=datetime(2026, 8, 4, 10, 0, second),
        )

    backups = sorted((tmp_path / ".backups").glob("shift_*.labelproj"))
    assert len(backups) == 10
    assert backups[0].name == "shift_20260804-100002.labelproj"


def test_project_loader_rejects_invalid_version_but_keeps_missing_paths(tmp_path):
    from video_labeler.project_io import load_project, project_from_dict

    invalid_path = tmp_path / "invalid.labelproj"
    invalid_path.write_text('{"version": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_project(invalid_path)

    missing = (tmp_path / "missing.mp4").resolve()
    project = project_from_dict(
        {
            "version": 1,
            "active_video_id": "video-1",
            "global_settings": {},
            "videos": [{"id": "video-1", "path": str(missing), "segments": []}],
        }
    )

    assert project.videos[0].path == missing
    assert not project.videos[0].path.exists()


@pytest.mark.parametrize(
    "document, message",
    [
        ([], "root"),
        (
            {
                "version": 1,
                "active_video_id": "missing",
                "global_settings": {},
                "videos": [{"id": "video-1", "path": "C:/video.mp4", "segments": []}],
            },
            "active_video_id",
        ),
        (
            {
                "version": 1,
                "active_video_id": "duplicate",
                "global_settings": {},
                "videos": [
                    {"id": "duplicate", "path": "C:/video.mp4", "segments": []},
                    {"id": "duplicate", "path": "C:/other.mp4", "segments": []},
                ],
            },
            "duplicate",
        ),
        (
            {
                "version": 1,
                "active_video_id": "video-1",
                "global_settings": {},
                "videos": [
                    {
                        "id": "video-1",
                        "path": "C:/video.mp4",
                        "segments": [{"source": "video.mp4"}],
                    }
                ],
            },
            "segment",
        ),
    ],
)
def test_project_loader_rejects_invalid_document_shapes(document, message):
    from video_labeler.project_io import project_from_dict

    with pytest.raises(ValueError, match=message):
        project_from_dict(document)
