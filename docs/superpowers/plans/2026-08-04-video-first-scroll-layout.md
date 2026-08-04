# Video-First Scroll Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the video preview and its controls visually separate and sufficiently tall while moving the existing segment task table below the editor in a vertically scrollable main workspace.

**Architecture:** Keep `workspace_splitter`, `editor_splitter`, `task_table`, player bindings, and table-selection signals intact. Wrap the existing page content in an outer `QScrollArea`; retain the vertical splitter order of editor first and task table second, but give the editor/video area fixed minimum geometry so a short window scrolls instead of squeezing the preview into the controls or task table.

**Tech Stack:** Python 3.11, PySide6, pytest.

## Global Constraints

- Do not change verified annotation refresh behavior, segment data, `self.records`, CSV import/export, filename generation, or FFmpeg export logic.
- Keep `task_table` as the existing table instance and preserve all selection, editing, filtering, sorting, batch-operation, and export integrations.
- Keep the existing `QGraphicsView` and `QGraphicsVideoItem` player output, with controls in `video_controls_panel` below the preview surface.
- Do not add a detached task-table dialog unless the scrollable layout proves unable to preserve the video minimum area.
- Do not push, merge, rebase, create a pull request, or alter remote configuration.
- Retain the existing light theme and only use current semantic QSS object names.

---

### Task 1: Lock Video-First Main Workspace Behavior

**Files:**
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Produces: assertions for `MainWindow.main_content_scroll`, `MainWindow.workspace_content`, and `MainWindow.task_panel`.
- Consumes: existing `workspace_splitter`, `editor_splitter`, `video_widget`, `video_controls_panel`, and `task_table`.

- [ ] **Step 1: Write a failing layout regression test**

Add the following test next to the current workspace/video layout tests:

```python
def test_video_first_workspace_scrolls_instead_of_compressing_preview(qt_app):
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    qt_app.processEvents()

    assert isinstance(window.main_content_scroll, QScrollArea)
    assert window.main_content_scroll.widget() is window.workspace_content
    assert window.main_content_scroll.verticalScrollBar().maximum() > 0
    assert window.workspace_splitter.indexOf(window.editor_splitter) == 0
    assert window.workspace_splitter.indexOf(window.task_panel) == 1
    assert window.editor_splitter.minimumHeight() >= 560
    assert window.video_widget.minimumHeight() >= 420

    content = window.workspace_content
    controls_bottom = window.video_controls_panel.mapTo(
        content,
        QPoint(0, window.video_controls_panel.height()),
    ).y()
    table_top = window.task_panel.mapTo(content, QPoint(0, 0)).y()

    assert controls_bottom < table_top
    assert window.task_panel.findChild(QTableWidget) is window.task_table
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_video_first_workspace_scrolls_instead_of_compressing_preview -v
```

Expected: fail because `MainWindow` does not yet expose `main_content_scroll`, `workspace_content`, or `task_panel`.

### Task 2: Add Scrollable Video-First Workspace Geometry

**Files:**
- Modify: `video_labeler/ui/main_window.py:254-291`
- Modify: `video_labeler/ui/main_window.py:383-461`

**Interfaces:**
- Produces: `self.main_content_scroll: QScrollArea`, `self.workspace_content: QWidget`, and `self.task_panel: QGroupBox`.
- Preserves: `self.workspace_splitter: QSplitter`, `self.editor_splitter: QSplitter`, and `self.task_table: QTableWidget`.

- [ ] **Step 1: Wrap the root content in a vertical-only page scroll area**

In `_build_ui()`:

```python
self.main_content_scroll = QScrollArea()
self.main_content_scroll.setObjectName("mainContentScroll")
self.main_content_scroll.setWidgetResizable(True)
self.main_content_scroll.setHorizontalScrollBarPolicy(
    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
)
self.main_content_scroll.setVerticalScrollBarPolicy(
    Qt.ScrollBarPolicy.ScrollBarAsNeeded
)
self.workspace_content = QWidget()
self.workspace_content.setObjectName("workspaceContent")
content_layout = QVBoxLayout(self.workspace_content)
content_layout.setContentsMargins(16, 14, 16, 14)
content_layout.setSpacing(12)
```

Move the existing project header, `workspace_splitter`, and export status layout into `content_layout`; set `workspace_content` as the scroll widget and add only `main_content_scroll` to the root layout.

- [ ] **Step 2: Reserve minimum heights instead of allowing a short window to compress the editor**

After constructing the editor and task panels:

```python
self.editor_splitter.setMinimumHeight(560)
self.task_panel = self._build_task_table()
self.task_panel.setMinimumHeight(320)
self.workspace_splitter.addWidget(self.editor_splitter)
self.workspace_splitter.addWidget(self.task_panel)
self.workspace_splitter.setMinimumHeight(892)
self.workspace_splitter.setSizes([560, 320])
```

Keep the existing vertical splitter and stretch factors so users can resize the sections once the window has enough vertical space.

- [ ] **Step 3: Strengthen preview height and maintain its separate control panel**

In `_build_video_panel()`:

```python
self.video_widget.setMinimumHeight(420)
layout.addWidget(self.video_widget, stretch=1)
layout.addSpacing(16)
layout.addWidget(self.video_controls_panel)
```

Do not alter the player, slider, or control-button connections.

- [ ] **Step 4: Run the focused layout tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_main_window_uses_resizable_workspace_splitters tests/test_main_window.py::test_video_preview_keeps_clearance_from_timeline_and_controls tests/test_main_window.py::test_video_progress_and_controls_use_a_dedicated_panel_below_preview tests/test_main_window.py::test_video_first_workspace_scrolls_instead_of_compressing_preview -v
```

Expected: all selected layout tests pass.

### Task 3: Verify Table Synchronization and Entire Regression Suite

**Files:**
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: existing table selection-to-editor data synchronization behavior.

- [ ] **Step 1: Add a direct table-selection synchronization assertion in the scroll-layout test**

Use an existing `ClipRecord` fixture pattern to create one record, refresh the table, select row zero, process Qt events, and assert `window._editing_index == 0`. This proves the below-video table retains its original signal/data connection after reparenting into the scrollable workspace.

- [ ] **Step 2: Run the focused layout and table synchronization tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "video_first_workspace or video_preview or resizable_workspace or select_existing_row" -v
```

Expected: all selected tests pass.

- [ ] **Step 3: Run the complete suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: zero failures.

- [ ] **Step 4: Start the local application for visual acceptance**

Run:

```powershell
Start-Process -FilePath 'D:\Python311\python.exe' -ArgumentList 'app.py' -WorkingDirectory 'C:\Users\16102\Downloads\video_labeler\.worktrees\chinese-ui-localization' -PassThru
```

Confirm the process remains running and report its PID. Do not perform any Git push, merge, rebase, or pull-request operation.
