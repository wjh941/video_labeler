import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QSlider, QSplitter

try:
    from video_labeler.ui.main_window import MainWindow
except ImportError:
    MainWindow = None


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
