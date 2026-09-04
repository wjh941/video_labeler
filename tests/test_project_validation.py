from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_validation import validate_project


def test_validate_project_reports_missing_behavior_and_missing_source(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "missing.mp4")
    video.segments.append(ClipRecord("missing.mp4", 1, 2, "clip.mp4"))

    issues = validate_project(project)

    assert [(item.code, item.severity) for item in issues] == [
        ("missing_source", "error"),
        ("missing_behavior", "warning"),
    ]


def test_validate_project_reports_overlaps_and_duplicate_outputs(tmp_path):
    source = tmp_path / "camera.mp4"
    source.write_bytes(b"video")
    project = new_project()
    video = add_or_activate_video(project, source)
    video.segments.extend([
        ClipRecord("camera.mp4", 1, 4, "same.mp4", ("dog_out",)),
        ClipRecord("camera.mp4", 3, 5, "same.mp4", ("fall",)),
    ])

    issues = validate_project(project)

    assert [item.code for item in issues] == [
        "duplicate_output",
        "overlapping_segments",
    ]
    assert issues[0].segment_index == 1
    assert issues[1].severity == "warning"
