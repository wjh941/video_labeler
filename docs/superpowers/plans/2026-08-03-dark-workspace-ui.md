# Dark Workspace UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the washed-out, vertically crowded annotation window with a high-contrast dark workspace that keeps video review, clip editing, and task inspection usable in a 1366x768 desktop window.

**Architecture:** Keep all application behavior in `MainWindow` and preserve its current public controls, signals, and export wiring. Change only widget composition, scroll containers, splitter ownership, and styles so that the existing data and export layers remain untouched.

**Tech Stack:** Python 3.11, PySide6 6.11, pytest 8.4.

## Global Constraints

- Preserve existing video selection, task editing, CSV, filename, and FFmpeg behavior.
- Use a dark neutral base with `#111827` application background and visible
  control borders.
- Keep primary file actions, date, camera, view, and Batch Export visible.
- Put video and annotation controls in the upper workspace pane.
- Use a vertical `QSplitter` for upper workspace and task list resizing.
- Wrap the annotation editor in a `QScrollArea`.
- Keep behavior selection compact in a two-column grid.
- Preserve table scrolling and use a 26-pixel task row height.
- Retain readable text for queued, success, skip, fail, and canceled statuses.

---

## File Structure

```text
video_labeler/
  video_labeler/
    ui/
      main_window.py
  tests/
    test_main_window.py
```

- `main_window.py` remains the single UI composition module.
- `test_main_window.py` verifies public UI behavior and structural layout
  contracts without requiring a real display.

### Task 1: Add Structural Layout Regression Tests

**Files:**
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes `MainWindow`.
- Requires public `workspace_splitter`, `editor_splitter`, and
  `annotation_scroll` widget attributes.
- Produces a test suite that rejects a vertically stacked, non-scrollable
  annotation interface.

- [ ] **Step 1: Write failing layout tests**

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter


def test_main_window_uses_resizable_workspace_splitters(qt_app):
    window = MainWindow()

    assert isinstance(window.workspace_splitter, QSplitter)
    assert window.workspace_splitter.orientation() == Qt.Orientation.Vertical
    assert isinstance(window.editor_splitter, QSplitter)
    assert window.editor_splitter.orientation() == Qt.Orientation.Horizontal


def test_annotation_controls_are_wrapped_in_a_scroll_area(qt_app):
    window = MainWindow()

    assert isinstance(window.annotation_scroll, QScrollArea)
    assert window.annotation_scroll.widget() is window.annotation_panel
    assert window.annotation_scroll.widgetResizable()
```

These tests catch regressions that remove resizable workspace panes or make
the annotation controls inaccessible on shorter screens.

- [ ] **Step 2: Run the layout tests to verify failure**

Run: `python -m pytest tests/test_main_window.py::test_main_window_uses_resizable_workspace_splitters tests/test_main_window.py::test_annotation_controls_are_wrapped_in_a_scroll_area -v`

Expected: FAIL because the current window does not expose the vertical
workspace splitter or annotation scroll area.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_main_window.py
git commit -m "test: define compact workspace layout"
```

### Task 2: Recompose the Workspace and Annotation Panel

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Produces `MainWindow.workspace_splitter: QSplitter`.
- Produces `MainWindow.editor_splitter: QSplitter`.
- Produces `MainWindow.annotation_scroll: QScrollArea`.
- Produces `MainWindow.annotation_panel: QWidget`.
- Preserves `date_edit`, `camera_edit`, `view_combo`, `behavior_checks`,
  `start_spin`, `end_spin`, `sequence_spin`, `task_table`, and all existing
  actions and signals.

- [ ] **Step 1: Replace the root stack with splitters**

Create a compact project toolbar, then add a vertical `workspace_splitter`.
Put an upper horizontal `editor_splitter` into its first pane and the task
table group into its second pane. Set initial sizes so the upper pane receives
about 60 percent of available height and the task pane receives about 40
percent.

```python
self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
self.editor_splitter.addWidget(self._build_video_panel())
self.editor_splitter.addWidget(self.annotation_scroll)
self.workspace_splitter.addWidget(self.editor_splitter)
self.workspace_splitter.addWidget(self._build_task_table())
root_layout.addWidget(self.workspace_splitter, stretch=1)
```

- [ ] **Step 2: Put annotation controls in a scrollable panel**

Build the existing annotation form in `self.annotation_panel`. Place it in
`self.annotation_scroll`, enable widget resizing, hide the horizontal scroll
bar, and use an always-available vertical scroll bar when content exceeds the
panel height.

```python
self.annotation_panel = QWidget()
self.annotation_scroll = QScrollArea()
self.annotation_scroll.setWidget(self.annotation_panel)
self.annotation_scroll.setWidgetResizable(True)
self.annotation_scroll.setHorizontalScrollBarPolicy(
    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
)
self.annotation_scroll.setVerticalScrollBarPolicy(
    Qt.ScrollBarPolicy.ScrollBarAsNeeded
)
```

- [ ] **Step 3: Compact behavior selection**

Replace the one-column behavior layout with a two-column `QGridLayout`.
Keep the same `behavior_checks` mapping and insert checkboxes row-first:

```python
for index, behavior in enumerate(BEHAVIOR_LABELS):
    row, column = divmod(index, 2)
    behavior_grid.addWidget(self.behavior_checks[behavior], row, column)
```

Keep the clip time inputs and Add Clip action above this scrollable behavior
section. Keep the filename preview directly below the label selectors.

- [ ] **Step 4: Run the layout and existing UI tests**

Run: `python -m pytest tests/test_main_window.py -v`

Expected: PASS, including sequential filename creation and draggable timeline
coverage.

- [ ] **Step 5: Commit the workspace composition**

```bash
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: add resizable annotation workspace"
```

### Task 3: Apply the Dark High-Contrast Visual System

**Files:**
- Modify: `video_labeler/ui/main_window.py`

**Interfaces:**
- Consumes the recomposed workspace widgets.
- Produces readable dark controls, dark dialogs, visible table selection, and
  status colors with text preserved.

- [ ] **Step 1: Apply base and control styles**

Replace the pale stylesheet with dark surfaces. Use the following concrete
values:

```css
QMainWindow { background: #111827; color: #f1f5f9; }
QWidget { color: #f1f5f9; }
QGroupBox { background: #18212d; border: 1px solid #334155; border-radius: 5px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #101923;
    color: #f1f5f9;
    border: 1px solid #475569;
    border-radius: 4px;
}
QTableWidget { background: #101923; color: #f1f5f9; gridline-color: #334155; }
QTableWidget::item:selected { background: #1d4f7a; color: #ffffff; }
```

Add `:hover` and `:focus` states with visible blue borders. Set dark
backgrounds for drop-down lists, scrollbars, progress bars, and message
boxes.

- [ ] **Step 2: Establish action hierarchy**

Assign object names to main actions and style them:

```python
self.add_button.setObjectName("addClipButton")
self.export_button.setObjectName("primaryButton")
self.remove_button.setObjectName("dangerButton")
```

Style `primaryButton` with blue `#2563eb`, `addClipButton` with teal
`#0f9f8c`, and `dangerButton` with red `#dc4c64`. Secondary actions use the
raised slate surface and a visible hover border.

- [ ] **Step 3: Update density and status contrast**

Set the task row height to 26 pixels. Set a compact 12-point application font
or equivalent widget spacing. Update `_apply_status_color` with colors that
remain readable against `#101923`: teal for `ok`, amber for `skip`, red for
`fail`, blue-gray for `canceled`, and light slate for `queued`.

- [ ] **Step 4: Manually smoke test at desktop height**

Run: `python app.py`

Check the following with a 1366x768 window:

- Open Video, Import CSV, Save CSV, Output Folder, date, camera, view, and
  Batch Export are visible.
- The annotation panel scrolls independently of the task table.
- Both splitters resize without hiding the video player.
- Checkbox labels, focus rings, table selection, and all task statuses have
  readable contrast.

- [ ] **Step 5: Run all automated tests**

Run: `python -m pytest tests -v`

Expected: PASS.

- [ ] **Step 6: Commit the visual system**

```bash
git add video_labeler/ui/main_window.py
git commit -m "feat: apply dark high-contrast workspace"
```

## Plan Self-Review

Spec coverage:

- Dark neutral palette, visible borders, status readability, and action
  hierarchy map to Task 3.
- Compact toolbar, upper editor area, lower task pane, and resizable vertical
  workspace map to Task 2.
- Scrollable annotation controls and two-column behavior layout map to Task 2.
- Existing behavior preservation maps to Task 2's existing UI test run and
  Task 3's full suite run.
- Short desktop manual inspection maps to Task 3.

The plan contains no deferred implementation markers. The public widget
attributes introduced by Task 2 match the assertions in Task 1.
