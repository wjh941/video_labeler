from video_labeler.plugin_api import get_exporter, load_plugin_file, export_with
from video_labeler.models import ClipRecord


def test_load_plugin_file_registers_exporter(tmp_path):
    plugin = tmp_path / "custom.py"
    plugin.write_text(
        "class Exporter:\n"
        "    name = 'custom-file'\n"
        "    version = '1'\n"
        "    def export(self, records, destination):\n"
        "        (destination / 'ok.txt').write_text('ok', encoding='utf-8')\n"
        "def register(register_exporter):\n"
        "    register_exporter(Exporter())\n",
        encoding="utf-8",
    )
    assert load_plugin_file(plugin) == ("custom-file",)
    export_with(get_exporter("custom-file"), [ClipRecord("a", 0, 1, "a")], tmp_path / "out")
    assert (tmp_path / "out" / "ok.txt").exists()
