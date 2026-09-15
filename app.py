import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from video_labeler.logging_setup import app_logger, setup_logging
from video_labeler.session_io import load_session
from video_labeler.themes import apply_light_fresh_theme
from video_labeler.ui.main_window import MainWindow


def configure_qt_runtime() -> None:
    """Configure Windows rendering before Qt creates the application object."""
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_OPENGL", "software")

    for attribute_name in ("AA_UseHighDpiPixmaps", "AA_UseSoftwareOpenGL"):
        attribute = getattr(Qt.ApplicationAttribute, attribute_name, None)
        if attribute is not None:
            QApplication.setAttribute(attribute, True)

    rounding_policy = getattr(
        Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough", None
    )
    if rounding_policy is not None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(rounding_policy)


def _install_crash_logger() -> None:
    """Write uncaught exceptions to the log file before the process dies."""
    logger = app_logger()

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        try:
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "程序遇到错误",
                    "发生未处理的错误，详情已写入日志文件。\n"
                    f"{exc_type.__name__}: {exc_value}",
                )
        except Exception:  # noqa: BLE001 - crash reporting must never crash
            pass

    sys.excepthook = _hook


def _offer_session_restore(window: MainWindow) -> None:
    """Offer to continue where the previous run left off."""
    state = load_session()
    if not state.get("project_path") and not state.get("video_path"):
        return
    lines = []
    if state.get("project_path"):
        lines.append(f"工程：{state['project_path']}")
    if state.get("video_path"):
        lines.append(f"视频：{state['video_path']}")
    total_seconds = int(state.get("position_ms") or 0) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    lines.append(f"上次播放位置：{minutes}:{seconds:02d}")
    answer = QMessageBox.question(
        window,
        "恢复上次会话",
        "检测到上次的工作状态：\n" + "\n".join(lines) + "\n\n是否恢复？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer == QMessageBox.StandardButton.Yes:
        window.apply_session_state(state)


def main() -> int:
    configure_qt_runtime()
    log_dir = setup_logging()
    app_logger().info("=== 应用启动，日志目录：%s ===", log_dir)
    _install_crash_logger()
    application = QApplication(sys.argv)
    application.setApplicationName("Video Segment Labeler")
    apply_light_fresh_theme(application)
    window = MainWindow()
    window.show()
    _offer_session_restore(window)
    exit_code = application.exec()
    app_logger().info("=== 应用退出（code=%s）===", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
