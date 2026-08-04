import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

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


def main() -> int:
    configure_qt_runtime()
    application = QApplication(sys.argv)
    application.setApplicationName("Video Segment Labeler")
    apply_light_fresh_theme(application)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
