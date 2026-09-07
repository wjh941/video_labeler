from pathlib import Path

import pytest

from video_labeler.models import ClipRecord
from video_labeler.plugin_api import (
    export_with, get_exporter, list_exporters, register_exporter,
)
from video_labeler.builtin_exporters import register_builtin_exporters


class Exporter:
    name = "test"
    version = "1"

    def export(self, records, destination: Path):
        (destination / "count.txt").write_text(str(len(records)), encoding="utf-8")


def test_export_with_validates_and_calls_plugin(tmp_path):
    export_with(Exporter(), [ClipRecord("a", 0, 1, "a.mp4")], tmp_path / "out")
    assert (tmp_path / "out" / "count.txt").read_text(encoding="utf-8") == "1"


def test_export_with_rejects_invalid_plugin(tmp_path):
    with pytest.raises(ValueError):
        export_with(object(), [], tmp_path / "out")


def test_registry_lists_and_runs_builtins(tmp_path):
    register_builtin_exporters()
    assert ("jsonl", "1") in list_exporters()
    register_exporter(Exporter(), replace=True)
    assert get_exporter("test").version == "1"
