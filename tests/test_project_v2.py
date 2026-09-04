import json

from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_v2 import (
    load_project_v2, migrate_v1_to_v2, project_to_v2_dict, save_project_v2,
)

def test_v2_uses_project_relative_media_path_and_round_trips_after_move(tmp_path):
    root = tmp_path / "project"
    media = root / "media" / "camera.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"x")
    project = new_project()
    video = add_or_activate_video(project, media)
    video.segments.append(ClipRecord("camera.mp4", 1, 2, "clip.mp4", ("dog_out",), "pos", "daytime", 1, "fail", "oops", "note"))
    target = root / "work.labelproj"
    save_project_v2(target, project, now="2026-01-01T00:00:00Z")
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["videos"][0]["path"] == "media/camera.mp4"
    assert document["videos"][0]["path_base"] == "project"
    assert load_project_v2(target).videos[0].path == media.resolve()

def test_v1_migration_preserves_segment_data(tmp_path):
    source = tmp_path / "camera.mp4"
    document = {"version": 1, "active_video_id": "v", "global_settings": {"camera": "a"}, "videos": [{"id": "v", "path": str(source), "segments": [{"source": "camera.mp4", "start_seconds": 1, "end_seconds": 2, "output": "renamed.mp4", "behaviors": ["dog_out"], "polarity": "neg", "lighting": "daytime", "sequence": 2, "status": "fail", "error": "x", "note": "n"}]}]}
    migrated = migrate_v1_to_v2(document, tmp_path / "work.labelproj", now="2026-01-01T00:00:00Z")
    assert migrated["version"] == 2
    assert migrated["settings"] == {"camera": "a"}
    assert migrated["videos"][0]["segments"][0]["error"] == "x"
    assert "id" in migrated["videos"][0]["segments"][0]
