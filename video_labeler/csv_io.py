import csv
from pathlib import Path
from typing import Sequence

from .models import ClipRecord
from .naming import parse_filename, validate_labels


CSV_FIELDS = (
    "source",
    "start",
    "end",
    "output",
    "behaviors",
    "polarity",
    "lighting",
    "sequence",
    "status",
    "error",
)
LEGACY_CSV_FIELDS = ("source", "start", "end", "output")


def _parse_seconds(value: str) -> float:
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


def _format_seconds(value: float) -> str:
    if value < 0:
        raise ValueError("time cannot be negative")

    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"


def write_clip_csv(path: Path, records: Sequence[ClipRecord]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "source": record.source,
                    "start": _format_seconds(record.start_seconds),
                    "end": _format_seconds(record.end_seconds),
                    "output": record.output,
                    "behaviors": "+".join(record.behaviors),
                    "polarity": record.polarity,
                    "lighting": record.lighting,
                    "sequence": record.sequence,
                    "status": record.status,
                    "error": record.error,
                }
            )


def _labels_from_row(
    row: dict[str, str | None], index: int, output: str
) -> tuple[tuple[str, ...], str, str, int]:
    explicit = tuple(
        (row.get(name) or "").strip()
        for name in ("behaviors", "polarity", "lighting", "sequence")
    )
    if any(explicit):
        if not all(explicit):
            raise ValueError(f"CSV row {index} has incomplete label values")
        behaviors = tuple(explicit[0].split("+"))
        sequence = int(explicit[3])
        validate_labels(behaviors, explicit[1], explicit[2], sequence)
        return behaviors, explicit[1], explicit[2], sequence

    parsed = parse_filename(output)
    if parsed is None:
        return (), "", "", 0
    return parsed.behaviors, parsed.polarity, parsed.lighting, parsed.sequence


def read_clip_csv(path: Path) -> list[ClipRecord]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = set(reader.fieldnames or ())
        missing = set(LEGACY_CSV_FIELDS) - fieldnames
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")

        records = []
        for index, row in enumerate(reader, start=2):
            if not any((row.get(field) or "").strip() for field in CSV_FIELDS):
                continue

            source = (row.get("source") or "").strip()
            start_text = (row.get("start") or "").strip()
            end_text = (row.get("end") or "").strip()
            output = (row.get("output") or "").strip()
            if not all((source, start_text, end_text, output)):
                raise ValueError(f"CSV row {index} has an empty required value")

            start_seconds = _parse_seconds(start_text)
            end_seconds = _parse_seconds(end_text)
            if end_seconds <= start_seconds:
                raise ValueError(f"CSV row {index} ends before it starts")

            behaviors, polarity, lighting, sequence = _labels_from_row(
                row, index, output
            )
            records.append(
                ClipRecord(
                    source=source,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    output=output,
                    behaviors=behaviors,
                    polarity=polarity,
                    lighting=lighting,
                    sequence=sequence,
                    status=(row.get("status") or "queued").strip() or "queued",
                    error=(row.get("error") or "").strip(),
                )
            )

    return records
