from video_labeler.csv_io import read_full_clip_csv, write_full_clip_csv
from video_labeler.models import ClipRecord


def test_full_csv_round_trip_preserves_labels_status_and_error(tmp_path):
    record = ClipRecord(
        source="camera.mp4", start_seconds=1.25, end_seconds=3.5,
        output="renamed.mp4", behaviors=("dog_out", "fall"),
        polarity="neg", lighting="daytime", sequence=7,
        status="fail", error="codec error", note="review",
    )
    path = tmp_path / "full.csv"
    write_full_clip_csv(path, [record])
    assert read_full_clip_csv(path) == [record]
