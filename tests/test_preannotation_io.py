import json

import pytest

from video_labeler.preannotation_io import PreAnnotation, read_preannotation_json


def test_read_preannotation_json_accepts_reviewable_segments(tmp_path):
    path = tmp_path / "preannotations.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start_seconds": 1.25,
                        "end_seconds": 3.5,
                        "behaviors": ["dog_out", "fall"],
                        "polarity": "pos",
                        "lighting": "daytime",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert read_preannotation_json(path) == [
        PreAnnotation(
            start_seconds=1.25,
            end_seconds=3.5,
            behaviors=("dog_out", "fall"),
            polarity="pos",
            lighting="daytime",
        )
    ]


def test_read_preannotation_json_rejects_an_invalid_time_range(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"segments":[{"start_seconds":4,"end_seconds":2,"behaviors":["dog_out"]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="end_seconds"):
        read_preannotation_json(path)
