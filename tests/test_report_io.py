import json

from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.report_io import project_statistics_to_dict, write_project_statistics_report


def test_statistics_report_is_portable_and_deterministic(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "camera.mp4")
    video.segments.append(ClipRecord("camera.mp4", 1, 3, "clip.mp4", ("dog_out",), "pos", status="done"))
    expected = project_statistics_to_dict(project)
    assert expected["format"] == "video-labeler-statistics"
    path = write_project_statistics_report(tmp_path / "report", project)
    assert path.name == "report.json"
    assert json.loads(path.read_text(encoding="utf-8")) == expected
