from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import threading
import uuid


MIN_VALID_OUTPUT_BYTES = 1024


@dataclass(frozen=True)
class ExportRequest:
    ffmpeg: str
    ffprobe: str
    input_path: Path
    output_path: Path
    start: str
    end: str
    mode: str
    overwrite: bool


@dataclass(frozen=True)
class ExportResult:
    status: str
    output: str = ""
    error: str = ""


def parse_time_to_seconds(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("empty time")
    if ":" not in text:
        return float(text)

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid time: {value}")

    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def format_seconds(value: float) -> str:
    if value < 0:
        raise ValueError("time cannot be negative")

    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"


def build_command(
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    start: str,
    end: str,
    mode: str,
    overwrite: bool,
) -> list[str]:
    start_seconds = parse_time_to_seconds(start)
    end_seconds = parse_time_to_seconds(end)
    if end_seconds <= start_seconds:
        raise ValueError(f"end must be later than start: {start} -> {end}")

    overwrite_arg = "-y" if overwrite else "-n"
    if mode == "copy":
        return [
            ffmpeg,
            "-hide_banner",
            overwrite_arg,
            "-i",
            str(input_path),
            "-ss",
            start,
            "-to",
            end,
            "-map",
            "0",
            "-c",
            "copy",
            str(output_path),
        ]

    if mode == "encode":
        duration = end_seconds - start_seconds
        pre_seek = max(0.0, start_seconds - 10)
        offset = start_seconds - pre_seek
        return [
            ffmpeg,
            "-hide_banner",
            overwrite_arg,
            "-ss",
            format_seconds(pre_seek),
            "-i",
            str(input_path),
            "-ss",
            f"{offset:.3f}",
            "-t",
            f"{duration:.3f}",
            "-map",
            "0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]

    raise ValueError("mode must be either 'encode' or 'copy'")


def is_valid_output(path: Path) -> bool:
    return path.is_file() and path.stat().st_size >= MIN_VALID_OUTPUT_BYTES


def resolve_ffmpeg(configured_path: str) -> str:
    configured_path = configured_path.strip()
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.is_file():
            return str(path)
        raise FileNotFoundError(f"configured FFmpeg path does not exist: {path}")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        return ffmpeg

    raise RuntimeError("FFmpeg was not found. Configure its executable path.")


def resolve_ffprobe(ffmpeg_path: str) -> str:
    configured_path = ffmpeg_path.strip()
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.is_file():
            ffprobe = path.with_name("ffprobe.exe")
            if ffprobe.is_file():
                return str(ffprobe)
            raise FileNotFoundError(
                f"configured FFprobe path does not exist: {ffprobe}"
            )

    ffprobe = shutil.which("ffprobe")
    if ffprobe is not None:
        return ffprobe

    raise RuntimeError("FFprobe was not found. Configure FFmpeg and ffprobe.")


def temporary_output_path(output_path: Path) -> Path:
    return output_path.with_name(
        f"{output_path.stem}.{uuid.uuid4().hex}.part{output_path.suffix}"
    )


def validate_output_media(
    ffprobe: str, path: Path, expected_duration: float
) -> None:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")

    payload = json.loads(completed.stdout)
    if not any(
        stream.get("codec_type") == "video" for stream in payload.get("streams", [])
    ):
        raise RuntimeError("output does not contain a video stream")

    duration = float(payload["format"]["duration"])
    tolerance = max(0.25, min(2.0, expected_duration * 0.10))
    if duration <= 0 or abs(duration - expected_duration) > tolerance:
        raise RuntimeError("output duration is outside the allowed tolerance")


class ExportControl:
    def __init__(self) -> None:
        self._canceled = threading.Event()
        self._processes: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._canceled.set()
        with self._lock:
            for process in tuple(self._processes):
                if process.poll() is None:
                    process.terminate()

    def is_canceled(self) -> bool:
        return self._canceled.is_set()

    def register(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.add(process)
            if self._canceled.is_set() and process.poll() is None:
                process.terminate()

    def unregister(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.discard(process)


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)


def _communicate_until_finished(
    process: subprocess.Popen[str], control: ExportControl | None
) -> tuple[str, str, bool]:
    while True:
        if control is not None and control.is_canceled():
            _stop_process(process)
            return "", "", True
        try:
            stdout, stderr = process.communicate(timeout=0.1)
            if control is not None and control.is_canceled():
                _stop_process(process)
                return stdout, stderr, True
            return stdout, stderr, False
        except subprocess.TimeoutExpired:
            continue


def run_clip_export(
    request: ExportRequest, control: ExportControl | None = None
) -> ExportResult:
    output_name = request.output_path.name
    temporary_path = temporary_output_path(request.output_path)
    try:
        if control is not None and control.is_canceled():
            return ExportResult(status="canceled", output=output_name)

        if request.output_path.exists() and not request.overwrite:
            if is_valid_output(request.output_path):
                return ExportResult(status="skip", output=output_name)
            raise FileExistsError(
                f"output exists but looks incomplete: {request.output_path}"
            )

        if not request.input_path.is_file():
            raise FileNotFoundError(f"source video not found: {request.input_path}")

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = build_command(
            request.ffmpeg,
            request.input_path,
            temporary_path,
            request.start,
            request.end,
            request.mode,
            request.overwrite,
        )
        process = subprocess.Popen(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if control is not None:
            control.register(process)
        try:
            stdout, stderr, canceled = _communicate_until_finished(process, control)
        finally:
            if control is not None:
                control.unregister(process)

        if canceled:
            return ExportResult(status="canceled", output=output_name)
        if control is not None and control.is_canceled():
            _stop_process(process)
            return ExportResult(status="canceled", output=output_name)
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or stdout.strip())
        if not is_valid_output(temporary_path):
            raise RuntimeError(
                "FFmpeg finished but output is missing or too small: "
                f"{temporary_path}"
            )
        expected_duration = parse_time_to_seconds(request.end) - parse_time_to_seconds(
            request.start
        )
        validate_output_media(request.ffprobe, temporary_path, expected_duration)
        if control is not None and control.is_canceled():
            return ExportResult(status="canceled", output=output_name)
        temporary_path.replace(request.output_path)
        return ExportResult(status="ok", output=output_name)
    except Exception as error:
        return ExportResult(status="fail", output=output_name, error=str(error))
    finally:
        temporary_path.unlink(missing_ok=True)
