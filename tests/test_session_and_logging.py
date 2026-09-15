import logging
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from video_labeler import logging_setup, session_io
from video_labeler.ui.main_window import MainWindow


@pytest.fixture()
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def isolated_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(logging_setup, "_CONFIGURED", False)
    logger = logging.getLogger(logging_setup.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    yield tmp_path
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logging_setup._CONFIGURED = False


def test_setup_logging_creates_one_rotating_file(isolated_appdata):
    directory = logging_setup.setup_logging()
    assert directory == isolated_appdata / "VideoSegmentLabeler" / "logs"
    logging_setup.setup_logging()  # repeated calls must not stack handlers
    logger = logging.getLogger(logging_setup.LOGGER_NAME)
    assert len(logger.handlers) == 1
    logger.info("导入视频 测试消息")
    for handler in logger.handlers:
        handler.flush()
    text = (directory / "app.log").read_text(encoding="utf-8")
    assert "导入视频 测试消息" in text


def test_session_roundtrip_survives_corruption(isolated_appdata):
    assert session_io.load_session() == {}
    session_io.save_session(
        project_path=Path("D:/labels/demo.labelproj"),
        video_path="D:/merged/a.mp4",
        position_ms=83_500,
    )
    state = session_io.load_session()
    assert state["project_path"] == "D:\\labels\\demo.labelproj"
    assert state["video_path"] == "D:/merged/a.mp4"
    assert state["position_ms"] == 83_500
    session_io.session_path().write_text("{corrupt", encoding="utf-8")
    assert session_io.load_session() == {}
    session_io.clear_session()
    assert session_io.load_session() == {}


def test_main_window_persists_session_on_source_selection(
    qt_app, isolated_appdata
):
    video = isolated_appdata / "clips" / "demo.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    window = MainWindow()
    try:
        window.set_source_path(video)
        window._persist_session()
        state = session_io.load_session()
        assert state["video_path"] == str(video)
    finally:
        window.deleteLater()


def test_apply_session_state_restores_video_without_project(
    qt_app, isolated_appdata
):
    video = isolated_appdata / "clips" / "demo.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    window = MainWindow()
    try:
        restored = window.apply_session_state(
            {
                "version": 1,
                "project_path": None,
                "video_path": str(video),
                "position_ms": 61_200,
            }
        )
        assert restored is True
        assert window.source_path == video
        assert window._pending_restore_position_ms == 61_200
    finally:
        window.deleteLater()
