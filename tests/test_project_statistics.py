from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_statistics import calculate_project_statistics


def test_project_statistics_counts_labels_status_and_duration(tmp_path):
    project = new_project()
    video = add_or_activate_video(project, tmp_path / "camera.mp4")
    video.segments = [
        ClipRecord("camera.mp4", 0, 2, "a.mp4", ("dog_out",), "pos", status="done"),
        ClipRecord("camera.mp4", 3, 6, "b.mp4", ("dog_out", "fall"), "neg", status="fail"),
        ClipRecord("camera.mp4", 8, 9, "c.mp4"),
    ]
    stats = calculate_project_statistics(project)
    assert stats.video_count == 1
    assert stats.segment_count == 3
    assert stats.total_duration == 6
    assert (stats.positive_count, stats.negative_count, stats.unlabeled_count) == (1, 1, 1)
    assert stats.status_counts == {"done": 1, "fail": 1, "queued": 1}
    assert stats.behavior_counts == {"dog_out": 2, "fall": 1}
    assert stats.behavior_durations == {"dog_out": 5.0, "fall": 3.0}
