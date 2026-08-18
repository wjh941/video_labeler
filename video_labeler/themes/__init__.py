"""Application-wide Qt themes."""

from pathlib import Path
import re

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory


_LIGHT_FRESH_QSS = Path(__file__).with_name("light_fresh.qss")
_DARK_COLOR_TOKENS = {
    "#1677ff": "#5aa9ff",
    "#1f2329": "#eef3fb",
    "#4096ff": "#7cbbff",
    "#4e5969": "#c4cfde",
    "#86909c": "#9eabba",
    "#a9aeb8": "#68778a",
    "#c9cdd4": "#536174",
    "#d9ecff": "#2d4d75",
    "#e5e6eb": "#3a4658",
    "#e8f3ff": "#273d5a",
    "#f2f3f5": "#293342",
    "#f7f8fa": "#151b25",
    "#ff7875": "#ff8d8a",
    "#ff9c99": "#ffa7a4",
    "#ffffff": "#202936",
}
_DARK_COLOR_PATTERN = re.compile(
    "|".join(re.escape(token) for token in _DARK_COLOR_TOKENS), re.IGNORECASE
)


def load_light_fresh_theme() -> str:
    """Return the bundled fresh light Qt stylesheet."""
    return _LIGHT_FRESH_QSS.read_text(encoding="utf-8")


def apply_light_fresh_theme(app: QApplication) -> None:
    """Apply the Fusion base style and the fresh light stylesheet."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(load_light_fresh_theme())


def load_dark_fresh_theme() -> str:
    """Return a dark variant covering the same widget selectors as the light theme."""
    stylesheet = _DARK_COLOR_PATTERN.sub(
        lambda match: _DARK_COLOR_TOKENS[match.group().lower()],
        load_light_fresh_theme(),
    )
    return stylesheet + """
QGraphicsView#videoSurface,
QGraphicsView#videoSurface::viewport {
    background: #090e16;
}

QPlainTextEdit,
QTextEdit,
QKeySequenceEdit {
    background: #202936;
    border: 1px solid #3a4658;
    border-radius: 8px;
    color: #eef3fb;
    selection-background-color: #273d5a;
    selection-color: #eef3fb;
}
"""


def apply_dark_fresh_theme(app: QApplication) -> None:
    """Apply the Fusion base style and the complete dark stylesheet."""
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = app.style().standardPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#151b25"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#202936"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#293342"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#293342"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#eef3fb"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#eef3fb"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#eef3fb"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#5aa9ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#151b25"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9eabba"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#202936"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#eef3fb"))
    app.setPalette(palette)
    app.setStyleSheet(load_dark_fresh_theme())
