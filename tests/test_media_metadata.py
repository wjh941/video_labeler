import json
from pathlib import Path

from video_labeler.ffmpeg_service import probe_media_metadata
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_v2 import load_project_v2, save_project_v2


class _Completed:
    returncode = 0
    stderr = ""
    stdout = json.dumps({
        "format": {"duration": "12.5"},
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                     "avg_frame_rate": "25/1", "codec_name": "h264"},
                    {"codec_type": "audio"}],
    })


def test_probe_media_metadata_parses_video_stream(monkeypatch, tmp_path):
    import video_labeler.ffmpeg_service as service
    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: _Completed())
    assert probe_media_metadata("ffprobe", tmp_path / "camera.mp4") == {
        "duration": 12.5, "width": 1920, "height": 1080, "fps": 25.0,
        "codec": "h264", "has_audio": True,
    }


def test_v2_round_trip_preserves_video_metadata(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "camera.mp4")
    video.metadata = {"duration": 12.5, "width": 1920, "height": 1080, "fps": 25.0}
    path = tmp_path / "job.labelproj"
    save_project_v2(path, project, now="2026-01-01T00:00:00Z")
    assert load_project_v2(path).videos[0].metadata == video.metadata
