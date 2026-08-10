import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QSlider, QSplitter

try:
    from video_labeler.ui import main_window as main_window_module
    from video_labeler.models import ClipRecord, ProjectMetadata
    from video_labeler.project_io import ProjectState
    from video_labeler.ui.main_window import MainWindow
except ImportError:
    MainWindow = None


class _FakeSignal:
    def connect(self, _callback):
        pass


class FakeExportWorker:
    kwargs = {}

    def __init__(self, **kwargs):
        type(self).kwargs = kwargs
        self.clip_finished = _FakeSignal()
        self.progress = _FakeSignal()
        self.export_completed = _FakeSignal()

    def isRunning(self):
        return False

    def start(self):
        pass


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_adding_clips_generates_sequential_task_filenames(qt_app, tmp_path):
    assert MainWindow is not None, "annotation main window is not implemented"
    window = MainWindow()
    source_path = Path(tmp_path / "cam02_20260729.mp4")

    window.set_source_path(source_path)
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("panorama")
    window.behavior_checks["dog_out"].setChecked(True)
    window.polarity_combo.setCurrentText("pos")
    window.lighting_combo.setCurrentText("night_full_color")
    window.set_clip_range(2.5, 4.0)
    window.add_or_update_clip()

    window.set_clip_range(5.0, 7.0)
    window.add_or_update_clip()

    assert [record.output for record in window.records] == [
        "20260729-cam02_panorama-dog_out-pos-night_full_color-001.mp4",
        "20260729-cam02_panorama-dog_out-pos-night_full_color-002.mp4",
    ]
    assert [record.source for record in window.records] == [
        "cam02_20260729.mp4",
        "cam02_20260729.mp4",
    ]


def test_main_window_uses_a_draggable_timeline_slider(qt_app):
    assert MainWindow is not None, "annotation main window is not implemented"
    window = MainWindow()

    assert isinstance(window.timeline_slider, QSlider)


def test_main_window_uses_resizable_workspace_splitters(qt_app):
    window = MainWindow()

    assert isinstance(window.workspace_splitter, QSplitter)
    assert window.workspace_splitter.orientation() == Qt.Orientation.Vertical
    assert isinstance(window.editor_splitter, QSplitter)
    assert window.editor_splitter.orientation() == Qt.Orientation.Horizontal


def test_annotation_controls_are_wrapped_in_a_scroll_area(qt_app):
    window = MainWindow()

    assert isinstance(window.annotation_scroll, QScrollArea)
    assert window.annotation_scroll.widget() is window.annotation_panel
    assert window.annotation_scroll.widgetResizable()


def test_add_clip_action_appears_before_behavior_choices(qt_app):
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    qt_app.processEvents()

    add_clip_y = window.add_button.mapTo(
        window.annotation_panel, QPoint(0, 0)
    ).y()
    behaviors_y = window.behaviors_group.mapTo(
        window.annotation_panel, QPoint(0, 0)
    ).y()

    assert add_clip_y < behaviors_y


def test_start_export_passes_resolved_ffprobe(qt_app, tmp_path, monkeypatch):
    window = MainWindow()
    source = tmp_path / "cam02.mp4"
    source.write_bytes(b"source")
    output_dir = tmp_path / "out"
    window.source_path = source
    window.output_dir = output_dir
    window.records = [
        ClipRecord(
            source="cam02.mp4",
            start_seconds=2.5,
            end_seconds=4.0,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
        )
    ]
    FakeExportWorker.kwargs = {}

    monkeypatch.setattr(main_window_module, "resolve_ffmpeg", lambda _path: "ffmpeg.exe")
    monkeypatch.setattr(
        main_window_module,
        "resolve_ffprobe",
        lambda _ffmpeg: "ffprobe.exe",
        raising=False,
    )
    monkeypatch.setattr(main_window_module, "ExportWorker", FakeExportWorker)

    window.start_export()

    assert FakeExportWorker.kwargs["ffprobe"] == "ffprobe.exe"


def test_project_actions_are_available(qt_app):
    window = MainWindow()

    assert window.open_project_button.text() == "Open Project"
    assert window.save_project_button.text() == "Save Project"


def test_apply_project_state_restores_annotation_data(qt_app, tmp_path):
    window = MainWindow()
    state = ProjectState(
        source_path=tmp_path / "cam02.mp4",
        output_dir=tmp_path / "out",
        metadata=ProjectMetadata("20260729", "cam02", "panorama"),
        records=[
            ClipRecord(
                source="cam02.mp4",
                start_seconds=2.5,
                end_seconds=4.0,
                output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            )
        ],
    )

    window.apply_project_state(state)

    assert window.source_path == state.source_path
    assert window.output_dir == state.output_dir
    assert window.records == state.records
    assert window.date_edit.text() == "20260729"
    assert window.camera_edit.text() == "cam02"
    assert window.view_combo.currentText() == "panorama"
    assert window.source_label.text() == "cam02.mp4"
    assert window.output_folder_label.text() == str(tmp_path / "out")
    assert window.task_table.rowCount() == 1


def test_start_export_rejects_mismatched_sources_before_creating_worker(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    source = tmp_path / "cam02.mp4"
    source.write_bytes(b"source")
    window.source_path = source
    window.output_dir = tmp_path / "out"
    window.records = [
        ClipRecord(
            source="cam03.mp4",
            start_seconds=2.5,
            end_seconds=4.0,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
        )
    ]
    errors = []
    FakeExportWorker.kwargs = {}

    monkeypatch.setattr(window, "_show_error", lambda title, message: errors.append((title, message)))
    monkeypatch.setattr(main_window_module, "ExportWorker", FakeExportWorker)

    window.start_export()

    assert FakeExportWorker.kwargs == {}
    assert errors == [
        (
            "Cannot start export",
            "All clips must use the selected source video; mismatched rows: cam03.mp4",
        )
    ]
