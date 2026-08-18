"""Optional real-media export coverage.

Set VIDEO_LABELER_SAMPLE_MEDIA to a local MP4 of at least two seconds and
ensure ffmpeg and ffprobe are available on PATH to run this test.
"""

import os
from pathlib import Path
import shutil

import pytest

from video_labeler.ffmpeg_service import ExportRequest, run_clip_export


def test_real_media_clip_export_when_sample_is_available(tmp_path):
    sample = Path(os.environ.get("VIDEO_LABELER_SAMPLE_MEDIA", ""))
    if not sample.is_file():
        pytest.skip("set VIDEO_LABELER_SAMPLE_MEDIA to run real-media export")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("ffmpeg and ffprobe must be available on PATH")

    output = tmp_path / "sample-clip.mp4"
    result = run_clip_export(
        ExportRequest(
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            input_path=sample,
            output_path=output,
            start="00:00:00.000",
            end="00:00:01.000",
            mode="copy",
            overwrite=False,
        )
    )

    assert result.status == "ok", result.error
    assert output.is_file()
