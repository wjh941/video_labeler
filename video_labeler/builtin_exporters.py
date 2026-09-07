"""Built-in exporters exposed through the plugin registry."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

from .dataset_io import write_clip_jsonl, write_clip_yolo
from .models import ClipRecord
from .plugin_api import register_exporter


class JsonlExporter:
    name = "jsonl"
    version = "1"

    def export(self, records: Sequence[ClipRecord], destination: Path) -> None:
        write_clip_jsonl(Path(destination) / "clips.jsonl", records)


class YoloExporter:
    name = "yolo"
    version = "1"

    def export(self, records: Sequence[ClipRecord], destination: Path) -> None:
        write_clip_yolo(destination, records)


def register_builtin_exporters() -> None:
    for exporter in (JsonlExporter(), YoloExporter()):
        register_exporter(exporter, replace=True)
