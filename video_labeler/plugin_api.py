"""Small stable extension API for third-party dataset exporters."""

from __future__ import annotations

from typing import Protocol
from pathlib import Path
from collections.abc import Sequence

from .models import ClipRecord


class ClipExporter(Protocol):
    name: str

    def export(self, records: Sequence[ClipRecord], destination: Path) -> None:
        """Export records into destination."""


def validate_exporter(exporter: ClipExporter) -> None:
    if not isinstance(getattr(exporter, "name", None), str) or not exporter.name.strip():
        raise ValueError("exporter name must be a non-empty string")
    if not callable(getattr(exporter, "export", None)):
        raise ValueError("exporter must provide an export method")


def export_with(exporter: ClipExporter, records: Sequence[ClipRecord], destination: Path) -> None:
    validate_exporter(exporter)
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    exporter.export(records, target)
