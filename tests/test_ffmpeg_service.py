from pathlib import Path

try:
    from video_labeler.ffmpeg_service import (
        build_command,
        format_seconds,
        parse_time_to_seconds,
    )
except ImportError:
    build_command = None
    format_seconds = None
    parse_time_to_seconds = None

try:
    from video_labeler.ffmpeg_service import ExportRequest, run_clip_export
except ImportError:
    ExportRequest = None
    run_clip_export = None


def _require_ffmpeg_api():
    assert build_command is not None, "FFmpeg service is not implemented"


def test_encode_command_uses_duration_and_h264_aac(tmp_path):
    _require_ffmpeg_api()
    command = build_command(
        "ffmpeg.exe",
        tmp_path / "source.mp4",
        tmp_path / "output.mp4",
        "00:00:12.000",
        "00:00:15.250",
        "encode",
        False,
    )

    assert command[0] == "ffmpeg.exe"
    assert "-n" in command
    assert ["-c:v", "libx264"] == command[
        command.index("-c:v") : command.index("-c:v") + 2
    ]
    assert ["-c:a", "aac"] == command[
        command.index("-c:a") : command.index("-c:a") + 2
    ]
    assert command[command.index("-t") + 1] == "3.250"


def test_copy_command_uses_end_time_and_stream_copy(tmp_path):
    _require_ffmpeg_api()
    command = build_command(
        "ffmpeg.exe",
        tmp_path / "source.mp4",
        tmp_path / "output.mp4",
        "00:00:12.000",
        "00:00:15.250",
        "copy",
        True,
    )

    assert "-y" in command
    assert command[command.index("-to") + 1] == "00:00:15.250"
    assert ["-c", "copy"] == command[command.index("-c") : command.index("-c") + 2]


def test_time_conversion_round_trips_millisecond_precision():
    _require_ffmpeg_api()

    assert parse_time_to_seconds("1:02:03.250") == 3723.25
    assert format_seconds(3723.25) == "01:02:03.250"


def test_encode_command_rejects_an_end_time_before_start_time(tmp_path):
    _require_ffmpeg_api()

    try:
        build_command(
            "ffmpeg.exe",
            Path(tmp_path / "source.mp4"),
            Path(tmp_path / "output.mp4"),
            "00:00:15.000",
            "00:00:12.000",
            "encode",
            False,
        )
    except ValueError as error:
        assert "end" in str(error)
    else:
        raise AssertionError("expected an invalid time range to be rejected")


def test_run_clip_export_skips_an_existing_valid_output(tmp_path):
    assert ExportRequest is not None, "clip export execution API is not implemented"
    output_path = tmp_path / "already-cut.mp4"
    output_path.write_bytes(b"x" * 1024)
    request = ExportRequest(
        ffmpeg="ffmpeg.exe",
        input_path=tmp_path / "source.mp4",
        output_path=output_path,
        start="00:00:02.000",
        end="00:00:04.000",
        mode="encode",
        overwrite=False,
    )

    result = run_clip_export(request)

    assert result.status == "skip"
    assert result.output == output_path.name
