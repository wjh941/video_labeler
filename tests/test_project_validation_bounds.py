from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_validation import validate_project

def test_validate_project_reports_duration_overflow(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "camera.mp4")
    video.metadata = {"duration": 3.0}
    video.segments.append(ClipRecord("camera.mp4", 1, 4, "clip.mp4", ("dog_out",)))
    assert [issue.code for issue in validate_project(project)] == ["missing_source", "out_of_bounds"]
