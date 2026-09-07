"""Stable extension API and registry for dataset exporters."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol
import importlib.util

from .models import ClipRecord


class ClipExporter(Protocol):
    name: str
    version: str

    def export(self, records: Sequence[ClipRecord], destination: Path) -> None:
        """Export records into destination."""


def validate_exporter(exporter: ClipExporter) -> None:
    if not isinstance(getattr(exporter, "name", None), str) or not exporter.name.strip():
        raise ValueError("exporter name must be a non-empty string")
    if not isinstance(getattr(exporter, "version", None), str) or not exporter.version.strip():
        raise ValueError("exporter version must be a non-empty string")
    if not callable(getattr(exporter, "export", None)):
        raise ValueError("exporter must provide an export method")


_EXPORTERS: dict[str, ClipExporter] = {}


def register_exporter(exporter: ClipExporter, *, replace: bool = False) -> None:
    validate_exporter(exporter)
    key = exporter.name.strip()
    if key in _EXPORTERS and not replace:
        raise ValueError(f"exporter already registered: {key}")
    _EXPORTERS[key] = exporter


def get_exporter(name: str) -> ClipExporter:
    try:
        return _EXPORTERS[name]
    except KeyError as error:
        raise KeyError(f"unknown exporter: {name}") from error


def list_exporters() -> tuple[tuple[str, str], ...]:
    return tuple((name, _EXPORTERS[name].version) for name in sorted(_EXPORTERS))


def load_plugin_file(path: Path) -> tuple[str, ...]:
    source = Path(path)
    if source.suffix.lower() != ".py":
        raise ValueError("plugin file must be a Python file")
    module_name = f"video_labeler_plugin_{abs(hash(source.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load plugin: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hook = getattr(module, "register", None)
    if hook is None or not callable(hook):
        raise ValueError("plugin must expose register()")
    before = set(_EXPORTERS)
    hook(register_exporter)
    return tuple(sorted(set(_EXPORTERS) - before))


def export_with(exporter: ClipExporter, records: Sequence[ClipRecord], destination: Path) -> None:
    validate_exporter(exporter)
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    exporter.export(records, target)
