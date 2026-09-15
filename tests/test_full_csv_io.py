from video_labeler.csv_io import (
    FULL_CSV_FIELDS, read_full_clip_csv, write_full_clip_csv,
)
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


def test_full_csv_round_trip_keeps_audit_fields(tmp_path):
    record = ClipRecord(
        source="camera.mp4", start_seconds=1.0, end_seconds=2.0,
        output="renamed.mp4", behaviors=("dog_out",), polarity="pos",
        lighting="daytime", sequence=1, note="n",
        annotator="zhang", created_at="2026-02-01T08:00:00Z",
        updated_at="2026-02-01T09:30:00Z",
    )
    path = tmp_path / "full.csv"
    write_full_clip_csv(path, [record])
    header = path.read_text(encoding="utf-8-sig").splitlines()[0]
    assert header.endswith("annotator,created_at,updated_at")
    assert FULL_CSV_FIELDS[-3:] == ("annotator", "created_at", "updated_at")
    loaded = read_full_clip_csv(path)[0]
    assert loaded.annotator == "zhang"
    assert loaded.created_at == "2026-02-01T08:00:00Z"
    assert loaded.updated_at == "2026-02-01T09:30:00Z"


def test_full_csv_without_audit_columns_still_imports(tmp_path):
    legacy_header = (
        "source,start_seconds,end_seconds,output,behaviors,polarity,lighting,"
        "sequence,status,error,note,review_status,reviewer,reviewed_at,"
        "review_comment,rejection_reason,data_stratum,events,age,"
        "face_familiarity,reid_familiarity,person_count"
    )
    legacy_row = (
        'camera.mp4,1.0,2.0,renamed.mp4,["dog_out"],pos,daytime,'
        "1,queued,,n,pending,,,,,,,[],,,0"
    )
    path = tmp_path / "legacy.csv"
    path.write_text(legacy_header + "\n" + legacy_row + "\n", encoding="utf-8-sig")
    record = read_full_clip_csv(path)[0]
    assert record.annotator == ""
    assert record.created_at == ""
    assert record.updated_at == ""
    assert record.source == "camera.mp4"
