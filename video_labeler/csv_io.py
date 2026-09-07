import csv
import json
import math
from pathlib import Path
from typing import Sequence

from .models import ClipRecord
from .naming import parse_filename


CSV_REQUIRED_FIELDS = ("source", "start", "end", "output")
CSV_FIELDS = (*CSV_REQUIRED_FIELDS, "note")
FULL_CSV_FIELDS = (
    "source", "start_seconds", "end_seconds", "output", "behaviors",
    "polarity", "lighting", "sequence", "status", "error", "note",
    "review_status", "reviewer", "reviewed_at", "review_comment", "rejection_reason"
)


def _parse_seconds(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("empty time")
    if ":" not in text:
        seconds = float(text)
    else:
        parts = text.split(":")
        if len(parts) > 3:
            raise ValueError(f"invalid time: {value}")

        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    if not math.isfinite(seconds):
        raise ValueError("time must be finite")
    return seconds


def _format_seconds(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("time must be finite")
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
                    "note": record.note,
                }
            )


def write_full_clip_csv(path: Path, records: Sequence[ClipRecord]) -> None:
    """Write a lossless interchange CSV containing every clip field."""
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FULL_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({
                "source": record.source,
                "start_seconds": record.start_seconds,
                "end_seconds": record.end_seconds,
                "output": record.output,
                "behaviors": json.dumps(list(record.behaviors), ensure_ascii=False),
                "polarity": record.polarity,
                "lighting": record.lighting,
                "sequence": record.sequence,
                "status": record.status,
                "error": record.error,
                "note": record.note,
                "review_status": record.review_status,
                "reviewer": record.reviewer,
                "reviewed_at": record.reviewed_at,
                "review_comment": record.review_comment,
                "rejection_reason": record.rejection_reason,
            })


def read_full_clip_csv(path: Path) -> list[ClipRecord]:
    """Read the lossless interchange CSV without relying on filenames."""
    import json
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if set(FULL_CSV_FIELDS) - set(reader.fieldnames or ()):
            raise ValueError("full CSV missing columns")
        records = []
        for index, row in enumerate(reader, start=2):
            try:
                start = float(row["start_seconds"])
                end = float(row["end_seconds"])
                behaviors = json.loads(row["behaviors"])
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"full CSV row {index} is invalid") from error
            if not math.isfinite(start) or not math.isfinite(end) or end <= start:
                raise ValueError(f"full CSV row {index} has an invalid time range")
            if not isinstance(behaviors, list) or not all(isinstance(tag, str) for tag in behaviors):
                raise ValueError(f"full CSV row {index} behaviors must be a JSON list")
            review_status = row.get("review_status") or "pending"
            if review_status not in {"pending", "approved", "rejected"}:
                raise ValueError(f"full CSV row {index} has an invalid review status")
            records.append(ClipRecord(
                source=row["source"], start_seconds=start, end_seconds=end,
                output=row["output"], behaviors=tuple(behaviors),
                polarity=row["polarity"], lighting=row["lighting"],
                sequence=int(row["sequence"]), status=row["status"],
                error=row["error"], note=row["note"],
                review_status=review_status,
                reviewer=row.get("reviewer", ""),
                reviewed_at=row.get("reviewed_at", ""),
                review_comment=row.get("review_comment", ""),
                rejection_reason=row.get("rejection_reason", ""),
            ))
    return records


def read_clip_csv(path: Path) -> list[ClipRecord]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = set(reader.fieldnames or ())
        missing = set(CSV_REQUIRED_FIELDS) - fieldnames
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")

        records = []
        for index, row in enumerate(reader, start=2):
            if not any(
                (row.get(field) or "").strip() for field in CSV_REQUIRED_FIELDS
            ):
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

            parsed = parse_filename(output)
            records.append(
                ClipRecord(
                    source=source,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    output=output,
                    behaviors=parsed.behaviors if parsed else (),
                    polarity=parsed.polarity if parsed else "",
                    lighting=parsed.lighting if parsed else "",
                    sequence=parsed.sequence if parsed else 0,
                    note=row.get("note") or "",
                )
            )

    return records
