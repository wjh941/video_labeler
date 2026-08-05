import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from video_labeler.themes import apply_light_fresh_theme, load_light_fresh_theme


def test_light_fresh_theme_loads_global_dialog_and_tooltip_rules():
    app = QApplication.instance() or QApplication([])

    apply_light_fresh_theme(app)

    stylesheet = load_light_fresh_theme()
    assert app.styleSheet() == stylesheet
    assert "#f7f8fa" in stylesheet
    assert "#1677ff" in stylesheet
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
    assert "QFileDialog QAbstractItemView" in stylesheet
    assert "QFileDialog QAbstractScrollArea::viewport" in stylesheet
    assert "background: #ffffff;" in stylesheet
    assert "color: #1f2329;" in stylesheet
    assert "selection-background-color: #e8f3ff;" in stylesheet


def test_light_theme_contains_card_workspace_selectors():
    stylesheet = load_light_fresh_theme()

    for selector in (
        "QGroupBox#toolbarCard",
        "QGroupBox#videoCard",
        "QGroupBox#annotationCard",
        "QGroupBox#taskCard",
        "QWidget#videoControlsPanel",
        "QWidget#importCsvActionGroup",
        "QWidget#exportOutputActionGroup",
        "QWidget#settingsOperationActionGroup",
        "QLabel#playbackRateBadge",
        "QWidget#tableFilterBar",
        "QWidget#tableActionBar",
        "QComboBox#behaviorTagCombo",
        "QComboBox#customTagLibraryCombo",
        "QLabel#historicalBehaviorTag",
        "QTableWidget::item:alternate",
    ):
        assert selector in stylesheet
    assert "QCheckBox#behaviorTag" not in stylesheet
    assert "QCheckBox#customBehaviorTag" not in stylesheet


def test_light_theme_styles_fixed_screen_workspace_panels():
    theme = load_light_fresh_theme()

    assert "QWidget#workspaceRow" in theme
    assert "QWidget#annotationWorkspace" in theme
    assert "QGroupBox#taskCard" in theme


def test_light_theme_contains_ant_desktop_tokens_and_eight_pixel_radius():
    stylesheet = load_light_fresh_theme()

    for token in (
        "#f7f8fa",
        "#ffffff",
        "#1677ff",
        "#4096ff",
        "#ff7875",
        "#f2f3f5",
        "#4e5969",
        "#1f2329",
        "#86909c",
        "#e5e6eb",
        "border-radius: 8px",
    ):
        assert token in stylesheet
