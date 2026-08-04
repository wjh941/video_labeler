import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from video_labeler.themes import apply_light_fresh_theme, load_light_fresh_theme


def test_light_fresh_theme_loads_global_dialog_and_tooltip_rules():
    app = QApplication.instance() or QApplication([])

    apply_light_fresh_theme(app)

    stylesheet = load_light_fresh_theme()
    assert app.styleSheet() == stylesheet
    assert "#F5F7FA" in stylesheet
    assert "#409EFF" in stylesheet
    for selector in (
        "QDialog",
        "QMessageBox",
        "QInputDialog",
        "QFileDialog",
        "QToolTip",
    ):
        assert selector in stylesheet


def test_light_theme_keeps_file_dialog_browser_views_unforced():
    stylesheet = load_light_fresh_theme()

    assert "QFileDialog QListView" not in stylesheet
    assert "QFileDialog QTreeView" not in stylesheet
    assert "QFileDialog {" in stylesheet
    assert "QFileDialog QLineEdit" in stylesheet
    assert "QFileDialog QPushButton" in stylesheet
    assert "QFileDialog QComboBox" in stylesheet
