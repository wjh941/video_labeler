from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


MIN_VALID_OUTPUT_BYTES = 1024


@dataclass(frozen=True)
class ExportRequest:
    ffmpeg: str
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


def run_clip_export(request: ExportRequest) -> ExportResult:
    output_name = request.output_path.name
    try:
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
            request.output_path,
            request.start,
            request.end,
            request.mode,
            request.overwrite,
        )
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        if not is_valid_output(request.output_path):
            raise RuntimeError(
                "FFmpeg finished but output is missing or too small: "
                f"{request.output_path}"
            )
        return ExportResult(status="ok", output=output_name)
    except Exception as error:
        return ExportResult(status="fail", output=output_name, error=str(error))
