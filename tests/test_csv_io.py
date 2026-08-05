import pytest

try:
    from video_labeler.csv_io import read_clip_csv, write_clip_csv
    from video_labeler.models import ClipRecord
except ImportError:
    ClipRecord = None
    read_clip_csv = None
    write_clip_csv = None


def _require_csv_api():
    assert ClipRecord is not None, "CSV compatibility API is not implemented"


def _record() -> object:
    _require_csv_api()
    return ClipRecord(
        source="cam02_20260729.mp4",
        start_seconds=2.5,
        end_seconds=4.0,
        output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=1,
    )


def test_write_clip_csv_uses_batch_script_headers_and_bom(tmp_path):
    _require_csv_api()
    csv_path = tmp_path / "clips.csv"

    write_clip_csv(csv_path, [_record()])

    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").splitlines() == [
        "source,start,end,output",
        (
            "cam02_20260729.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam02_panorama-dog_out-pos-daytime-001.mp4"
        ),
    ]


def test_read_clip_csv_restores_times_and_standard_filename_labels(tmp_path):
    _require_csv_api()
    csv_path = tmp_path / "clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam02_closeup-dog_out+fall-neg-daytime-021.mp4\n"
        ),
        encoding="utf-8-sig",
    )

    record = read_clip_csv(csv_path)[0]

    assert record.source == "cam02.mp4"
    assert record.start_seconds == 2.5
    assert record.end_seconds == 4.0
    assert record.behaviors == ("dog_out", "fall")
    assert record.polarity == "neg"
    assert record.lighting == "daytime"
    assert record.sequence == 21


def test_read_clip_csv_restores_custom_filename_labels(tmp_path):
    _require_csv_api()
    csv_path = tmp_path / "custom-clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam_02_doorway-dog_out-needs_review-night_red-007.mp4\n"
        ),
        encoding="utf-8-sig",
    )

    record = read_clip_csv(csv_path)[0]

    assert record.behaviors == ("dog_out",)
    assert record.polarity == "needs_review"
    assert record.lighting == "night_red"
    assert record.sequence == 7


def test_read_clip_csv_restores_unknown_custom_behavior_tags(tmp_path):
    _require_csv_api()
    csv_path = tmp_path / "custom-behavior-clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam02_panorama-delivery_dropoff-pos-daytime-007.mp4\n"
        ),
        encoding="utf-8-sig",
    )

    record = read_clip_csv(csv_path)[0]

    assert record.behaviors == ("delivery_dropoff",)
    assert record.polarity == "pos"
    assert record.lighting == "daytime"
    assert record.sequence == 7


def test_read_clip_csv_rejects_missing_required_headers(tmp_path):
    _require_csv_api()
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("source,start\ncam02.mp4,00:00:01", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        read_clip_csv(csv_path)
