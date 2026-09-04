import json

from video_labeler.csv_io import read_full_clip_csv, write_full_clip_csv
from video_labeler.models import ClipRecord
from video_labeler.project_io import add_or_activate_video, new_project
from video_labeler.project_v2 import load_project_v2, save_project_v2


def test_review_status_round_trips_through_full_csv_and_v2(tmp_path):
    record = ClipRecord("camera.mp4", 1, 2, "clip.mp4", ("dog_out",), review_status="approved")
    csv_path = tmp_path / "review.csv"
    write_full_clip_csv(csv_path, [record])
    assert read_full_clip_csv(csv_path) == [record]

    project = new_project()
    video = add_or_activate_video(project, tmp_path / "camera.mp4")
    video.segments.append(record)
    project_path = save_project_v2(tmp_path / "job.labelproj", project)
    document = json.loads(project_path.read_text(encoding="utf-8"))
    assert document["videos"][0]["segments"][0]["review_status"] == "approved"
    restored = load_project_v2(project_path)
    assert restored.videos[0].segments[0].review_status == "approved"
