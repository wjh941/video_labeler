from pathlib import Path
import subprocess
import threading

import pytest

try:
    from video_labeler.ffmpeg_service import (
        ExportControl,
        ExportRequest,
        build_command,
        format_seconds,
        parse_time_to_seconds,
        resolve_ffprobe,
        run_clip_export,
        temporary_output_path,
        validate_output_media,
    )
except ImportError:
    ExportControl = None
    ExportRequest = None
    build_command = None
    format_seconds = None
    parse_time_to_seconds = None
    resolve_ffprobe = None
    run_clip_export = None
    temporary_output_path = None
    validate_output_media = None


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


def test_resolve_ffprobe_uses_sibling_of_configured_ffmpeg(tmp_path):
    assert resolve_ffprobe is not None, "ffprobe resolution API is not implemented"
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"")
    ffprobe.write_bytes(b"")

    assert resolve_ffprobe(str(ffmpeg)) == str(ffprobe)


def test_resolve_ffprobe_uses_path_for_unconfigured_ffmpeg(monkeypatch):
    assert resolve_ffprobe is not None, "ffprobe resolution API is not implemented"
    monkeypatch.setattr("video_labeler.ffmpeg_service.shutil.which", lambda _: "ffprobe")

    assert resolve_ffprobe("") == "ffprobe"


def test_temporary_output_path_keeps_mp4_extension(tmp_path):
    assert temporary_output_path is not None, "temporary output API is not implemented"

    first = temporary_output_path(tmp_path / "clip.mp4")
    second = temporary_output_path(tmp_path / "clip.mp4")

    assert first.parent == tmp_path
    assert first.name.startswith("clip.")
    assert first.name.endswith(".part.mp4")
    assert first != second


def test_temporary_output_path_is_unique_for_simultaneous_calls(tmp_path):
    assert temporary_output_path is not None, "temporary output API is not implemented"
    output_path = tmp_path / "clip.mp4"
    paths = []
    barrier = threading.Barrier(2)

    def create_temporary_path():
        barrier.wait()
        paths.append(temporary_output_path(output_path))

    first = threading.Thread(target=create_temporary_path)
    second = threading.Thread(target=create_temporary_path)
    first.start()
    second.start()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(set(paths)) == 2


def test_validate_output_media_rejects_missing_video_stream(tmp_path, monkeypatch):
    assert validate_output_media is not None, "media validation API is not implemented"
    path = tmp_path / "clip.part.mp4"
    path.write_bytes(b"x" * 2048)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, '{"format":{"duration":"2.0"},"streams":[]}', ""
        ),
    )

    with pytest.raises(RuntimeError, match="video stream"):
        validate_output_media("ffprobe.exe", path, 2.0)


def test_validate_output_media_accepts_video_within_duration_tolerance(
    tmp_path, monkeypatch
):
    assert validate_output_media is not None, "media validation API is not implemented"
    path = tmp_path / "clip.part.mp4"
    path.write_bytes(b"x" * 2048)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            '{"format":{"duration":"2.1"},"streams":[{"codec_type":"video"}]}',
            "",
        ),
    )

    validate_output_media("ffprobe.exe", path, 2.0)


def test_validate_output_media_rejects_duration_outside_tolerance(
    tmp_path, monkeypatch
):
    assert validate_output_media is not None, "media validation API is not implemented"
    path = tmp_path / "clip.part.mp4"
    path.write_bytes(b"x" * 2048)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            '{"format":{"duration":"2.3"},"streams":[{"codec_type":"video"}]}',
            "",
        ),
    )

    with pytest.raises(RuntimeError, match="duration"):
        validate_output_media("ffprobe.exe", path, 2.0)


def test_run_clip_export_publishes_valid_temporary_output(tmp_path, monkeypatch):
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"

    class SuccessfulPopen:
        def __init__(self, command, **kwargs):
            self.command = command
            self.temporary_path = Path(command[-1])
            self.returncode = None

        def communicate(self, timeout=None):
            assert self.temporary_path.parent == output.parent
            assert self.temporary_path.name.startswith("clip.")
            assert self.temporary_path.name.endswith(".part.mp4")
            assert not output.exists()
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


def test_run_clip_export_does_not_publish_when_canceled_during_validation(
    tmp_path, monkeypatch
):
    assert ExportControl is not None, "export process control API is not implemented"
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"
    validation_started = threading.Event()
    allow_validation_to_finish = threading.Event()

    class SuccessfulPopen:
        def __init__(self, command, **kwargs):
            self.command = command
            self.temporary_path = Path(command[-1])
            self.returncode = None

        def communicate(self, timeout=None):
            self.temporary_path.write_bytes(b"x" * 2048)
            self.returncode = 0
            return "", ""

        def poll(self):
            return self.returncode

    def run_ffprobe(*args, **kwargs):
        validation_started.set()
        assert allow_validation_to_finish.wait(timeout=1)
        return subprocess.CompletedProcess(
            args,
            0,
            '{"format":{"duration":"2.0"},"streams":[{"codec_type":"video"}]}',
            "",
        )

    monkeypatch.setattr(subprocess, "Popen", SuccessfulPopen)
    monkeypatch.setattr(subprocess, "run", run_ffprobe)
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
    result = []
    thread = threading.Thread(
        target=lambda: result.append(run_clip_export(request, control))
    )

    thread.start()
    assert validation_started.wait(timeout=1)
    control.cancel()
    allow_validation_to_finish.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert result[0].status == "canceled"
    assert not output.exists()
    assert not list(tmp_path.glob("clip.*.part.mp4"))


def test_run_clip_export_does_not_publish_when_cancellation_wins_at_publication(
    tmp_path, monkeypatch
):
    assert ExportControl is not None, "export process control API is not implemented"
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

    class CancelAtPublicationBoundary(ExportControl):
        def publish(self, temporary_path, output_path):
            self.cancel()
            return super().publish(temporary_path, output_path)

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
        ),
        CancelAtPublicationBoundary(),
    )

    assert result.status == "canceled"
    assert not output.exists()
    assert not list(tmp_path.glob("clip.*.part.mp4"))


@pytest.mark.parametrize("ffmpeg_returncode, has_video", [(1, True), (0, False)])
def test_run_clip_export_removes_temporary_output_after_failure(
    tmp_path, monkeypatch, ffmpeg_returncode, has_video
):
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"

    class FailingPopen:
        def __init__(self, command, **kwargs):
            self.command = command
            self.temporary_path = Path(command[-1])
            self.returncode = None

        def communicate(self, timeout=None):
            self.temporary_path.write_bytes(b"x" * 2048)
            self.returncode = ffmpeg_returncode
            return "", "ffmpeg failed" if ffmpeg_returncode else ""

        def poll(self):
            return self.returncode

    streams = '[{"codec_type":"video"}]' if has_video else "[]"
    monkeypatch.setattr(subprocess, "Popen", FailingPopen)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, '{"format":{"duration":"2.0"},"streams":' + streams + "}", ""
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

    assert result.status == "fail"
    assert not output.exists()
    assert not list(tmp_path.glob("clip.*.part.mp4"))


def test_run_clip_export_cancels_managed_process_and_removes_temporary_output(
    tmp_path, monkeypatch
):
    assert ExportControl is not None, "export process control API is not implemented"
    assert run_clip_export is not None, "clip export execution API is not implemented"
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "clip.mp4"
    started = threading.Event()

    class HangingPopen:
        def __init__(self, command, **kwargs):
            self.command = command
            self.temporary_path = Path(command[-1])
            self.returncode = None
            self.terminated = False
            self.killed = False

        def communicate(self, timeout=None):
            self.temporary_path.write_bytes(b"x" * 2048)
            started.set()
            raise subprocess.TimeoutExpired(self.command, timeout)

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired(self.command, timeout)
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    processes = []

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
    result = []
    thread = threading.Thread(
        target=lambda: result.append(run_clip_export(request, control))
    )

    thread.start()
    assert started.wait(timeout=1)
    control.cancel()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert result[0].status == "canceled"
    assert not output.exists()
    assert not list(tmp_path.glob("clip.*.part.mp4"))
    assert processes[0].killed
