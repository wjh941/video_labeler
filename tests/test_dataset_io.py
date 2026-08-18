import json

from video_labeler.dataset_io import write_clip_jsonl, write_clip_yolo
from video_labeler.models import ClipRecord


def _record() -> ClipRecord:
    return ClipRecord(
        source="camera.mp4",
        start_seconds=1.5,
        end_seconds=3.0,
        output="clip-001.mp4",
        behaviors=("dog_out", "fall"),
        polarity="pos",
        lighting="daytime",
        sequence=1,
        note="review after export",
    )


def test_dataset_exports_write_jsonl_records_and_yolo_label_files(tmp_path):
    record = _record()
    jsonl_path = tmp_path / "clips.jsonl"
    yolo_dir = tmp_path / "yolo"

    write_clip_jsonl(jsonl_path, [record])
    write_clip_yolo(yolo_dir, [record])

    assert json.loads(jsonl_path.read_text(encoding="utf-8")) == {
        "source": "camera.mp4",
        "start_seconds": 1.5,
        "end_seconds": 3.0,
        "output": "clip-001.mp4",
        "behaviors": ["dog_out", "fall"],
        "polarity": "pos",
        "lighting": "daytime",
        "sequence": 1,
        "status": "queued",
        "error": "",
        "note": "review after export",
    }
    assert (yolo_dir / "classes.txt").read_text(encoding="utf-8") == "dog_out\nfall\n"
    assert (yolo_dir / "labels" / "clip-001.txt").read_text(encoding="utf-8") == "0\n1\n"
