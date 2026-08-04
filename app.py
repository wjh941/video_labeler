import sys

from PySide6.QtWidgets import QApplication

from video_labeler.themes import apply_light_fresh_theme
from video_labeler.ui.main_window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Video Segment Labeler")
    apply_light_fresh_theme(application)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
