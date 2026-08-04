# Light Fresh Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a globally consistent fresh light Qt theme, migrate all MainWindow QSS into an external asset, use styled Qt file dialogs, and animate behavior-tag expansion without changing annotation or export behavior.

**Architecture:** A new `video_labeler.themes` package owns QSS loading and application-wide Fusion styling. `app.py` applies the theme before constructing `MainWindow`; `main_window.py` retains its existing widget hierarchy and business methods while replacing inline styles with semantic object names, non-native file-dialog options, and an internally animated `CollapsibleGroupBox`.

**Tech Stack:** Python 3.11, PySide6, Qt Style Sheets, Qt property animations, pytest.

## Global Constraints

- Keep all clip refresh behavior, video playback, CSV import/export, filename construction, FFmpeg commands, and export-worker behavior unchanged.
- Keep English values in `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, and `VIEW_TYPES` unchanged.
- Preserve `CollapsibleGroupBox` inheritance, checkable state, `set_content()` interface, and external caller behavior.
- Remove every inline `setStyleSheet()` string from `video_labeler/ui/main_window.py`.
- Create `video_labeler/themes/light_fresh.qss` as the single stylesheet source and apply it to `QApplication` before creating `MainWindow`.
- Force all open, save, and folder `QFileDialog` calls to use `DontUseNativeDialog`.
- Use a 300ms content-height and chevron-rotation animation for the behavior-tag group.
- Do not merge, push, or create a pull request. Work remains on `feature/video-segment-labeler-zh`.

---

### Task 1: Add The Global Theme Package And Bootstrap

**Files:**
- Create: `video_labeler/themes/__init__.py`
- Create: `video_labeler/themes/light_fresh.qss`
- Create: `tests/test_themes.py`
- Modify: `app.py:1-14`

**Interfaces:**
- Produces: `load_light_fresh_theme() -> str`
- Produces: `apply_light_fresh_theme(app: QApplication) -> None`
- Consumes: `QApplication` from `PySide6.QtWidgets`

- [ ] **Step 1: Write a failing test for the external global theme**

Create `tests/test_themes.py`:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from video_labeler.themes import apply_light_fresh_theme, load_light_fresh_theme


def test_light_fresh_theme_loads_global_dialog_and_tooltip_rules():
    app = QApplication.instance() or QApplication([])

    apply_light_fresh_theme(app)

    stylesheet = load_light_fresh_theme()
    assert app.style().objectName().lower() == "fusion"
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
```

- [ ] **Step 2: Run the theme test and verify it fails because the package does not exist**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py -v
```

Expected: FAIL during collection with `ModuleNotFoundError` for
`video_labeler.themes`.

- [ ] **Step 3: Create the theme loader and application bootstrap**

Create `video_labeler/themes/__init__.py`:

```python
from pathlib import Path

from PySide6.QtWidgets import QApplication, QStyleFactory


_LIGHT_FRESH_QSS = Path(__file__).with_name("light_fresh.qss")


def load_light_fresh_theme() -> str:
    return _LIGHT_FRESH_QSS.read_text(encoding="utf-8")


def apply_light_fresh_theme(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(load_light_fresh_theme())
```

Update `app.py`:

```python
from video_labeler.themes import apply_light_fresh_theme
from video_labeler.ui.main_window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Video Segment Labeler")
    apply_light_fresh_theme(application)
    window = MainWindow()
    window.show()
    return application.exec()
```

Create `video_labeler/themes/light_fresh.qss` with this complete shared
baseline. Task 2 extends the same file with all semantic object selectors:

```css
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog {
    background: #F5F7FA;
    color: #303133;
}

QWidget {
    color: #303133;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

QToolTip {
    background: #FFFFFF;
    color: #303133;
    border: 1px solid #DCDFE6;
    border-radius: 4px;
    padding: 5px 7px;
}

QDialogButtonBox {
    border-top: 1px solid #EBEEF5;
    padding-top: 10px;
}

QPushButton {
    min-height: 30px;
    padding: 4px 12px;
    background: #FFFFFF;
    border: 1px solid #DCDFE6;
    border-radius: 6px;
    color: #303133;
}

QPushButton:hover {
    background: #ECF5FF;
    border-color: #A0CFFF;
    color: #409EFF;
}

QPushButton#primaryButton, QPushButton#addClipButton {
    background: #409EFF;
    border-color: #409EFF;
    color: #FFFFFF;
}

QPushButton#primaryButton:hover, QPushButton#addClipButton:hover {
    background: #66B1FF;
    border-color: #66B1FF;
    color: #FFFFFF;
}
```

- [ ] **Step 4: Run the theme test and verify it passes**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py -v
```

Expected: PASS. The application uses Fusion and the external stylesheet contains
the required palette and top-level dialog selectors.

- [ ] **Step 5: Commit the theme bootstrap**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add app.py video_labeler/themes tests/test_themes.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: add global light theme"
```

### Task 2: Extract MainWindow Styles And Use Styled File Dialogs

**Files:**
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `video_labeler/ui/main_window.py:129-267`
- Modify: `video_labeler/ui/main_window.py:269-574`
- Modify: `video_labeler/ui/main_window.py:777-864`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `apply_light_fresh_theme()` from Task 1 at application startup.
- Preserves: all existing `MainWindow` methods, controls, signals, record
  state, button names, and `QFileDialog` return values.
- Produces: `MainWindow` with no inline QSS and file picker calls carrying
  `QFileDialog.Option.DontUseNativeDialog`.

- [ ] **Step 1: Add failing tests for semantic style hooks and non-native dialogs**

Add these tests to `tests/test_main_window.py`:

```python
def test_main_window_uses_semantic_style_object_names(qt_app):
    window = MainWindow()

    assert window.output_folder_label.objectName() == "mutedLabel"
    assert window.source_label.objectName() == "mutedLabel"
    assert window.video_widget.objectName() == "videoSurface"
    assert window.behaviors_group.objectName() == "collapsibleBehaviorGroup"


def test_file_dialogs_request_non_native_windows(qt_app, monkeypatch):
    window = MainWindow()
    dialog_options = []

    def open_file_name(*_args, **kwargs):
        dialog_options.append(kwargs["options"])
        return "", ""

    def save_file_name(*_args, **kwargs):
        dialog_options.append(kwargs["options"])
        return "", ""

    def existing_directory(*_args, **kwargs):
        dialog_options.append(kwargs["options"])
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
        option & QFileDialog.Option.DontUseNativeDialog
        for option in dialog_options
    )
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "semantic_style_object_names or file_dialogs_request_non_native_windows"
```

Expected: FAIL because the muted labels and video widget have inline styles but
no semantic names, the behavior group has no style name, and file-dialog calls
do not yet pass `options`.

- [ ] **Step 3: Move all MainWindow QSS rules into the external stylesheet**

Delete the complete `self.setStyleSheet(...)` block from `_build_ui()` and
remove the inline label/video `setStyleSheet()` calls. Set the object names:

```python
self.output_folder_label.setObjectName("mutedLabel")
self.video_widget.setObjectName("videoSurface")
self.source_label.setObjectName("mutedLabel")
self.behaviors_group.setObjectName("collapsibleBehaviorGroup")
```

Retain the existing `primaryButton`, `addClipButton`, and `dangerButton`
object names. Increase only layout margins and spacing in the existing layouts;
do not add, remove, or reorder widgets.

Extend `light_fresh.qss` with all required widget rules:

```css
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #DCDFE6;
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #303133;
}

QLabel#mutedLabel {
    color: #909399;
}

QWidget#videoSurface {
    background: #1F2937;
    border: 1px solid #DCDFE6;
    border-radius: 6px;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 28px;
    padding: 2px 8px;
    background: #FFFFFF;
    border: 1px solid #DCDFE6;
    border-radius: 6px;
    selection-background-color: #C6E2FF;
    selection-color: #303133;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #409EFF;
}

QTableWidget {
    background: #FFFFFF;
    color: #303133;
    gridline-color: #EBEEF5;
    selection-background-color: #ECF5FF;
    selection-color: #303133;
    border: 1px solid #DCDFE6;
    border-radius: 6px;
}

QTableWidget::item {
    padding: 4px 7px;
}

QTableWidget::item:selected {
    background: #ECF5FF;
    color: #303133;
}

QHeaderView::section {
    background: #F5F7FA;
    color: #606266;
    border: 0;
    border-right: 1px solid #EBEEF5;
    border-bottom: 1px solid #DCDFE6;
    padding: 6px;
    font-weight: 600;
}

QCheckBox {
    color: #606266;
    spacing: 7px;
}

QCheckBox::indicator {
    width: 15px;
    height: 15px;
    background: #FFFFFF;
    border: 1px solid #C0C4CC;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background: #409EFF;
    border-color: #409EFF;
}

QScrollArea {
    background: #FFFFFF;
    border: 1px solid #DCDFE6;
    border-radius: 8px;
}

QScrollBar:vertical {
    width: 10px;
    margin: 3px;
    background: transparent;
}

QScrollBar::handle:vertical {
    min-height: 28px;
    background: #C0C4CC;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #A0CFFF;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #DCDFE6;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #409EFF;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 14px;
    margin: -4px 0;
    background: #FFFFFF;
    border: 2px solid #409EFF;
    border-radius: 7px;
}

QProgressBar {
    min-height: 20px;
    background: #FFFFFF;
    border: 1px solid #DCDFE6;
    border-radius: 6px;
    color: #606266;
    text-align: center;
}

QProgressBar::chunk {
    background: #409EFF;
    border-radius: 5px;
}
```

Also style disabled and destructive buttons, combo popup views, horizontal
scrollbars, splitter handles, and `QDialogButtonBox` controls using the same
palette. Do not create a second stylesheet or add a visual string in
`main_window.py`.

- [ ] **Step 4: Pass non-native options to every existing file dialog**

Change the two open calls and save call to include:

```python
options=QFileDialog.Option.DontUseNativeDialog,
```

Change the folder call to include:

```python
options=(
    QFileDialog.Option.ShowDirsOnly
    | QFileDialog.Option.DontUseNativeDialog
),
```

Do not change dialog title, start path, name filters, selected path handling,
or cancellation branches.

- [ ] **Step 5: Run the focused style and file-dialog tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "semantic_style_object_names or file_dialogs_request_non_native_windows"
```

Expected: PASS. The tests see semantic style hooks and all four file chooser
paths request styled Qt dialogs while preserving their no-selection exits.

- [ ] **Step 6: Commit the MainWindow style extraction**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/themes/light_fresh.qss video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: apply light fresh workspace theme"
```

### Task 3: Animate The Existing Collapsible Behavior Group

**Files:**
- Modify: `video_labeler/ui/main_window.py:5-108`
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `tests/test_main_window.py:8-20`
- Modify: `tests/test_main_window.py:130-146`

**Interfaces:**
- Preserves: `CollapsibleGroupBox(QGroupBox)`, `set_content(content)`, checked
  state, `toggled` signal, and existing `behaviors_group` callers.
- Produces: `chevron_rotation: float` readable property and a 300ms internal
  transition for content height and chevron rotation.

- [ ] **Step 1: Update the collapsible-group test to require animation**

Import `QTest`:

```python
from PySide6.QtTest import QTest
```

Replace the immediate-visibility assertions in
`test_collapsible_behavior_group` with:

```python
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
```

- [ ] **Step 2: Run the animation test and verify it fails**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_collapsible_behavior_group -v
```

Expected: FAIL because the current group has no animation duration or chevron
property and hides the content immediately.

- [ ] **Step 3: Add the internal height and chevron animations**

Extend the Qt imports:

```python
from PySide6.QtCore import (
    QEasingCurve,
    QItemSelectionModel,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Property,
    QSignalBlocker,
    Qt,
    QUrl,
)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QPolygonF, QShortcut
```

Implement the class around these concrete behaviors:

```python
class CollapsibleGroupBox(QGroupBox):
    animation_duration_ms = 300

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self._content: QWidget | None = None
        self._chevron_rotation = 90.0
        self._animation = QParallelAnimationGroup(self)
        self._content_animation: QPropertyAnimation | None = None
        self._chevron_animation = QPropertyAnimation(self, b"chevronRotation", self)
        self._chevron_animation.setDuration(self.animation_duration_ms)
        self._chevron_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.addAnimation(self._chevron_animation)
        self._animation.finished.connect(self._finish_content_animation)
        self.toggled.connect(self._animate_content)

    @Property(float)
    def chevronRotation(self) -> float:
        return self._chevron_rotation

    @chevronRotation.setter
    def chevronRotation(self, value: float) -> None:
        self._chevron_rotation = value
        self.update()

    @property
def chevron_rotation(self) -> float:
    return self._chevron_rotation
```

In `set_content()`, retain the current initial visible-state behavior, set the
content's maximum height to its unrestricted Qt maximum, then create the
height animation against that content:

```python
self._content_animation = QPropertyAnimation(content, b"maximumHeight", self)
self._content_animation.setDuration(self.animation_duration_ms)
self._content_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
self._animation.insertAnimation(0, self._content_animation)
```

In `_animate_content(expanded)`, return when either the content or its
animation is unavailable; otherwise stop any running group animation, make
content visible before expansion, animate the content maximum height to zero
when collapsing or to `content.sizeHint().height()` when expanding, and
animate the chevron from its current value to `0.0` or `90.0`. In
`_finish_content_animation()`, hide content only when unchecked; otherwise
release its maximum height to the unrestricted value and call
`content.updateGeometry()`.

Override `paintEvent()` after `super().paintEvent(event)` to draw a small
anti-aliased chevron at the left side of the title margin. Rotate it around its
center by `chevron_rotation` and use the group palette's highlight color. Do
not use a hard-coded dark-theme color.

In `light_fresh.qss`, hide the native check indicator only for the behavior
group and reserve title space for the painted chevron:

```css
QGroupBox#collapsibleBehaviorGroup::indicator {
    width: 0px;
    height: 0px;
}

QGroupBox#collapsibleBehaviorGroup::title {
    left: 26px;
}
```

- [ ] **Step 4: Run the animation test and verify it passes**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_collapsible_behavior_group -v
```

Expected: PASS. The group keeps the same checkable API, content remains visible
during collapse, is hidden after 300ms, and the chevron reaches the expected
closed and open rotations.

- [ ] **Step 5: Run UI regression tests and commit the animation**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
```

Expected: PASS. This includes responsive behavior-tag reflow, clipping
avoidance, all post-save interaction tests, shortcuts, batch table actions,
imports, custom labels, and filename behavior.

Commit:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: animate behavior tag panel"
```

### Task 4: Full Verification And Visual Handoff

**Files:**
- Verify: `app.py`
- Verify: `video_labeler/themes/__init__.py`
- Verify: `video_labeler/themes/light_fresh.qss`
- Verify: `video_labeler/ui/main_window.py`
- Verify: `tests/test_themes.py`
- Verify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: the completed global theme, styled dialogs, existing UI behavior,
  and all test modules.
- Produces: a verified local Phase 2 branch ready for user visual acceptance.

- [ ] **Step 1: Inspect the final diff and verify no forbidden files changed**

Run:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' diff HEAD~3..HEAD --stat
& 'C:\Program Files\Git\cmd\git.exe' diff --check
& 'C:\Program Files\Git\cmd\git.exe' status --short
```

Expected: changes are limited to `app.py`, theme assets, `main_window.py`, and
tests, plus the already committed specification and plan documents. No model,
CSV, FFmpeg, naming, or export-worker source is modified.

- [ ] **Step 2: Run the full suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: all pre-existing 54 tests and all newly added theme tests PASS.

- [ ] **Step 3: Start the application for manual visual review**

Run:

```powershell
D:\Python311\python.exe app.py
```

Expected: a new `视频片段标注工具` window opens with the fresh light theme.
Verify the main UI and open the shortcut help, batch edit, custom option,
confirmation, and file-picker dialogs manually. Do not terminate any
previously running user-owned instance.

- [ ] **Step 4: Report the visual-review handoff without integration actions**

Report the final commit IDs, the full pytest result, the local worktree path,
and the application start command. State explicitly that no merge, push, or
pull request was created and that the next action is user visual acceptance.

## Plan Self-Review

Spec coverage:

- Task 1 implements the external QSS source, Fusion application style, and
  global dialog/tooltip coverage.
- Task 2 removes MainWindow inline QSS, adds semantic selectors, applies the
  defined light visual system, and makes every file chooser non-native.
- Task 3 preserves the original collapsible-group contract while adding the
  exact 300ms height and chevron animation.
- Task 4 verifies UI and service regression boundaries, then stops for user
  visual acceptance with no integration action.

No placeholders:

- New paths, public functions, object names, property names, test bodies,
  commands, expected failures, and commit messages are concrete.

Type consistency:

- Theme application accepts the existing `QApplication`.
- QSS remains text returned by `load_light_fresh_theme()`.
- File dialogs use the existing static return types.
- `CollapsibleGroupBox` continues to accept a `QWidget` in `set_content()`
  and exposes a Qt-animatable `float` chevron property.
