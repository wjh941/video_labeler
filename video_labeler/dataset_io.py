"""Additional dataset exports that keep CSV compatibility untouched."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .models import ClipRecord


def write_clip_jsonl(path: Path, records: Sequence[ClipRecord]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(
                json.dumps(
                    {
                        "source": record.source,
                        "start_seconds": record.start_seconds,
                        "end_seconds": record.end_seconds,
                        "output": record.output,
                        "behaviors": list(record.behaviors),
                        "polarity": record.polarity,
                        "lighting": record.lighting,
                        "sequence": record.sequence,
                        "status": record.status,
                        "error": record.error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_clip_yolo(directory: Path, records: Sequence[ClipRecord]) -> None:
    target = Path(directory)
    labels_dir = target / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    classes = list(
        dict.fromkeys(tag for record in records for tag in record.behaviors)
    )
    class_ids = {tag: index for index, tag in enumerate(classes)}
    (target / "classes.txt").write_text(
        "".join(f"{tag}\n" for tag in classes), encoding="utf-8"
    )
    for record in records:
        label_path = labels_dir / f"{Path(record.output).stem}.txt"
        label_path.write_text(
            "".join(f"{class_ids[tag]}\n" for tag in record.behaviors),
            encoding="utf-8",
        )
