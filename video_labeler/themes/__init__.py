"""Application-wide Qt themes."""

from pathlib import Path

from PySide6.QtWidgets import QApplication, QStyleFactory


_LIGHT_FRESH_QSS = Path(__file__).with_name("light_fresh.qss")


def load_light_fresh_theme() -> str:
    """Return the bundled fresh light Qt stylesheet."""
    return _LIGHT_FRESH_QSS.read_text(encoding="utf-8")


def apply_light_fresh_theme(app: QApplication) -> None:
    """Apply the Fusion base style and the fresh light stylesheet."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(load_light_fresh_theme())
