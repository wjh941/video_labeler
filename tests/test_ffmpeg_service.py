from pathlib import Path
import subprocess
import threading

import pytest

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
    from video_labeler.ffmpeg_service import (
        ExportControl,
        temporary_output_path,
    )
except ImportError:
    ExportControl = None
    temporary_output_path = None

try:
    from video_labeler.ffmpeg_service import cleanup_orphaned_temporary_outputs
except ImportError:
    cleanup_orphaned_temporary_outputs = None

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


@pytest.mark.parametrize("invalid_time", ("nan", "inf", "-inf"))
def test_time_conversion_rejects_nonfinite_values(invalid_time):
    _require_ffmpeg_api()

    with pytest.raises(ValueError, match="finite"):
        parse_time_to_seconds(invalid_time)
    with pytest.raises(ValueError, match="finite"):
        format_seconds(float(invalid_time))


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
        ffprobe="ffprobe.exe",
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


def test_temporary_output_path_is_unique_and_keeps_the_media_suffix(tmp_path):
    assert temporary_output_path is not None, "temporary output API is not implemented"
    output = tmp_path / "clip.mp4"

    first = temporary_output_path(output)
    second = temporary_output_path(output)

    assert first != second
    assert first.name.endswith(".part.mp4")
    assert second.name.endswith(".part.mp4")


def test_cleanup_orphaned_temporary_outputs_only_removes_our_uuid_parts(tmp_path):
    assert cleanup_orphaned_temporary_outputs is not None
    orphan = tmp_path / ("clip." + "a" * 32 + ".part.mp4")
    user_media = tmp_path / "family.part.mp4"
    nested_orphan = tmp_path / "nested" / ("clip." + "b" * 32 + ".part.mp4")
    orphan.write_bytes(b"partial")
    user_media.write_bytes(b"user media")
    nested_orphan.parent.mkdir()
    nested_orphan.write_bytes(b"partial")

    removed = cleanup_orphaned_temporary_outputs(tmp_path)

    assert removed == [orphan]
    assert not orphan.exists()
    assert user_media.exists()
    assert nested_orphan.exists()


def test_run_clip_export_reports_a_permission_tip(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "locked" / "clip.mp4"
    path_type = type(tmp_path)
    original_mkdir = path_type.mkdir

    def deny_output_directory(path, *args, **kwargs):
        if path == output.parent:
            raise PermissionError("access denied")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(path_type, "mkdir", deny_output_directory)

    result = run_clip_export(
        ExportRequest(
            ffmpeg="ffmpeg.exe",
            ffprobe="ffprobe.exe",
            input_path=source,
            output_path=output,
            start="00:00:00.000",
            end="00:00:01.000",
            mode="encode",
            overwrite=False,
        )
    )

    assert result.status == "fail"
    assert "访问被拒绝" in result.error


def test_run_clip_export_publishes_only_after_media_validation(tmp_path, monkeypatch):
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"

    class SuccessfulPopen:
        def __init__(self, command, **kwargs):
            self.temporary_path = Path(command[-1])
            self.returncode = None

        def communicate(self, timeout=None):
            self.temporary_path.write_bytes(b"x" * 2048)
            self.returncode = 0
            return "", ""

        def poll(self):
            return self.returncode

    monkeypatch.setattr(subprocess, "Popen", SuccessfulPopen)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            '{"format":{"duration":"2.0"},"streams":[{"codec_type":"video"}]}',
            "",
        ),
    )

    result = run_clip_export(
        ExportRequest(
            ffmpeg="ffmpeg.exe",
            ffprobe="ffprobe.exe",
            input_path=source,
            output_path=output,
            start="00:00:02.000",
            end="00:00:04.000",
            mode="encode",
            overwrite=False,
        )
    )

    assert result.status == "ok"
    assert output.read_bytes() == b"x" * 2048
    assert not list(tmp_path.glob("clip.*.part.mp4"))


def test_run_clip_export_cancellation_leaves_no_published_output(tmp_path, monkeypatch):
    assert ExportControl is not None, "export control API is not implemented"
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"
    started = threading.Event()
    processes = []

    class HangingPopen:
        def __init__(self, command, **kwargs):
            self.command = command
            self.temporary_path = Path(command[-1])
            self.returncode = None
            self.terminated = False

        def communicate(self, timeout=None):
            self.temporary_path.write_bytes(b"x" * 2048)
            started.set()
            raise subprocess.TimeoutExpired(self.command, timeout)

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.returncode = -15
            return self.returncode

    def start_process(*args, **kwargs):
        process = HangingPopen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", start_process)
    control = ExportControl()
    request = ExportRequest(
        ffmpeg="ffmpeg.exe",
        ffprobe="ffprobe.exe",
        input_path=source,
        output_path=output,
        start="00:00:02.000",
        end="00:00:04.000",
        mode="encode",
        overwrite=False,
    )
    results = []
    thread = threading.Thread(
        target=lambda: results.append(run_clip_export(request, control))
    )

    thread.start()
    assert started.wait(timeout=1)
    control.cancel()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert results[0].status == "canceled"
    assert processes[0].terminated
    assert not output.exists()
    assert not list(tmp_path.glob("clip.*.part.mp4"))
