from pathlib import Path

import pytest

from video_labeler.models import ClipRecord
from video_labeler.plugin_api import export_with


class Exporter:
    name = "test"

    def export(self, records, destination: Path):
        (destination / "count.txt").write_text(str(len(records)), encoding="utf-8")


def test_export_with_validates_and_calls_plugin(tmp_path):
    export_with(Exporter(), [ClipRecord("a", 0, 1, "a.mp4")], tmp_path / "out")
    assert (tmp_path / "out" / "count.txt").read_text(encoding="utf-8") == "1"


def test_export_with_rejects_invalid_plugin(tmp_path):
    with pytest.raises(ValueError):
        export_with(object(), [], tmp_path / "out")
