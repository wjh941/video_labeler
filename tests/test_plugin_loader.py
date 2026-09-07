from video_labeler.plugin_api import get_exporter, load_plugin_directory, load_plugin_file, export_with
from video_labeler.models import ClipRecord


def _write_plugin(path, name):
    path.write_text(
        f"class Exporter:\n    name = '{name}'\n    version = '1'\n    def export(self, records, destination):\n        pass\ndef register(register_exporter):\n    register_exporter(Exporter())\n",
        encoding="utf-8",
    )


def test_load_plugin_file_registers_exporter(tmp_path):
    plugin = tmp_path / "custom.py"
    _write_plugin(plugin, "custom-file")
    assert load_plugin_file(plugin) == ("custom-file",)
    assert get_exporter("custom-file").version == "1"


def test_load_plugin_directory_skips_private_files(tmp_path):
    _write_plugin(tmp_path / "one.py", "one")
    _write_plugin(tmp_path / "two.py", "two")
    _write_plugin(tmp_path / "_private.py", "private")
    loaded = load_plugin_directory(tmp_path)
    assert loaded == ("one", "two")
