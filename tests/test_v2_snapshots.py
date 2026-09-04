import json
from datetime import datetime

from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, create_backup, create_version_snapshot, new_project, restore_version_snapshot


def _project(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "media" / "camera.mp4")
    video.metadata = {"duration": 9.0, "width": 1280}
    video.segments.append(ClipRecord("camera.mp4", 1, 2, "clip.mp4", ("dog_out",)))
    return project


def test_backup_and_snapshot_are_v2_and_keep_project_relative_paths(tmp_path):
    project_path = tmp_path / "job.labelproj"
    project = _project(tmp_path)
    backup = create_backup(project_path, project, now=datetime(2026, 1, 1, 1, 2, 3))
    snapshot = create_version_snapshot(project_path, project, now=datetime(2026, 1, 1, 1, 2, 4))
    for path in (backup, snapshot):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["version"] == 2
        assert document["format"] == "video-labeler-project"
        assert document["videos"][0]["path"] == "media/camera.mp4"
        assert document["videos"][0]["metadata"]["duration"] == 9.0


def test_restore_v2_snapshot_rewrites_v2_project(tmp_path):
    project_path = tmp_path / "job.labelproj"
    project = _project(tmp_path)
    snapshot = create_version_snapshot(project_path, project, now=datetime(2026, 1, 1, 1, 2, 4))
    restore_version_snapshot(project_path, snapshot)
    document = json.loads(project_path.read_text(encoding="utf-8"))
    assert document["version"] == 2
    assert document["videos"][0]["metadata"]["width"] == 1280
