import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSignalBlocker, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea, QSlider, QSplitter

from video_labeler.models import (
    BEHAVIOR_LABELS,
    LIGHTING_VALUES,
    POLARITIES,
    ClipRecord,
)

try:
    from video_labeler.ui.main_window import MainWindow
except ImportError:
    MainWindow = None


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_main_window_uses_chinese_workflow_copy_and_keeps_tag_values(qt_app):
    window = MainWindow()

    assert window.windowTitle() == "视频片段标注工具"
    assert window.open_video_button.text() == "导入视频"
    assert window.import_csv_button.text() == "导入 CSV"
    assert window.output_folder_button.text() == "选择输出文件夹"
    assert window.export_button.text() == "批量导出"
    assert window.add_button.text() == "添加片段"
    assert window.cancel_export_button.text() == "取消导出"
    assert window.task_table.horizontalHeaderItem(0).text() == "编号"
    assert window.behavior_checks[BEHAVIOR_LABELS[0]].text() == "strangers_climbs"
    assert window.polarity_combo.itemText(0) == "pos"
    assert window.lighting_combo.itemText(0) == "daytime"


def test_task_table_displays_chinese_status_without_changing_record_status(qt_app):
    window = MainWindow()
    statuses = ("queued", "ok", "skip", "fail", "canceled")
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=1,
            end_seconds=2,
            output=f"clip-{index}.mp4",
            sequence=index,
            status=status,
        )
        for index, status in enumerate(statuses, start=1)
    ]

    window._refresh_table()

    assert [window.task_table.item(row, 8).text() for row in range(5)] == [
        "排队中",
        "成功",
        "已跳过",
        "失败",
        "已取消",
    ]
    assert [record.status for record in window.records] == list(statuses)


def test_duplicate_filename_error_uses_chinese_context_and_keeps_filename(
    qt_app, monkeypatch
):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=1,
            end_seconds=2,
            output="first.mp4",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=3,
            output="second.mp4",
            sequence=2,
        ),
    ]
    window._refresh_table()
    with QSignalBlocker(window.task_table):
        window.task_table.item(1, 7).setText("first.mp4")
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )

    window._table_cell_changed(1, 7)

    assert messages == [("文件名重复", "输出文件名重复：first.mp4")]


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
