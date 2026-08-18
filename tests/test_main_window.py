import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QItemSelectionModel,
    QPoint,
    QPointF,
    QSignalBlocker,
    Qt,
)
from PySide6.QtGui import QKeySequence, QMouseEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QGraphicsView,
    QGroupBox,
    QInputDialog,
    QMessageBox,
    QScrollArea,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QTableWidget,
)

from video_labeler.models import (
    BEHAVIOR_LABELS,
    LIGHTING_VALUES,
    POLARITIES,
    ClipRecord,
)
from video_labeler.ffmpeg_service import ExportResult

try:
    from video_labeler.ui.main_window import (
        BehaviorTagComboBox,
        CollapsibleGroupBox,
        MainWindow,
    )
except ImportError:
    BehaviorTagComboBox = None
    CollapsibleGroupBox = None
    MainWindow = None


APPROVED_PLAYBACK_RATE_ITEMS = [
    "0.25x",
    "0.5x",
    "0.75x",
    "1.0x",
    "1.5x",
    "2.0x",
    "3.0x",
    "4.0x",
    "自定义",
]


class PopupTrackingBehaviorTagComboBox(BehaviorTagComboBox):
    def __init__(self):
        super().__init__()
        self.popup_requests = 0

    def showPopup(self):
        self.popup_requests += 1


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _add_valid_clip(window: MainWindow, *, start: float, end: float, behavior: str) -> None:
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("pos")
    window.lighting_combo.setCurrentText("daytime")
    window.set_clip_range(start, end)
    window.behavior_checks[behavior].setChecked(True)
    window.add_or_update_clip()


def _wait_for_content_animation(
    qt_app, window: MainWindow, group: CollapsibleGroupBox | None = None
) -> None:
    group = group or window.behaviors_group
    for _ in range(100):
        qt_app.processEvents()
        if group._animation.state() != QAbstractAnimation.State.Running:
            return
        QTest.qWait(5)
    pytest.fail("行为标签折叠动画未完成")


def test_add_clip_prepares_next_clip_and_keeps_fixed_metadata(qt_app, tmp_path):
    window = MainWindow()
    source_path = tmp_path / "source.mp4"
    window.set_source_path(source_path)
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.behavior_checks["dog_out"].setChecked(True)
    window.behavior_checks["fall"].setChecked(True)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.note_edit.setText("review before export")
    window.set_clip_range(1.0, 2.0)

    window.add_or_update_clip()

    assert len(window.records) == 1
    assert window.records[0].note == "review before export"
    assert window.note_edit.text() == ""
    assert window.sequence_spin.value() == 2
    assert window.start_spin.value() == pytest.approx(2.0)
    assert window.end_spin.value() == pytest.approx(2.0)
    assert window.selected_behaviors() == ()
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window._editing_index is None
    assert window.add_button.text() == "添加片段"


def test_update_clip_prepares_next_clip_and_keeps_fixed_metadata(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.behavior_checks["dog_out"].setChecked(True)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.set_clip_range(1.0, 2.0)
    window.add_or_update_clip()

    window.task_table.selectRow(0)
    qt_app.processEvents()
    window.set_clip_range(1.0, 6.5)
    window.behavior_checks["fall"].setChecked(True)
    window.add_or_update_clip()

    assert len(window.records) == 1
    assert window.records[0].end_seconds == pytest.approx(6.5)
    assert window.sequence_spin.value() == 2
    assert window.start_spin.value() == pytest.approx(6.5)
    assert window.end_spin.value() == pytest.approx(6.5)
    assert window.selected_behaviors() == ()
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window._editing_index is None
    assert window.add_button.text() == "添加片段"


def test_selecting_clip_restores_all_annotation_fields(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=12.5,
            end_seconds=18.75,
            output=(
                "20260729-cam02_indoor-dog_out+fall-neg-"
                "night_full_color-007.mp4"
            ),
            behaviors=("dog_out", "fall"),
            polarity="neg",
            lighting="night_full_color",
            sequence=7,
            note="check occlusion",
        )
    ]
    window._refresh_table()
    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window._editing_index == 0
    assert window.note_edit.text() == "check occlusion"
    assert window.start_spin.value() == pytest.approx(12.5)
    assert window.end_spin.value() == pytest.approx(18.75)
    assert window.sequence_spin.value() == 7
    assert set(window.selected_behaviors()) == {"dog_out", "fall"}
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window.view_combo.currentText() == "indoor"
    assert window.add_button.text() == "更新片段"


def test_collapsible_behavior_group(qt_app):
    window = MainWindow()
    window.show()
    qt_app.processEvents()

    assert isinstance(window.behaviors_group, QGroupBox)
    assert window.behaviors_group.isCheckable()
    assert window.behaviors_group.isChecked()
    assert window.behavior_checks_container.isVisible()
    assert window.behaviors_group.animation_duration_ms == 300
    assert window.behaviors_group.chevron_rotation == pytest.approx(90.0)

    window.behaviors_group.setChecked(False)
    qt_app.processEvents()
    assert window.behavior_checks_container.isVisible()
    QTest.qWait(350)
    assert not window.behavior_checks_container.isVisible()
    assert window.behaviors_group.chevron_rotation == pytest.approx(0.0)

    window.behaviors_group.setChecked(True)
    qt_app.processEvents()
    assert window.behavior_checks_container.isVisible()
    QTest.qWait(350)
    assert window.behavior_checks_container.isVisible()
    assert window.behaviors_group.chevron_rotation == pytest.approx(90.0)


def test_behavior_selector_holds_multiple_checked_tags(qt_app):
    window = MainWindow()

    window.behavior_tag_combo.set_tags(
        ("dog_out", "fall", "delivery_dropoff"),
        ("dog_out", "delivery_dropoff"),
    )

    assert window.behavior_tag_combo.checked_tags() == (
        "dog_out",
        "delivery_dropoff",
    )
    assert "2" in window.behavior_tag_combo.currentText()


def test_clicking_behavior_selector_summary_opens_its_dropdown(qt_app):
    combo = PopupTrackingBehaviorTagComboBox()
    combo.set_tags(("dog_out", "fall"), ())
    combo.resize(420, 36)
    combo.show()
    qt_app.processEvents()

    QTest.mouseClick(combo.lineEdit(), Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert combo.popup_requests == 1


def test_behavior_selector_popup_contains_all_available_tags(qt_app):
    window = MainWindow()
    window.project.custom_behavior_tags.append("delivery_dropoff")

    window._rebuild_behavior_controls(())

    assert window.behavior_tag_combo.count() == len(
        (*BEHAVIOR_LABELS, "delivery_dropoff")
    )
    assert window.behavior_tag_combo.itemText(
        window.behavior_tag_combo.findData("delivery_dropoff")
    ) == "delivery_dropoff"


@pytest.mark.parametrize("click_indicator", (False, True))
def test_behavior_selector_click_keeps_summary_and_filename_in_sync(
    qt_app, click_indicator
):
    window = MainWindow()
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.show()
    qt_app.processEvents()

    window.behavior_tag_combo.showPopup()
    qt_app.processEvents()
    index = window.behavior_tag_combo.model().index(0, 0)
    rect = window.behavior_tag_combo.view().visualRect(index)
    click_point = rect.center()
    if click_indicator:
        click_point.setX(rect.left() + 8)
    QTest.mouseClick(
        window.behavior_tag_combo.view().viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        click_point,
    )
    qt_app.processEvents()

    assert window.behavior_tag_combo.checked_tags() == (
        BEHAVIOR_LABELS[0],
    )
    assert window.behavior_tag_combo.currentText() == "已选 1 项"
    assert BEHAVIOR_LABELS[0] in window.filename_preview.text()


def test_main_window_uses_semantic_style_object_names(qt_app):
    window = MainWindow()

    assert window.output_folder_label.objectName() == "mutedLabel"
    assert window.source_label.objectName() == "mutedLabel"
    assert window.project_video_combo.objectName() == "projectVideoCombo"
    assert window.video_widget.objectName() == "videoSurface"
    assert window.behaviors_group.objectName() == "collapsibleBehaviorGroup"


def test_file_dialogs_request_non_native_windows(qt_app, monkeypatch):
    window = MainWindow()
    dialog_options = []

    def open_file_name(*_args, **kwargs):
        dialog_options.append(kwargs.get("options"))
        return "", ""

    def save_file_name(*_args, **kwargs):
        dialog_options.append(kwargs.get("options"))
        return "", ""

    def existing_directory(*_args, **kwargs):
        dialog_options.append(kwargs.get("options"))
        return ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(open_file_name))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(save_file_name))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(existing_directory)
    )
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=1,
            end_seconds=2,
            output="20260729-cam02_indoor-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        )
    ]

    window.open_video()
    window.import_csv()
    window.save_csv()
    window.select_output_folder()

    assert len(dialog_options) == 4
    assert all(
        option is not None and option & QFileDialog.Option.DontUseNativeDialog
        for option in dialog_options
    )


def _clip_record(source: str, sequence: int) -> ClipRecord:
    return ClipRecord(
        source=source,
        start_seconds=float(sequence),
        end_seconds=float(sequence + 1),
        output=(
            f"20260729-cam02_indoor-dog_out-pos-daytime-{sequence:03d}.mp4"
        ),
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=sequence,
    )


def _wait_for_export_completion(qt_app, window: MainWindow) -> None:
    worker = window._export_worker
    assert worker is not None
    for _ in range(100):
        qt_app.processEvents()
        if window._export_worker is None:
            assert worker.wait(1000)
            return
        QTest.qWait(10)
    pytest.fail("export worker did not complete")


def test_switching_project_video_rebinds_records_without_cross_video_leakage(
    qt_app, tmp_path
):
    window = MainWindow()
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"

    window.set_source_path(first)
    window.records.append(_clip_record(first.name, 1))
    window.set_source_path(second)
    window.records.append(_clip_record(second.name, 2))
    window.switch_active_video(window.project.videos[0].id)

    assert window.records[0].source == first.name
    assert len(window.records) == 1
    assert len(window.project.videos[1].segments) == 1
    assert window.project_video_combo.currentData() == window.project.videos[0].id


def test_project_save_open_and_restore_backup_keep_active_video_segments(
    qt_app, tmp_path
):
    project_path = tmp_path / "work.labelproj"
    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    window.records.append(_clip_record("camera.mp4", 1))
    window._project_path = project_path
    window._mark_project_dirty()
    window.save_project()
    window._write_automatic_backup()

    restored = MainWindow()
    restored._load_project_path(project_path)

    assert restored.records == window.records
    assert list((tmp_path / ".backups").glob("work_*.labelproj"))


def test_annotation_change_starts_or_resets_backup_debounce(qt_app, tmp_path):
    window = MainWindow()
    window._project_path = tmp_path / "work.labelproj"
    window._mark_project_dirty()

    assert window._project_dirty
    assert window._backup_timer.isActive()
    assert window._backup_timer.interval() == 30_000


def test_project_file_pickers_request_non_native_dialogs(qt_app, monkeypatch):
    window = MainWindow()
    dialog_options = []

    def save_file_name(*_args, **kwargs):
        dialog_options.append(kwargs.get("options"))
        return "", ""

    def open_file_name(*_args, **kwargs):
        dialog_options.append(kwargs.get("options"))
        return "", ""

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(save_file_name)
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(open_file_name)
    )

    window.save_project()
    window.open_project()
    window.restore_project_from_backup()

    assert len(dialog_options) == 3
    assert all(
        option is not None and option & QFileDialog.Option.DontUseNativeDialog
        for option in dialog_options
    )


def test_import_csv_replaces_active_project_segments_in_place(
    qt_app, tmp_path, monkeypatch
):
    csv_path = tmp_path / "clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "camera.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    active_records = window.records
    active_records.append(_clip_record("camera.mp4", 99))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert window.records is active_records
    assert window.project.videos[0].segments is active_records
    assert [record.sequence for record in active_records] == [1]


def test_import_csv_activating_different_video_rebinds_media_source(
    qt_app, tmp_path, monkeypatch
):
    current_path = tmp_path / "current.mp4"
    selected_path = tmp_path / "selected.mp4"
    other_path = tmp_path / "other.mp4"
    csv_path = tmp_path / "clips.csv"
    current_path.touch()
    selected_path.touch()
    csv_path.write_text(
        (
            "source,start,end,output\n"
            f"{selected_path},00:00:01.000,00:00:02.000,"
            "20260202-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
            f"{other_path},00:00:03.000,00:00:04.000,"
            "20260303-cam03_closeup-fall-neg-night_black_white-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    window.set_source_path(current_path)
    window.switch_active_video(window.project.active_video_id)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    selected_video = next(
        video for video in window.project.videos if video.path == selected_path
    )
    assert window.project.active_video_id == selected_video.id
    assert window.project_video_combo.currentData() == selected_video.id
    assert window.source_path == selected_path
    assert window.records is selected_video.segments
    assert [record.source for record in window.records] == [str(selected_path)]
    assert Path(window.player.source().toLocalFile()) == selected_path


def test_import_csv_activating_missing_video_clears_media_source(
    qt_app, tmp_path, monkeypatch
):
    current_path = tmp_path / "current.mp4"
    missing_path = tmp_path / "missing.mp4"
    other_path = tmp_path / "other.mp4"
    csv_path = tmp_path / "clips.csv"
    current_path.touch()
    csv_path.write_text(
        (
            "source,start,end,output\n"
            f"{missing_path},00:00:01.000,00:00:02.000,"
            "20260202-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
            f"{other_path},00:00:03.000,00:00:04.000,"
            "20260303-cam03_closeup-fall-neg-night_black_white-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    window.set_source_path(current_path)
    window.switch_active_video(window.project.active_video_id)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert window.source_path == missing_path
    assert [record.source for record in window.records] == [str(missing_path)]
    assert window.player.source().isEmpty()


def test_import_csv_restores_defaults_from_selected_active_video(
    qt_app, tmp_path, monkeypatch
):
    active_path = tmp_path / "active.mp4"
    other_path = tmp_path / "other.mp4"
    csv_path = tmp_path / "clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            f"{other_path},00:00:01.000,00:00:02.000,"
            "20260101-cam01_panorama-fall-neg-night_black_white-001.mp4\n"
            f"{active_path},00:00:03.000,00:00:04.000,"
            "20260202-cam02_indoor-dog_out-pos-daytime-002.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    window.set_source_path(active_path)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert window.source_path == active_path
    assert [record.source for record in window.records] == [str(active_path)]
    assert window.date_edit.text() == "20260202"
    assert window.camera_edit.text() == "cam02"
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "pos"
    assert window.lighting_combo.currentText() == "daytime"
    assert window.sequence_spin.value() == 3


@pytest.mark.parametrize(
    ("control_name", "value"),
    (
        ("date_edit", "20260804"),
        ("camera_edit", "cam04"),
        ("view_combo", "closeup"),
    ),
)
def test_saved_project_global_setting_change_marks_dirty_and_restarts_backup(
    qt_app, tmp_path, control_name, value
):
    window = MainWindow()
    window._project_path = tmp_path / "work.labelproj"
    window._project_dirty = False
    window._backup_timer.stop()

    control = getattr(window, control_name)
    if control_name == "view_combo":
        control.setCurrentText(value)
    else:
        control.setText(value)

    assert window._project_dirty
    assert window._backup_timer.isActive()
    assert window._backup_timer.interval() == 30_000


def test_export_status_change_marks_saved_project_dirty_and_persists(
    qt_app, tmp_path, monkeypatch
):
    source_path = tmp_path / "source.mp4"
    project_path = tmp_path / "work.labelproj"
    output_dir = tmp_path / "output"
    source_path.touch()
    window = MainWindow()
    window.set_source_path(source_path)
    window.records.append(_clip_record(source_path.name, 1))
    window.output_dir = output_dir
    window._project_path = project_path
    window.save_project()
    window._backup_timer.stop()
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffmpeg", lambda _value: "ffmpeg"
    )
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffprobe", lambda _value: "ffprobe"
    )
    monkeypatch.setattr(
        "video_labeler.export_worker.run_clip_export",
        lambda request, control: ExportResult(
            status="fail", output=request.output_path.name, error="simulated failure"
        ),
    )
    monkeypatch.setattr(window, "_confirm_export_preview", lambda *_args: True)

    window.start_export()
    _wait_for_export_completion(qt_app, window)

    assert window.records[0].status == "fail"
    assert window.records[0].error == "simulated failure"
    assert window._project_dirty
    assert window._backup_timer.isActive()

    window.save_project()
    restored = MainWindow()

    assert restored._load_project_path(project_path)
    assert restored.records[0].status == "fail"
    assert restored.records[0].error == "simulated failure"


def test_export_passes_resolved_ffprobe_to_each_clip(qt_app, tmp_path, monkeypatch):
    source_path = tmp_path / "source.mp4"
    source_path.touch()
    window = MainWindow()
    window.set_source_path(source_path)
    window.records.append(_clip_record(source_path.name, 1))
    window.output_dir = tmp_path / "output"
    captured_requests = []
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffmpeg", lambda _value: "ffmpeg"
    )
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffprobe", lambda _value: "ffprobe"
    )
    monkeypatch.setattr(
        "video_labeler.export_worker.run_clip_export",
        lambda request, control=None: (
            captured_requests.append((request, control))
            or ExportResult(status="ok", output=request.output_path.name)
        ),
    )
    monkeypatch.setattr(window, "_confirm_export_preview", lambda *_args: True)

    window.start_export()
    _wait_for_export_completion(qt_app, window)

    assert captured_requests[0][0].ffprobe == "ffprobe"
    assert captured_requests[0][1] is not None


def test_loading_project_cleans_orphaned_export_parts_after_confirmation(
    qt_app, tmp_path, monkeypatch
):
    from video_labeler.project_io import new_project, save_project

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    orphan = output_dir / ("clip." + "a" * 32 + ".part.mp4")
    user_media = output_dir / "user.part.mp4"
    orphan.write_bytes(b"partial")
    user_media.write_bytes(b"user media")
    project = new_project()
    project.global_settings["output_dir"] = str(output_dir)
    project_path = save_project(tmp_path / "work.labelproj", project)
    window = MainWindow()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )

    assert window._load_project_path(project_path)
    assert not orphan.exists()
    assert user_media.exists()


def test_loading_project_keeps_orphaned_export_parts_when_cleanup_is_skipped(
    qt_app, tmp_path, monkeypatch
):
    from video_labeler.project_io import new_project, save_project

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    orphan = output_dir / ("clip." + "a" * 32 + ".part.mp4")
    orphan.write_bytes(b"partial")
    project = new_project()
    project.global_settings["output_dir"] = str(output_dir)
    project_path = save_project(tmp_path / "work.labelproj", project)
    window = MainWindow()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.No),
    )

    assert window._load_project_path(project_path)
    assert orphan.exists()


def test_whole_project_export_uses_each_project_video_source(
    qt_app, tmp_path, monkeypatch
):
    first_source = tmp_path / "first.mp4"
    second_source = tmp_path / "second.mp4"
    first_source.touch()
    second_source.touch()
    window = MainWindow()
    window.set_source_path(first_source)
    window.records.append(_clip_record(first_source.name, 1))
    window.set_source_path(second_source)
    window.records.append(_clip_record(second_source.name, 2))
    window.output_dir = tmp_path / "output"
    captured_requests = []
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffmpeg", lambda _value: "ffmpeg"
    )
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffprobe", lambda _value: "ffprobe"
    )
    monkeypatch.setattr(
        "video_labeler.export_worker.run_clip_export",
        lambda request, control: (
            captured_requests.append(request)
            or ExportResult(status="ok", output=request.output_path.name)
        ),
    )
    monkeypatch.setattr(window, "_confirm_export_preview", lambda *_args: True)

    window.start_project_export()
    _wait_for_export_completion(qt_app, window)

    assert window.project_export_button.text() == "导出整个项目"
    assert window.project_queue_dialog.table.rowCount() == 2
    assert window.project_queue_dialog.progress_bar.maximum() == 2
    assert window.project_queue_dialog.table.item(0, 3).text() == "成功"
    assert not window.project_queue_dialog.cancel_button.isEnabled()
    assert {request.input_path for request in captured_requests} == {
        first_source,
        second_source,
    }


def test_empty_project_shows_quick_start_hint(qt_app, tmp_path):
    window = MainWindow()

    assert not window.welcome_hint_label.isHidden()
    window.set_source_path(tmp_path / "source.mp4")

    assert window.welcome_hint_label.isHidden()


def test_export_with_unchanged_record_state_keeps_saved_project_clean(
    qt_app, tmp_path, monkeypatch
):
    source_path = tmp_path / "source.mp4"
    output_dir = tmp_path / "output"
    source_path.touch()
    window = MainWindow()
    window.set_source_path(source_path)
    window.records.append(_clip_record(source_path.name, 1))
    window.records[0].status = "skip"
    window.output_dir = output_dir
    window._project_path = tmp_path / "work.labelproj"
    window.save_project()
    window._backup_timer.stop()
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffmpeg", lambda _value: "ffmpeg"
    )
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffprobe", lambda _value: "ffprobe"
    )
    monkeypatch.setattr(
        "video_labeler.export_worker.run_clip_export",
        lambda request, control: ExportResult(
            status="skip", output=request.output_path.name
        ),
    )
    monkeypatch.setattr(window, "_confirm_export_preview", lambda *_args: True)

    window.start_export()
    _wait_for_export_completion(qt_app, window)

    assert not window._project_dirty
    assert not window._backup_timer.isActive()


def test_export_status_change_without_saved_project_keeps_project_clean(
    qt_app, tmp_path, monkeypatch
):
    source_path = tmp_path / "source.mp4"
    output_dir = tmp_path / "output"
    source_path.touch()
    window = MainWindow()
    window.set_source_path(source_path)
    window.records.append(_clip_record(source_path.name, 1))
    window.output_dir = output_dir
    window._project_dirty = False
    window._backup_timer.stop()
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffmpeg", lambda _value: "ffmpeg"
    )
    monkeypatch.setattr(
        "video_labeler.ui.main_window.resolve_ffprobe", lambda _value: "ffprobe"
    )
    monkeypatch.setattr(
        "video_labeler.export_worker.run_clip_export",
        lambda request, control: ExportResult(
            status="ok", output=request.output_path.name
        ),
    )
    monkeypatch.setattr(window, "_confirm_export_preview", lambda *_args: True)

    window.start_export()
    _wait_for_export_completion(qt_app, window)

    assert window.records[0].status == "ok"
    assert not window._project_dirty
    assert not window._backup_timer.isActive()


def test_import_csv_without_active_video_creates_persisted_project_video(
    qt_app, tmp_path, monkeypatch
):
    csv_path = tmp_path / "clips.csv"
    project_path = tmp_path / "work.labelproj"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "camera.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()
    window._project_path = project_path
    window.save_project()

    restored = MainWindow()
    assert restored._load_project_path(project_path)
    assert len(restored.project.videos) == 1
    assert restored.project.videos[0].segments is restored.records
    assert restored.records == window.records
    assert restored.project.videos[0].path.is_absolute()


def test_import_csv_without_active_video_partitions_multiple_sources(
    qt_app, tmp_path, monkeypatch
):
    csv_path = tmp_path / "clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "first.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
            "second.mp4,00:00:03.000,00:00:04.000,"
            "20260729-cam02_indoor-fall-neg-daytime-002.mp4\n"
            "first.mp4,00:00:05.000,00:00:06.000,"
            "20260729-cam02_indoor-dog_out-pos-daytime-003.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert [video.path.name for video in window.project.videos] == [
        "first.mp4",
        "second.mp4",
    ]
    assert [record.source for record in window.project.videos[0].segments] == [
        "first.mp4",
        "first.mp4",
    ]
    assert [record.source for record in window.project.videos[1].segments] == [
        "second.mp4"
    ]
    assert window.records is window.project.videos[0].segments

    window.switch_active_video(window.project.videos[1].id)

    assert window.records is window.project.videos[1].segments
    assert [record.source for record in window.records] == ["second.mp4"]


def test_import_csv_keeps_same_basename_videos_in_different_directories_isolated(
    qt_app, tmp_path, monkeypatch
):
    first_path = tmp_path / "a" / "cam.mp4"
    second_path = tmp_path / "b" / "cam.mp4"
    csv_path = tmp_path / "clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            f"{second_path},00:00:03.000,00:00:04.000,"
            "20260729-cam02_indoor-fall-neg-daytime-002.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    window.set_source_path(first_path)
    window.records.append(_clip_record(first_path.name, 1))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert len(window.project.videos) == 2
    assert window.project.videos[0].path == first_path.resolve()
    assert [record.sequence for record in window.project.videos[0].segments] == [1]
    assert window.project.videos[1].path == second_path.resolve()
    assert [record.sequence for record in window.records] == [2]


def test_import_csv_merges_relative_and_absolute_source_aliases(
    qt_app, tmp_path, monkeypatch
):
    csv_path = tmp_path / "clips.csv"
    video_path = (tmp_path / "same.mp4").resolve()
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "same.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam02_indoor-dog_out-pos-daytime-001.mp4\n"
            f"{video_path},00:00:03.000,00:00:04.000,"
            "20260729-cam02_indoor-fall-neg-daytime-002.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV")),
    )

    window.import_csv()

    assert len(window.project.videos) == 1
    assert window.project.videos[0].path == video_path
    assert [record.sequence for record in window.records] == [1, 2]
    assert [record.source for record in window.records] == [
        "same.mp4",
        str(video_path),
    ]


def test_restore_invalid_project_keeps_current_state_and_reports_no_success(
    qt_app, tmp_path, monkeypatch
):
    invalid_path = tmp_path / "invalid.labelproj"
    invalid_path.write_text("not-json", encoding="utf-8")
    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    original_project = window.project
    original_path = tmp_path / "work.labelproj"
    window._project_path = original_path
    window._project_dirty = True
    messages = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(invalid_path), "工程")),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(
        window,
        "_show_error",
        lambda _title, text: messages.append(text),
    )

    window.restore_project_from_backup()

    assert window.project is original_project
    assert window._project_path == original_path
    assert window._project_dirty
    assert messages == ["打开工程失败：project JSON is invalid"]
    assert "已从备份恢复工程" not in window.status_label.text()


def test_automatic_backup_reports_project_validation_error(qt_app, tmp_path, monkeypatch):
    window = MainWindow()
    window._project_path = tmp_path / "work.labelproj"
    statuses = []
    monkeypatch.setattr(
        "video_labeler.ui.main_window.create_backup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("invalid project")
        ),
    )
    monkeypatch.setattr(window, "_set_status", statuses.append)

    window._write_automatic_backup()

    assert statuses == ["自动备份失败：invalid project"]


def test_behavior_selector_is_compact_and_shows_all_popup_options(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert not window.behaviors_group.findChildren(QScrollArea)
    assert window.behavior_tag_combo.maxVisibleItems() == (
        window.behavior_tag_combo.count()
    )
    assert not window.behavior_tag_combo.view().isVisible()
    assert not hasattr(window, "behavior_checks_layout")

    assert window.view_combo.maxVisibleItems() == window.view_combo.count()
    assert window.polarity_combo.maxVisibleItems() == window.polarity_combo.count()
    assert window.lighting_combo.maxVisibleItems() == window.lighting_combo.count()


def test_collapsible_behavior_group_restores_content_height_after_resize(qt_app):
    window = MainWindow()
    window.show()
    window.resize(1440, 900)
    qt_app.processEvents()

    window.behaviors_group.setChecked(False)
    _wait_for_content_animation(qt_app, window)
    window.resize(1280, 900)
    window.behaviors_group.setChecked(True)
    _wait_for_content_animation(qt_app, window)
    qt_app.processEvents()

    assert window.behavior_checks_container.maximumHeight() == 16777215
    assert window.behavior_checks_container.height() >= (
        window.behavior_checks_container.sizeHint().height()
    )


def test_new_window_sizes_behavior_filter_to_all_options(qt_app):
    window = MainWindow()

    assert (
        window.behavior_filter_combo.maxVisibleItems()
        == window.behavior_filter_combo.count()
    )


def test_sort_clears_selection_before_batch_delete(qt_app, monkeypatch):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=index,
            end_seconds=index + 1,
            output=f"clip-{index}.mp4",
            sequence=index,
        )
        for index in range(1, 3)
    ]
    window._refresh_table()
    window.task_table.selectRow(0)

    window.sort_combo.setCurrentIndex(1)

    assert not window.task_table.selectionModel().selectedRows()
    errors = []
    monkeypatch.setattr(
        window,
        "_show_error",
        lambda title, text: errors.append((title, text)),
    )
    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [2, 1]
    assert errors == [("未选择片段", "请先选择至少一个片段。")]


def test_delete_clears_selection_before_repeat_delete(qt_app, monkeypatch):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=index,
            end_seconds=index + 1,
            output=f"clip-{index}.mp4",
            sequence=index,
        )
        for index in range(1, 3)
    ]
    window._refresh_table()
    window.task_table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )

    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [2]
    assert not window.task_table.selectionModel().selectedRows()
    errors = []
    monkeypatch.setattr(
        window,
        "_show_error",
        lambda title, text: errors.append((title, text)),
    )
    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [2]
    assert errors == [("未选择片段", "请先选择至少一个片段。")]


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


def test_table_batch_operation_chinese_text(qt_app):
    window = MainWindow()

    assert window.task_table.selectionMode() == (
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    assert window.batch_edit_button.text() == "批量修改选中片段"
    assert window.batch_delete_button.text() == "批量删除选中"
    assert window.clear_filters_button.text() == "清空筛选"
    assert window.behavior_filter_combo.itemText(0) == "全部行为"
    assert window.polarity_filter_combo.itemText(0) == "全部正负例"
    assert window.status_filter_combo.itemText(0) == "全部导出状态"

    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=0,
            end_seconds=2,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=8,
            output=(
                "20260729-cam02_panorama-fall-neg-night_full_color-002.mp4"
            ),
            behaviors=("fall",),
            polarity="neg",
            lighting="night_full_color",
            sequence=2,
            status="fail",
        ),
    ]
    window._refresh_table()

    window.behavior_filter_combo.setCurrentData("fall")
    assert window.task_table.isRowHidden(0)
    assert not window.task_table.isRowHidden(1)

    window.clear_filters_button.click()
    assert not window.task_table.isRowHidden(0)
    assert not window.task_table.isRowHidden(1)

    window._apply_batch_changes(
        [0],
        behaviors=("fall",),
        polarity="neg",
        lighting=None,
        view=None,
    )
    assert window.records[0].behaviors == ("fall",)
    assert window.records[0].polarity == "neg"

    window.sort_combo.setCurrentIndex(3)
    assert [record.sequence for record in window.records] == [2, 1]


def test_batch_delete_selected_rows_after_confirmation(qt_app, monkeypatch):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=index,
            end_seconds=index + 1,
            output=f"clip-{index}.mp4",
            sequence=index,
        )
        for index in range(1, 4)
    ]
    window._refresh_table()
    window.task_table.selectRow(0)
    window.task_table.selectionModel().select(
        window.task_table.model().index(2, 0),
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes
        ),
    )

    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [2]


def test_filtering_out_selected_rows_excludes_them_from_batch_operations(
    qt_app, monkeypatch
):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=0,
            end_seconds=2,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=4,
            output="20260729-cam02_panorama-fall-neg-daytime-002.mp4",
            behaviors=("fall",),
            polarity="neg",
            lighting="daytime",
            sequence=2,
        ),
    ]
    window._refresh_table()
    window.task_table.selectRow(0)

    window.behavior_filter_combo.setCurrentData("fall")

    assert window.task_table.isRowHidden(0)
    assert not window.task_table.selectionModel().selectedRows()
    assert window._selected_record_indexes() == []

    errors = []
    monkeypatch.setattr(
        window,
        "_show_error",
        lambda title, text: errors.append((title, text)),
    )
    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [1, 2]
    assert errors == [("未选择片段", "请先选择至少一个片段。")]


def test_batch_changes_reject_filename_collisions_without_partial_mutation(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=0,
            end_seconds=2,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=4,
            output="20260729-cam02_panorama-fall-pos-daytime-001.mp4",
            behaviors=("fall",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=4,
            end_seconds=6,
            output="20260729-cam02_panorama-dog_out-pos-daytime-002.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=2,
        ),
    ]
    original_records = list(window.records)

    with pytest.raises(ValueError, match="批量修改后输出文件名重复"):
        window._apply_batch_changes(
            [0, 2],
            behaviors=("fall",),
            polarity=None,
            lighting=None,
            view=None,
        )

    assert window.records == original_records


def test_batch_view_update_preserves_manual_filename_and_reports_skip_status(qt_app):
    window = MainWindow()
    manual_output = "manual-clip.mp4"
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=0,
            end_seconds=2,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=4,
            output=manual_output,
            behaviors=("fall",),
            polarity="neg",
            lighting="night_full_color",
            sequence=2,
        ),
    ]

    window._apply_batch_changes(
        [0, 1],
        behaviors=None,
        polarity=None,
        lighting=None,
        view="indoor",
    )

    assert window.records[0].output == (
        "20260729-cam02_indoor-dog_out-pos-daytime-001.mp4"
    )
    assert window.records[1].output == manual_output
    assert window.status_label.text() == "批量修改完成；手动命名片段未更新视角"


def test_undo_redo_restore_added_updated_and_deleted_segments(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    active_records = window.records
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")

    window.task_table.selectRow(0)
    qt_app.processEvents()
    window.set_clip_range(1, 3)
    window.add_or_update_clip()
    _add_valid_clip(window, start=3, end=4, behavior="fall")
    assert [(record.sequence, record.end_seconds) for record in window.records] == [
        (1, 3),
        (2, 4),
    ]

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )
    window.task_table.selectRow(1)
    window.remove_selected_clip()
    assert [record.sequence for record in window.records] == [1]
    assert window.undo_button.isEnabled()

    window.undo_segments()
    assert window.records is active_records
    assert [(record.sequence, record.end_seconds) for record in window.records] == [
        (1, 3),
        (2, 4),
    ]
    assert window.redo_button.isEnabled()

    window.undo_segments()
    assert [(record.sequence, record.end_seconds) for record in window.records] == [
        (1, 3),
    ]
    window.undo_segments()
    assert [(record.sequence, record.end_seconds) for record in window.records] == [
        (1, 2),
    ]

    window.redo_segments()
    window.redo_segments()
    window.redo_segments()
    assert [record.sequence for record in window.records] == [1]


def test_undo_history_is_scoped_to_active_video_and_cleared_by_new_project(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    window.set_source_path(first)
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")
    first_id = window.project.active_video_id
    assert window.undo_button.isEnabled()

    window.set_source_path(second)
    assert not window.undo_button.isEnabled()
    _add_valid_clip(window, start=3, end=4, behavior="fall")
    second_id = window.project.active_video_id
    assert second_id != first_id

    window.switch_active_video(first_id)
    assert window.undo_button.isEnabled()
    window.undo_segments()
    assert window.records == []

    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )
    window.new_project()
    assert window.records == []
    assert not window.undo_button.isEnabled()
    assert not window.redo_button.isEnabled()
    assert window._active_video_histories == {}


def test_undo_does_not_change_verified_next_clip_reset_fields(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")

    window.undo_segments()

    assert window.selected_behaviors() == ()
    assert window.start_spin.value() == pytest.approx(2)
    assert window.end_spin.value() == pytest.approx(2)
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"


def test_batch_edit_is_undoable_as_one_segment_history_operation(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")
    assert window.undo_button.isEnabled()

    window._apply_batch_changes(
        [0],
        behaviors=("fall",),
        polarity=None,
        lighting=None,
        view=None,
    )

    assert window.records[0].behaviors == ("fall",)
    assert window.undo_button.isEnabled()
    window.undo_segments()
    assert window.records[0].behaviors == ("dog_out",)
    assert window.redo_button.isEnabled()
    window.redo_segments()
    assert window.records[0].behaviors == ("fall",)


def test_sorting_segments_keeps_the_previous_history_entry_undoable(
    qt_app, tmp_path
):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")
    _add_valid_clip(window, start=2, end=5, behavior="fall")

    window.sort_combo.setCurrentIndex(3)

    assert [record.sequence for record in window.records] == [2, 1]
    window.undo_segments()
    assert [record.sequence for record in window.records] == [1, 2]


def test_project_setup_collapses_after_the_first_segment_is_added(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    assert window.project_header.isChecked()

    _add_valid_clip(window, start=1, end=2, behavior="dog_out")

    assert not window.project_header.isChecked()


def test_main_window_shortcut_mapping(qt_app):
    window = MainWindow()

    expected = {
        "play_pause": "Space",
        "previous_frame": "A",
        "next_frame": "D",
        "set_start": "S",
        "set_end": "E",
        "delete_selected": "Del",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "save_project": "Ctrl+S",
    }

    assert set(window.shortcuts) == set(expected)
    assert all(
        window.shortcuts[name].key() == QKeySequence(sequence)
        for name, sequence in expected.items()
    )
    assert window.shortcut_help_button.text() == "快捷键说明"
    assert "空格" in window.shortcut_hint_label.text()
    assert "I/O" not in window.shortcut_hint_label.text()
    assert "Ctrl+E" not in window.shortcut_hint_label.text()

    dialog = window._create_shortcut_help_dialog()
    assert dialog.windowTitle() == "快捷键说明"
    help_table = dialog.findChild(QTableWidget)
    assert help_table is not None
    assert [
        help_table.item(row, 0).text() for row in range(help_table.rowCount())
    ] == [
        "Space",
        "A",
        "D",
        "S",
        "E",
        "Del",
        "Ctrl+Z",
        "Ctrl+Y",
        "Ctrl+S",
    ]


def test_editable_metadata_combos_include_custom_action(qt_app):
    window = MainWindow()

    assert window.view_combo.itemText(window.view_combo.count() - 1) == "自定义..."
    assert window.polarity_combo.itemText(window.polarity_combo.count() - 1) == "自定义..."
    assert window.lighting_combo.itemText(window.lighting_combo.count() - 1) == "自定义..."
    assert [window.mode_combo.itemText(index) for index in range(window.mode_combo.count())] == [
        "encode",
        "copy",
    ]
    assert [
        window.speed_combo.itemText(index)
        for index in range(window.speed_combo.count())
    ] == APPROVED_PLAYBACK_RATE_ITEMS


def test_playback_rate_controls_apply_presets_and_custom_values(qt_app):
    window = MainWindow()

    assert [
        window.speed_combo.itemText(index)
        for index in range(window.speed_combo.count())
    ] == APPROVED_PLAYBACK_RATE_ITEMS
    assert window.custom_speed_spin.minimum() == pytest.approx(0.1)
    assert window.custom_speed_spin.maximum() == pytest.approx(4.0)

    window.speed_combo.setCurrentText("1.5x")

    assert window.player.playbackRate() == pytest.approx(1.5)
    assert window.custom_speed_spin.value() == pytest.approx(1.5)
    assert window.playback_rate_badge.text() == "1.5x"

    window.custom_speed_spin.setValue(1.7)
    window._on_custom_speed_committed()

    assert window.player.playbackRate() == pytest.approx(1.7)
    assert window.speed_combo.currentText() == "自定义"
    assert window.playback_rate_badge.text() == "1.7x"


def test_invalid_playback_rate_restores_the_last_valid_value(qt_app):
    window = MainWindow()
    window.custom_speed_spin.setValue(1.7)
    window._on_custom_speed_committed()

    assert not window._apply_playback_rate(4.1)
    assert window.player.playbackRate() == pytest.approx(1.7)
    assert window.custom_speed_spin.value() == pytest.approx(1.7)
    assert "0.1x" in window.status_label.text()
    assert "4.0x" in window.status_label.text()


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


def test_import_csv_registers_custom_metadata_values(qt_app, tmp_path, monkeypatch):
    csv_path = tmp_path / "custom-clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam_02_doorway-dog_out-needs_review-night_red-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV files (*.csv)")),
    )

    window.import_csv()

    assert window.view_combo.currentText() == "doorway"
    assert window.polarity_combo.findText("needs_review") >= 0
    assert window.lighting_combo.findText("night_red") >= 0


def test_add_custom_behavior_tag_registers_project_data_and_preserves_fixed_fields(
    qt_app,
):
    window = MainWindow()
    window.set_clip_range(3.0, 5.0)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.custom_behavior_tag_edit.setText(" delivery_dropoff ")

    window.add_custom_behavior_tag()

    assert window.project.custom_behavior_tags == ["delivery_dropoff"]
    assert "delivery_dropoff" in window.behavior_checks
    assert window.behavior_checks["delivery_dropoff"].isChecked() is False
    assert window.start_spin.value() == pytest.approx(3.0)
    assert window.end_spin.value() == pytest.approx(5.0)
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"


def test_custom_tag_color_and_preset_merge_are_persisted_in_the_ui(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()
    window.set_custom_behavior_tag_color("delivery_dropoff", "#3F9CFF")
    preset_path = tmp_path / "team.tagpreset.json"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(preset_path), "Preset")),
    )
    window.export_tag_preset()

    restored = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(preset_path), "Preset")),
    )
    restored.import_tag_preset()

    assert preset_path.is_file()
    assert restored.project.custom_behavior_tags == ["delivery_dropoff"]
    assert restored.project.custom_behavior_tag_colors == {
        "delivery_dropoff": "#3F9CFF"
    }
    assert "#3F9CFF" in restored.behavior_checks["delivery_dropoff"].styleSheet()


def test_batch_tag_add_and_remove_preserve_unrelated_tags(qt_app):
    window = MainWindow()
    window.records = [_clip_record("source.mp4", 1), _clip_record("source.mp4", 2)]

    window._apply_batch_changes(
        [0, 1],
        ("fall",),
        None,
        None,
        None,
        behavior_mode="add",
    )
    window._apply_batch_changes(
        [0, 1],
        ("dog_out",),
        None,
        None,
        None,
        behavior_mode="remove",
    )

    assert [record.behaviors for record in window.records] == [
        ("fall",),
        ("fall",),
    ]


def test_switching_videos_clears_the_bounded_frame_cache(qt_app, tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.touch()
    second.touch()
    window = MainWindow()
    window.set_source_path(first)
    first_id = window.project.active_video_id
    window.set_source_path(second)
    second_id = window.project.active_video_id
    window.switch_active_video(first_id)
    window.frame_cache.put("frame", b"frame", size_bytes=5)

    window.switch_active_video(second_id)

    assert len(window.frame_cache) == 0


def test_project_export_queue_is_restored_from_its_sidecar(qt_app, tmp_path):
    source = tmp_path / "camera.mp4"
    project_path = tmp_path / "work.labelproj"
    window = MainWindow()
    window.set_source_path(source)
    window.records.append(_clip_record(source.name, 1))
    window._project_path = project_path
    window.save_project()
    window.records[0].status = "fail"
    window.records[0].error = "write denied"
    window._project_export_queue = [(source, window.records[0])]
    window._persist_project_export_queue()

    restored = MainWindow()
    assert restored._load_project_path(project_path)

    assert len(restored._project_export_queue) == 1
    assert restored.project_queue_dialog.table.item(0, 3).text() == "失败"
    assert restored.project_queue_dialog.table.item(0, 4).text() == "write denied"


def test_invalid_time_range_shows_a_warning_without_adding_a_segment(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    window.set_clip_range(4, 2)
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )

    window.add_or_update_clip()

    assert window.records == []
    assert len(messages) == 1


def test_timeline_segment_edge_adjustment_updates_clip_time_controls(qt_app):
    window = MainWindow()
    window.timeline_slider.setRange(0, 10_000)
    window.set_clip_range(1.0, 3.0)

    window.timeline_slider.adjust_segment_edge("end", 4_000)

    assert window.start_spin.value() == pytest.approx(1.0)
    assert window.end_spin.value() == pytest.approx(4.0)


def test_timeline_discloses_draggable_segment_edges(qt_app):
    from video_labeler.segment_timeline import SegmentTimelineSlider

    slider = SegmentTimelineSlider()
    slider.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    slider.resize(400, 32)
    slider.setRange(0, 100)
    slider.set_segment_range(25, 75)
    slider.show()
    qt_app.processEvents()

    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    groove = slider.style().subControlRect(
        QStyle.ComplexControl.CC_Slider,
        option,
        QStyle.SubControl.SC_SliderGroove,
        slider,
    )
    start_position = groove.x() + QStyle.sliderPositionFromValue(
        slider.minimum(), slider.maximum(), 25, max(0, groove.width() - 1)
    )

    local_position = QPointF(start_position, slider.height() / 2)
    global_position = QPointF(
        slider.mapToGlobal(QPoint(start_position, slider.height() // 2))
    )
    QApplication.sendEvent(
        slider,
        QMouseEvent(
            QEvent.Type.MouseMove,
            local_position,
            global_position,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )

    assert "拖动" in slider.toolTip()
    assert slider.cursor().shape() == Qt.CursorShape.SizeHorCursor
    slider.close()
    qt_app.processEvents()


def test_applying_reviewed_preannotations_adds_labeled_segments(qt_app, tmp_path):
    from video_labeler.preannotation_io import PreAnnotation

    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    window.date_edit.setText("20260818")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")

    window._apply_preannotations(
        [
            PreAnnotation(
                start_seconds=1.0,
                end_seconds=2.0,
                behaviors=("delivery_dropoff",),
                polarity="pos",
                lighting="daytime",
            )
        ]
    )

    assert window.records[0].behaviors == ("delivery_dropoff",)
    assert "delivery_dropoff" in window.project.custom_behavior_tags


def test_hotkey_rebinding_persists_and_rebuilds_window_shortcuts(qt_app, tmp_path):
    from video_labeler.preferences_io import DEFAULT_HOTKEYS, load_hotkey_preferences

    window = MainWindow()
    window._hotkey_preferences_path = tmp_path / "preferences.json"
    bindings = {**DEFAULT_HOTKEYS, "play_pause": "F5"}

    window.apply_hotkey_bindings(bindings)

    assert window.shortcuts["play_pause"].key() == QKeySequence("F5")
    assert load_hotkey_preferences(window._hotkey_preferences_path)["play_pause"] == "F5"


def test_log_panel_appends_copies_and_clears_operation_messages(qt_app):
    window = MainWindow()

    window._set_status("export started")
    window.copy_log()

    assert "export started" in window.log_panel.toPlainText()
    assert "export started" in QApplication.clipboard().text()
    window.clear_log()
    assert window.log_panel.toPlainText() == ""


def test_adding_custom_behavior_tag_partially_refreshes_editor_fields(
    qt_app, monkeypatch
):
    window = MainWindow()
    window.set_clip_range(3.0, 5.0)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.behaviors_group.setChecked(False)
    window.custom_behavior_tag_edit.setText("delivery_dropoff")

    refreshed_ranges = []
    original_set_clip_range = window.set_clip_range

    def capture_range_refresh(start_seconds: float, end_seconds: float) -> None:
        refreshed_ranges.append((start_seconds, end_seconds))
        original_set_clip_range(start_seconds, end_seconds)

    monkeypatch.setattr(window, "set_clip_range", capture_range_refresh)

    window.add_custom_behavior_tag()

    assert refreshed_ranges == [(3.0, 5.0)]
    assert "delivery_dropoff" in window.behavior_checks
    assert window.behaviors_group.isChecked() is False
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window.lighting_group.isChecked() is False
    assert window.polarity_group.isChecked() is False


def test_custom_field_group_lists_added_tag_for_removal(qt_app):
    window = MainWindow()

    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()
    window.custom_tags_group.setChecked(True)

    assert isinstance(window.custom_tags_group, CollapsibleGroupBox)
    assert window.custom_tag_library_combo.currentData() == "delivery_dropoff"
    assert window.remove_custom_behavior_tag_button.isEnabled()


def test_adding_custom_tag_preserves_fixed_group_collapse_states(qt_app):
    window = MainWindow()
    window.set_clip_range(3.0, 5.0)
    window.lighting_combo.setCurrentText("night_full_color")
    window.polarity_combo.setCurrentText("neg")
    window.behaviors_group.setChecked(False)
    window.lighting_group.setChecked(False)
    window.polarity_group.setChecked(False)
    window.custom_behavior_tag_edit.setText("delivery_dropoff")

    window.add_custom_behavior_tag()

    assert window.start_spin.value() == pytest.approx(3.0)
    assert window.end_spin.value() == pytest.approx(5.0)
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert not window.behaviors_group.isChecked()
    assert not window.lighting_group.isChecked()
    assert not window.polarity_group.isChecked()


def test_loading_project_restores_custom_behavior_tag_buttons(qt_app, tmp_path):
    project_path = tmp_path / "work.labelproj"
    window = MainWindow()
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()
    window._project_path = project_path

    window.save_project()

    restored = MainWindow()
    assert restored._load_project_path(project_path)
    assert restored.project.custom_behavior_tags == ["delivery_dropoff"]
    assert "delivery_dropoff" in restored.behavior_checks


def test_import_csv_registers_unknown_behavior_tag_in_active_project(
    qt_app, tmp_path, monkeypatch
):
    csv_path = tmp_path / "custom-behavior.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam02_panorama-delivery_dropoff-pos-daytime-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV files (*.csv)")),
    )

    window.import_csv()

    assert window.project.custom_behavior_tags == ["delivery_dropoff"]
    assert "delivery_dropoff" in window.behavior_checks
    assert window.records[0].behaviors == ("delivery_dropoff",)


def test_removing_custom_tag_keeps_selected_record_data_as_historical_tag(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()
    window.set_clip_range(1.0, 2.0)
    window.behavior_checks["delivery_dropoff"].setChecked(True)
    window.add_or_update_clip()
    window.task_table.selectRow(0)
    qt_app.processEvents()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )

    window._remove_custom_behavior_tag("delivery_dropoff")

    assert window.project.custom_behavior_tags == []
    assert window.records[0].behaviors == ("delivery_dropoff",)
    assert "delivery_dropoff" not in window.behavior_checks
    assert window.historical_behavior_tags == ("delivery_dropoff",)
    assert not window.historical_tag_labels["delivery_dropoff"].isEnabled()
    assert window.historical_tag_labels["delivery_dropoff"].toolTip().startswith(
        "[Historical Tag]"
    )
    assert window.selected_behaviors() == ("delivery_dropoff",)

    window.set_clip_range(1.0, 3.0)
    window.add_or_update_clip()

    assert window.records[0].behaviors == ("delivery_dropoff",)


def test_readding_historical_custom_tag_restores_an_interactive_selected_tag(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()
    window.set_clip_range(1.0, 2.0)
    window.behavior_checks["delivery_dropoff"].setChecked(True)
    window.add_or_update_clip()
    window.task_table.selectRow(0)
    qt_app.processEvents()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )
    window._remove_custom_behavior_tag("delivery_dropoff")
    window.custom_behavior_tag_edit.setText("delivery_dropoff")

    window.add_custom_behavior_tag()

    assert "delivery_dropoff" in window.behavior_checks
    assert window.behavior_checks["delivery_dropoff"].isChecked()
    assert "delivery_dropoff" not in window.historical_tag_labels


def test_selecting_custom_metadata_record_restores_all_metadata_combos(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="cam02.mp4",
            start_seconds=1,
            end_seconds=2,
            output=(
                "20260729-cam_02_doorway-dog_out-needs_review-night_red-001.mp4"
            ),
            behaviors=("dog_out",),
            polarity="needs_review",
            lighting="night_red",
            sequence=1,
        )
    ]
    window._refresh_table()

    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window.date_edit.text() == "20260729"
    assert window.camera_edit.text() == "cam_02"
    assert window.view_combo.currentText() == "doorway"
    assert window.polarity_combo.currentText() == "needs_review"
    assert window.lighting_combo.currentText() == "night_red"


def test_selecting_manually_renamed_record_restores_stored_custom_labels(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="cam02.mp4",
            start_seconds=1,
            end_seconds=2,
            output="manual.mp4",
            behaviors=("dog_out",),
            polarity="needs_review",
            lighting="night_red",
            sequence=1,
        )
    ]
    window._refresh_table()

    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window.polarity_combo.currentText() == "needs_review"
    assert window.polarity_combo.findText("needs_review") >= 0
    assert window.lighting_combo.currentText() == "night_red"
    assert window.lighting_combo.findText("night_red") >= 0


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


def test_shift_click_selects_the_continuous_segment_range(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=index,
            end_seconds=index + 1,
            output=f"clip-{index}.mp4",
            sequence=index,
        )
        for index in range(1, 4)
    ]
    window._refresh_table()

    QTest.mouseClick(
        window.task_table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        window.task_table.visualRect(window.task_table.model().index(0, 0)).center(),
    )
    QTest.mouseClick(
        window.task_table.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        window.task_table.visualRect(window.task_table.model().index(2, 0)).center(),
    )
    QTest.keyRelease(window.task_table, Qt.Key.Key_Shift)
    assert QApplication.keyboardModifiers() == Qt.KeyboardModifier.NoModifier

    assert [index.row() for index in window.task_table.selectionModel().selectedRows()] == [
        0,
        1,
        2,
    ]


def test_global_search_matches_tags_notes_and_source_filename(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="garage_camera.mp4",
            start_seconds=0,
            end_seconds=1,
            output="first.mp4",
            behaviors=("fall",),
            note="",
            sequence=1,
        ),
        ClipRecord(
            source="door_camera.mp4",
            start_seconds=1,
            end_seconds=2,
            output="second.mp4",
            behaviors=("dog_out",),
            note="needs human review",
            sequence=2,
        ),
    ]
    window._refresh_table()
    assert "2/2" in window.filter_result_label.text()

    window.search_edit.setText("fall")
    assert not window.task_table.isRowHidden(0)
    assert window.task_table.isRowHidden(1)

    window.search_edit.setText("HUMAN REVIEW")
    assert window.task_table.isRowHidden(0)
    assert not window.task_table.isRowHidden(1)

    window.search_edit.setText("garage_camera")
    assert not window.task_table.isRowHidden(0)
    assert window.task_table.isRowHidden(1)

    window.search_edit.setText("no matching segment")
    assert "0/2" in window.filter_result_label.text()
    assert "清空筛选" in window.filter_result_label.text()


def test_export_preview_shows_count_and_space_estimate_before_starting(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    source = tmp_path / "source.mp4"
    source.write_bytes(b"x" * 4096)
    window.output_dir = tmp_path / "exports"
    record = ClipRecord(
        source=source.name,
        start_seconds=2,
        end_seconds=4,
        output="clip.mp4",
        sequence=1,
    )
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda _parent, title, text, *_args: (
                messages.append((title, text))
                or QMessageBox.StandardButton.No
            )
        ),
    )

    window._start_export([record], [source])

    assert window._export_worker is None
    assert messages and messages[0][0] == "导出预览"
    assert "1" in messages[0][1]
    assert "预计" in messages[0][1]


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
    window.behavior_checks["dog_out"].setChecked(True)
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


@pytest.mark.parametrize(("width", "height"), ((1120, 720), (1440, 900)))
def test_page_scroll_keeps_video_and_annotation_in_top_workspace(
    qt_app, width, height, tmp_path
):
    window = MainWindow()
    window.resize(width, height)
    window.show()
    window.set_source_path(tmp_path / "source.mp4")
    qt_app.processEvents()

    assert isinstance(window.main_content_scroll, QScrollArea)
    assert window.main_content_scroll.verticalScrollBar().maximum() > 0
    assert window.main_content_scroll.horizontalScrollBar().maximum() == 0
    assert window.main_content_scroll.widget() is window.workspace_content
    layout = window.workspace_row.layout()
    assert layout.itemAt(0).widget() is window.video_panel
    assert layout.itemAt(1).widget() is window.annotation_workspace
    assert window.workspace_row.contentsRect().contains(
        window.video_panel.geometry()
    )
    assert window.workspace_row.contentsRect().contains(
        window.annotation_workspace.geometry()
    )
    assert window.annotation_workspace.contentsRect().contains(
        window.annotation_panel.geometry()
    )
    annotation_rect = window.annotation_panel.contentsRect()
    annotation_controls = (
        window.add_button,
        window.remove_button,
        window.undo_button,
        window.redo_button,
        window.clear_button,
        window.behavior_tag_combo,
    )
    assert all(
        annotation_rect.contains(control.mapTo(window.annotation_panel, QPoint()))
        and annotation_rect.contains(
            control.mapTo(
                window.annotation_panel,
                QPoint(control.width() - 1, control.height() - 1),
            )
        )
        for control in annotation_controls
    )
    assert window.task_panel.parentWidget() is window.workspace_content
    assert window.video_panel.isVisible()
    assert window.annotation_panel.isVisible()


def test_task_table_is_below_workspace_and_rejoins_page_after_detach(qt_app):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content
    assert window.workspace_content.layout().indexOf(window.task_panel) > (
        window.workspace_content.layout().indexOf(window.workspace_row)
    )

    window._show_task_table_dialog()
    qt_app.processEvents()
    window.task_table_dialog.close()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content


def test_workspace_uses_two_parallel_panels(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    layout = window.workspace_row.layout()
    assert layout.count() == 2
    assert layout.itemAt(0).widget() is window.video_panel
    assert layout.itemAt(1).widget() is window.annotation_workspace


def test_right_side_modules_are_collapsible_groups(qt_app):
    window = MainWindow()

    assert isinstance(window.behaviors_group, CollapsibleGroupBox)
    assert isinstance(window.custom_tags_group, CollapsibleGroupBox)
    assert isinstance(window.lighting_group, CollapsibleGroupBox)
    assert isinstance(window.polarity_group, CollapsibleGroupBox)
    assert isinstance(window.task_panel, CollapsibleGroupBox)


def test_task_table_keeps_a_usable_page_section(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.isChecked()
    assert window.task_table.height() >= 200
    assert window.task_panel.parentWidget() is window.workspace_content


def test_video_panel_receives_about_fifty_two_percent_of_workspace(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    video_width = window.video_panel.width()
    annotation_width = window.annotation_workspace.width()
    assert video_width / (video_width + annotation_width) == pytest.approx(
        0.52, abs=0.04
    )


def test_toolbar_uses_three_semantic_action_groups(qt_app):
    window = MainWindow()

    assert window.import_csv_action_group.objectName() == "importCsvActionGroup"
    assert window.export_output_action_group.objectName() == "exportOutputActionGroup"
    assert (
        window.settings_operation_action_group.objectName()
        == "settingsOperationActionGroup"
    )
    assert not window.advanced_export_group.isChecked()


def test_project_settings_card_is_expanded_and_collapsible(qt_app):
    window = MainWindow()

    assert isinstance(window.project_header, CollapsibleGroupBox)
    assert window.project_header.isChecked()
    assert window.project_header._content is window.project_settings_content
    assert window.project_settings_content.isAncestorOf(
        window.open_video_button
    )


def test_annotation_actions_use_primary_and_secondary_rows_without_clipping(qt_app):
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    qt_app.processEvents()

    primary_y = window.add_button.mapTo(
        window.annotation_panel, QPoint(0, 0)
    ).y()
    secondary_y = {
        control.mapTo(window.annotation_panel, QPoint(0, 0)).y()
        for control in (
            window.remove_button,
            window.undo_button,
            window.redo_button,
            window.clear_button,
        )
    }
    panel_rect = window.annotation_panel.contentsRect()
    actions = (
        window.add_button,
        window.remove_button,
        window.undo_button,
        window.redo_button,
        window.clear_button,
    )

    assert primary_y < min(secondary_y)
    assert len(secondary_y) == 1
    assert all(
        panel_rect.contains(action.mapTo(window.annotation_panel, QPoint()))
        and panel_rect.contains(
            action.mapTo(
                window.annotation_panel,
                QPoint(action.width() - 1, action.height() - 1),
            )
        )
        for action in actions
    )


def test_lighting_and_polarity_use_independent_collapsible_groups(qt_app):
    window = MainWindow()

    assert isinstance(window.lighting_group, QGroupBox)
    assert isinstance(window.polarity_group, QGroupBox)
    assert window.lighting_group.isCheckable()
    assert window.polarity_group.isCheckable()
    assert not window.lighting_group.isChecked()
    assert not window.polarity_group.isChecked()


def test_lighting_and_polarity_titles_summarize_selected_values(qt_app):
    window = MainWindow()

    window.lighting_combo.setCurrentText("night_full_color")
    window.polarity_combo.setCurrentText("neg")

    assert window.lighting_group.title() == "光照条件：night_full_color"
    assert window.polarity_group.title() == "正负例：neg"


def test_output_path_is_elided_with_a_full_path_tooltip(qt_app):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()
    window.output_dir = Path(
        "C:/very-long-output-directory/with-many-subdirectories/"
        "and-a-dataset-name-that-must-not-overflow-the-toolbar"
    )

    window._set_output_folder_display()

    assert window.output_folder_label.toolTip() == str(window.output_dir)
    assert "…" in window.output_folder_label.text()


def test_selecting_output_folder_refreshes_elided_path_display(
    qt_app, monkeypatch
):
    selected = (
        "C:/very-long-output-directory/with-many-subdirectories/"
        "and-a-dataset-name-that-must-not-overflow-the-toolbar"
    )
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: selected),
    )

    window.select_output_folder()

    assert window.output_folder_label.toolTip() == str(Path(selected))
    assert "…" in window.output_folder_label.text()


def test_card_workspace_uses_semantic_cards_without_overlapping_video_controls(
    qt_app,
):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    assert window.project_header.objectName() == "toolbarCard"
    assert window.video_panel.objectName() == "videoCard"
    assert window.annotation_panel.objectName() == "annotationCard"
    assert window.task_panel.objectName() == "taskCard"
    assert window.video_controls_panel.geometry().top() > (
        window.video_widget.geometry().bottom()
    )
    assert window.video_panel.graphicsEffect() is not None


def test_refined_visual_sections_keep_existing_controls_semantic(qt_app):
    window = MainWindow()
    window.show()
    qt_app.processEvents()

    assert window.import_csv_action_group.objectName() == "importCsvActionGroup"
    assert (
        window.export_output_action_group.objectName()
        == "exportOutputActionGroup"
    )
    assert (
        window.settings_operation_action_group.objectName()
        == "settingsOperationActionGroup"
    )
    assert window.playback_rate_badge.objectName() == "playbackRateBadge"
    assert window.table_filter_bar.objectName() == "tableFilterBar"
    assert window.table_action_bar.objectName() == "tableActionBar"
    assert window.task_table.alternatingRowColors()
    assert all(
        not button.icon().isNull()
        for button in (
            window.play_button,
            window.seek_back_button,
            window.seek_forward_button,
        )
    )


def test_video_scene_overlay_tracks_empty_loading_and_loaded_states(qt_app):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    overlay = window.video_placeholder_item
    assert overlay.isVisible()
    assert overlay.text() == "导入视频后开始标注"

    window._update_video_placeholder(QMediaPlayer.MediaStatus.LoadingMedia)
    assert overlay.isVisible()
    assert overlay.text() == "正在加载视频…"

    window._update_video_placeholder(QMediaPlayer.MediaStatus.LoadedMedia)
    assert not overlay.isVisible()

    window._resize_video_item()
    overlay_center = overlay.pos() + overlay.boundingRect().center()
    scene_center = window.video_scene.sceneRect().center()
    assert overlay_center.x() == pytest.approx(scene_center.x(), abs=1.0)
    assert overlay_center.y() == pytest.approx(scene_center.y(), abs=1.0)


@pytest.mark.parametrize(("width", "height"), ((1120, 720), (1440, 900)))
def test_refined_video_controls_fit_without_text_clipping(qt_app, width, height):
    window = MainWindow()
    window.resize(width, height)
    window.show()
    qt_app.processEvents()

    controls = (
        window.play_button,
        window.seek_back_button,
        window.seek_forward_button,
        window.set_start_button,
        window.set_end_button,
        window.playback_rate_badge,
        window.speed_combo,
        window.custom_speed_spin,
    )
    parent_rect = window.video_controls_panel.contentsRect()

    assert window.video_controls_panel.geometry().top() > (
        window.video_widget.geometry().bottom()
    )
    assert all(
        control.width() >= control.sizeHint().width()
        and parent_rect.contains(control.geometry())
        for control in controls
    )


def test_task_table_defaults_to_bottom_card_and_can_detach_and_restore(qt_app):
    window = MainWindow()
    window.records = [_clip_record("source.mp4", 1)]
    window._refresh_table()

    assert window.task_panel.parentWidget() is window.workspace_content

    window._show_task_table_dialog()
    qt_app.processEvents()

    assert window.task_table_dialog.isVisible()
    assert window.task_panel.parentWidget() is window.task_table_dialog
    assert window.task_table_dialog.findChild(QTableWidget) is window.task_table

    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window._editing_index == 0

    window.task_table_dialog.close()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content
    assert window.task_table.currentRow() == 0


def test_narrow_window_keeps_embedded_table_until_user_detaches_it(qt_app):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content

    window.detach_table_button.click()

    assert window.task_table_dialog.isVisible()


def test_video_preview_keeps_clearance_from_timeline_and_controls(qt_app):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    video_panel = window.video_widget.parentWidget()
    preview_bottom = window.video_widget.mapTo(
        video_panel,
        QPoint(0, window.video_widget.height()),
    ).y()
    timeline_top = window.timeline_slider.mapTo(video_panel, QPoint(0, 0)).y()
    timeline_bottom = window.timeline_slider.mapTo(
        video_panel,
        QPoint(0, window.timeline_slider.height()),
    ).y()
    controls = (
        window.play_button,
        window.seek_back_button,
        window.seek_forward_button,
        window.set_start_button,
        window.set_end_button,
        window.speed_combo,
    )

    assert window.video_widget.minimumHeight() >= 280
    assert preview_bottom + 14 < timeline_top
    assert all(
        timeline_bottom + 6
        <= control.mapTo(video_panel, QPoint(0, 0)).y()
        for control in controls
    )


def test_video_preview_uses_graphics_surface_that_stays_inside_its_viewport(
    qt_app,
):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    assert isinstance(window.video_widget, QGraphicsView)
    assert window.player.videoOutput() is window.video_item
    assert window.video_item.size().width() == pytest.approx(
        window.video_widget.viewport().width()
    )
    assert window.video_item.size().height() == pytest.approx(
        window.video_widget.viewport().height()
    )


def test_video_progress_and_controls_use_a_dedicated_panel_below_preview(qt_app):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    controls = (
        window.play_button,
        window.seek_back_button,
        window.seek_forward_button,
        window.set_start_button,
        window.set_end_button,
        window.speed_combo,
    )

    assert window.video_controls_panel.isVisible()
    assert window.video_widget.geometry().bottom() + 8 < (
        window.video_controls_panel.geometry().top()
    )
    assert window.timeline_slider.parentWidget() is window.video_controls_panel
    assert window.timeline_slider.minimumHeight() >= 28
    assert all(
        control.parentWidget() is window.video_controls_panel for control in controls
    )


def test_add_clip_action_appears_before_behavior_choices(qt_app):
    window = MainWindow()
    window.resize(1366, 768)
    window.show()
    qt_app.processEvents()

    add_clip_y = window.add_button.mapTo(
        window.annotation_workspace, QPoint(0, 0)
    ).y()
    behaviors_y = window.behaviors_group.mapTo(
        window.annotation_workspace, QPoint(0, 0)
    ).y()

    assert add_clip_y < behaviors_y
