import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMessageBox,
    QScrollArea,
    QSlider,
    QSplitter,
)

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


def test_editable_metadata_combos_include_custom_action(qt_app):
    window = MainWindow()

    assert window.view_combo.itemText(window.view_combo.count() - 1) == "自定义..."
    assert window.polarity_combo.itemText(window.polarity_combo.count() - 1) == "自定义..."
    assert window.lighting_combo.itemText(window.lighting_combo.count() - 1) == "自定义..."
    assert [window.mode_combo.itemText(index) for index in range(window.mode_combo.count())] == [
        "encode",
        "copy",
    ]
    assert [window.speed_combo.itemText(index) for index in range(window.speed_combo.count())] == [
        "0.5x",
        "1.0x",
        "1.5x",
        "2.0x",
    ]


@pytest.mark.parametrize(
    ("combo_name", "entered", "expected"),
    (
        ("view_combo", " DoorWay ", "doorway"),
        ("polarity_combo", " Needs_Review ", "needs_review"),
        ("lighting_combo", " Night_Red ", "night_red"),
    ),
)
def test_custom_metadata_prompt_normalizes_adds_and_selects_value(
    qt_app, monkeypatch, combo_name, entered, expected
):
    window = MainWindow()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: (entered, True)),
    )
    combo = getattr(window, combo_name)

    combo.setCurrentIndex(combo.count() - 1)

    assert combo.currentText() == expected
    assert combo.itemText(combo.count() - 2) == expected
    assert combo.itemText(combo.count() - 1) == "自定义..."


def test_custom_metadata_prompt_selects_an_existing_value_without_duplicate(
    qt_app, monkeypatch
):
    window = MainWindow()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: (" PANORAMA ", True)),
    )
    initial_count = window.view_combo.count()

    window.view_combo.setCurrentIndex(window.view_combo.count() - 1)

    assert window.view_combo.currentText() == "panorama"
    assert window.view_combo.count() == initial_count


def test_invalid_custom_view_restores_previous_selection(qt_app, monkeypatch):
    window = MainWindow()
    messages = []
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: ("indoor_room", True)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )

    window.view_combo.setCurrentText("panorama")
    window.view_combo.setCurrentIndex(window.view_combo.count() - 1)

    assert window.view_combo.currentText() == "panorama"
    assert messages
    assert "仅支持小写英文和数字" in messages[0][1]


def test_canceling_custom_value_restores_previous_selection(qt_app, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: ("", False)),
    )

    window.polarity_combo.setCurrentText("neg")
    window.polarity_combo.setCurrentIndex(window.polarity_combo.count() - 1)

    assert window.polarity_combo.currentText() == "neg"


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


def test_invalid_filename_error_uses_chinese_context_and_keeps_diagnostic(
    qt_app, monkeypatch
):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=1,
            end_seconds=2,
            output="valid.mp4",
            sequence=1,
        )
    ]
    window._refresh_table()
    with QSignalBlocker(window.task_table):
        window.task_table.item(0, 7).setText("bad/name.mp4")
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )

    window._table_cell_changed(0, 7)

    assert messages == [
        (
            "文件名无效",
            "输出文件名无效：bad/name.mp4；"
            "output filename contains invalid Windows characters",
        )
    ]


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
