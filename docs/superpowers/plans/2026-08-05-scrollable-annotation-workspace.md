# Scrollable Annotation Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the video preview and core segment editor side by side at the
top of the application, while lower-priority task-table and export content is
reachable through vertical page scrolling.

**Architecture:** Reintroduce a single page-level `QScrollArea` as the
central widget. Its content owns the project toolbar, a horizontal top
workspace row, the existing task-table card below that row, and export
status. The editor card remains the right sibling of the video card, so video
preview and segment editing share the same screen area without forcing the
task table into the right pane.

**Tech Stack:** Python 3.11, PySide6, Qt QSS, pytest.

## Global Constraints

- Do not change CSV headers, `ClipRecord` fields, `.labelproj` schema,
  filename construction, FFmpeg command construction, or export-worker
  behavior.
- Keep `self.records` as the active-video segment collection. Preserve
  import/export, undo/redo, batch edit/delete, filters, sorting, shortcuts,
  table selection, and detached task-table behavior.
- Keep `BehaviorTagComboBox`, custom-tag persistence, historical deleted-tag
  capsules, and the partial-refresh rule. Adding a custom tag refreshes only
  start/end time and behavior controls; lighting and polarity selection and
  collapse state remain unchanged.
- Preserve the light Ant-style QSS theme and all current semantic object
  names.
- Keep video controls below the video surface and do not introduce a
  horizontal-clipping path at the 1120px minimum window width.
- Do not push, merge, rebase, reset, or create a pull request.

---

### Task 1: Define The Scrollable Page Layout Contract

**Files:**
- Modify: `tests/test_main_window.py:1967-2310`

**Interfaces:**
- Consumes: `MainWindow`, `main_content_scroll`, `workspace_content`,
  `workspace_row`, `video_panel`, `annotation_workspace`, `annotation_panel`,
  `task_panel`, `task_table_dialog`, and `set_source_path`.
- Produces: test coverage for a vertical page scroll container, same-row
  video/editor topology, below-workspace task card, and task-table reparenting.

- [ ] **Step 1: Replace the obsolete fixed-screen tests with a page-scroll test**

```python
@pytest.mark.parametrize(("width", "height"), ((1120, 720), (1440, 900)))
def test_page_scroll_keeps_video_and_annotation_in_top_workspace(
    qt_app, width, height, tmp_path
):
    window = MainWindow()
    window.resize(width, height)
    window.show()
    window.set_source_path(tmp_path / "source.mp4")
    qt_app.processEvents()

    assert isinstance(window.main_content_scroll, QScrollArea)
    assert window.main_content_scroll.widget() is window.workspace_content
    layout = window.workspace_row.layout()
    assert layout.itemAt(0).widget() is window.video_panel
    assert layout.itemAt(1).widget() is window.annotation_workspace
    assert window.video_panel.isVisible()
    assert window.annotation_panel.isVisible()
```

- [ ] **Step 2: Add a regression proving the task table is below the top workspace**

```python
def test_task_table_is_below_workspace_and_rejoins_page_after_detach(qt_app):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content
    assert window.workspace_content.layout().indexOf(window.task_panel) > (
        window.workspace_content.layout().indexOf(window.workspace_row)
    )

    window._show_task_table_dialog()
    qt_app.processEvents()
    window.task_table_dialog.close()
    qt_app.processEvents()

    assert window.task_panel.parentWidget() is window.workspace_content
```

- [ ] **Step 3: Update right-pane table assumptions**

Replace the old assertion that the task table receives remaining
right-pane height with a below-workspace table assertion:

```python
def test_task_table_keeps_a_usable_page_section(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.isChecked()
    assert window.task_table.height() >= 200
    assert window.task_panel.parentWidget() is window.workspace_content
```

Update all detach/restore tests to expect `workspace_content` rather than
`annotation_workspace` as the embedded task-card parent. Retain their
selection synchronization assertions unchanged.

- [ ] **Step 4: Run the layout tests and confirm they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "page_scroll_keeps_video or task_table_is_below or usable_page_section"
```

Expected: FAIL because the current application has no `main_content_scroll`
and parents `task_panel` inside `annotation_workspace`.

- [ ] **Step 5: Commit the red test contract**

```powershell
git add tests/test_main_window.py
git commit -m "test: define scrollable annotation workspace"
```

### Task 2: Build The Scrollable Annotation Page

**Files:**
- Modify: `video_labeler/ui/main_window.py:33-60, 371-445, 1208-1230`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `_build_project_header()`, `_build_video_panel()`,
  `_build_clip_editor()`, `_build_task_table()`, `_build_export_status()`,
  `_show_task_table_dialog()`, and `_restore_task_panel()`.
- Produces: `main_content_scroll: QScrollArea` and
  `page_layout: QVBoxLayout`.

- [ ] **Step 1: Add the page scroll-area import and root container**

Add `QScrollArea` to the `PySide6.QtWidgets` imports. In `_build_ui()`, keep
`workspace_content` as the scrollable page and retain its existing object
name. Add:

```python
self.main_content_scroll = QScrollArea()
self.main_content_scroll.setObjectName("mainContentScroll")
self.main_content_scroll.setWidgetResizable(True)
self.main_content_scroll.setFrameShape(QFrame.Shape.NoFrame)
self.main_content_scroll.setWidget(self.workspace_content)
```

Store the page layout for later task-panel restoration:

```python
self.page_layout = QVBoxLayout(self.workspace_content)
self.page_layout.setContentsMargins(14, 12, 14, 12)
self.page_layout.setSpacing(10)
```

Set `main_content_scroll` as the central widget after building its page.

- [ ] **Step 2: Keep only the editor in the right top pane**

Construct `annotation_workspace` with its existing object name and one
`QVBoxLayout`. Add only `annotation_panel` to that layout:

```python
self.annotation_workspace_layout.addWidget(self.annotation_panel)
workspace_layout.addWidget(self.video_panel, 13)
workspace_layout.addWidget(self.annotation_workspace, 12)
```

Add the task panel to the page layout after `workspace_row`:

```python
self.page_layout.addWidget(self.project_header)
self.page_layout.addWidget(self.workspace_row)
self.page_layout.addWidget(self.task_panel)
self.page_layout.addLayout(self._build_export_status())
```

Keep the existing card shadows and all widget object names. Do not move any
editor controls or modify their signals.

- [ ] **Step 3: Reparent the detached table back into the page**

In `_show_task_table_dialog()`, remove the task panel from `page_layout`
before adding it to the dialog. In `_restore_task_panel()`, restore it before
the final export-status layout:

```python
def _restore_task_panel(self, *_args: object) -> None:
    if self.task_panel.parentWidget() is self.workspace_content:
        return

    dialog_layout = self.task_table_dialog.layout()
    if dialog_layout is not None:
        dialog_layout.removeWidget(self.task_panel)
    self.task_panel.setParent(None)
    self.page_layout.insertWidget(
        self.page_layout.count() - 1,
        self.task_panel,
    )
    self.task_panel.show()
```

Do not touch table signals, `self.records`, or row selection code.

- [ ] **Step 4: Run the focused red-green tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "page_scroll_keeps_video or task_table_is_below or usable_page_section or detach"
```

Expected: PASS.

- [ ] **Step 5: Run the full main-window regression suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the implementation**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: make annotation workspace vertically scrollable"
```

### Task 3: Verify Presentation And Business Regression Boundaries

**Files:**
- Test: `tests/test_main_window.py`
- Test: `tests/test_csv_io.py`
- Test: `tests/test_project_io.py`
- Test: `tests/test_export_worker.py`
- Test: `tests/test_ffmpeg_service.py`
- Test: `tests/test_themes.py`

**Interfaces:**
- Consumes: current production code and the complete test suite.
- Produces: proof that the page layout change preserves video/editor topology,
  tag partial refresh, CSV/project behavior, export behavior, and theme
  loading.

- [ ] **Step 1: Run the full suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: PASS with no failures.

- [ ] **Step 2: Compile application modules**

Run:

```powershell
D:\Python311\python.exe -m compileall -q app.py video_labeler
```

Expected: exit code 0.

- [ ] **Step 3: Check the pending tree**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; leave the pre-existing untracked
`.superpowers/brainstorm/` directory untouched.

