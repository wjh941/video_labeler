import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from video_labeler import csv_io, project_io
from video_labeler.models import ClipRecord, EventRecord
from video_labeler.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _event_record():
    return ClipRecord(
        source="camera.mp4",
        start_seconds=1.0,
        end_seconds=2.0,
        output="clip.mp4",
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=1,
        status="ok",
        error="",
        note="",
        data_stratum="hard_pos",
        events=[
            EventRecord("dog_out", 100, 800),
            EventRecord("fall", 300, 900),
        ],
        age="adult",
        face_familiarity="familiar",
        reid_familiarity="unfamiliar",
        person_count=2,
    )


def test_project_io_roundtrips_events():
    record = _event_record()
    project = project_io.new_project()
    project.videos = [
        project_io.ProjectVideo(
            id="v1",
            path=Path("C:/tmp/v.mp4"),
            segments=[record],
        )
    ]
    project.active_video_id = "v1"

    restored = project_io.project_from_dict(project_io.project_to_dict(project))
    restored_record = restored.videos[0].segments[0]
    assert restored_record.events == record.events
    assert restored_record.age == "adult"
    assert restored_record.face_familiarity == "familiar"
    assert restored_record.reid_familiarity == "unfamiliar"
    assert restored_record.person_count == 2


def test_full_csv_roundtrips_events(tmp_path):
    record = _event_record()
    path = tmp_path / "events.csv"
    csv_io.write_full_clip_csv(path, [record])
    restored = csv_io.read_full_clip_csv(path)
    assert restored[0].events == record.events
    assert restored[0].age == "adult"
    assert restored[0].face_familiarity == "familiar"
    assert restored[0].reid_familiarity == "unfamiliar"
    assert restored[0].person_count == 2


def test_ui_collects_clears_and_restores_events(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("pos")
    window.lighting_combo.setCurrentText("daytime")
    window.set_clip_range(1.0, 2.0)
    window.behavior_checks["dog_out"].setChecked(True)

    window._add_event_row("dog_out", 100, 800)
    window._add_event_row("fall", 300, 900)

    assert window.add_or_update_clip()
    assert len(window.records) == 1
    assert window.records[0].events == [
        EventRecord("dog_out", 100, 800),
        EventRecord("fall", 300, 900),
    ]

    window.clear_editor()
    assert window._collect_events() == []

    window.task_table.selectRow(0)
    window._load_selected_clip()
    assert window._collect_events() == [
        EventRecord("dog_out", 100, 800),
        EventRecord("fall", 300, 900),
    ]


def test_ui_collects_and_restores_person_attributes(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("pos")
    window.lighting_combo.setCurrentText("daytime")
    window.set_clip_range(1.0, 2.0)
    window.behavior_checks["dog_out"].setChecked(True)

    window.age_combo.setCurrentIndex(window.age_combo.findData("adult"))
    window.face_familiarity_combo.setCurrentIndex(
        window.face_familiarity_combo.findData("familiar")
    )
    window.reid_familiarity_combo.setCurrentIndex(
        window.reid_familiarity_combo.findData("unfamiliar")
    )
    window.person_count_spin.setValue(2)

    assert window.add_or_update_clip()
    assert len(window.records) == 1
    record = window.records[0]
    assert record.age == "adult"
    assert record.face_familiarity == "familiar"
    assert record.reid_familiarity == "unfamiliar"
    assert record.person_count == 2

    window.clear_editor()
    assert window.age_combo.currentData() == ""
    assert window.person_count_spin.value() == 0

    window.task_table.selectRow(0)
    window._load_selected_clip()
    assert window.age_combo.currentData() == "adult"
    assert window.face_familiarity_combo.currentData() == "familiar"
    assert window.reid_familiarity_combo.currentData() == "unfamiliar"
    assert window.person_count_spin.value() == 2
