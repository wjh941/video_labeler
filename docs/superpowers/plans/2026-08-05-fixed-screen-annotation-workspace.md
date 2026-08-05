# Fixed-Screen Annotation Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present the video player and all annotation tools in one fixed,
side-by-side desktop workspace without a global vertical scroll bar.

**Architecture:** Replace the outer scroll-area content container with a
direct `QVBoxLayout`: compact project settings, a horizontal workspace row,
and export status. The workspace row uses a `QHBoxLayout` with the video card
on the left and a direct vertical annotation layout on the right; the task
table receives the remaining height in its own collapsible group.

**Tech Stack:** Python 3.11, PySide6, Qt QSS, pytest.

## Global Constraints

- Do not change CSV headers, `ClipRecord` fields, `.labelproj` schema,
  filename construction, FFmpeg command construction, or export-worker
  behavior.
- Keep `self.records` as the active-video segment collection and preserve
  existing import/export, undo/redo, batch, filter, sort, shortcuts, table
  selection, and detached-table behavior.
- Keep the current multi-select `BehaviorTagComboBox`, custom-tag
  persistence, deleted historical tag capsules, and partial-refresh rule.
- Adding a custom behavior tag may rebuild only the behavior selector and
  refresh only start/end values. Lighting and polarity controls must retain
  their selected values.
- Keep the global light Ant-style QSS theme. No dark or system-native-only
  widget styling is introduced.
- Do not push, merge, rebase, or create a pull request as part of this
  refactor.

---

### Task 1: Lock The Fixed-Screen Layout Contract With Tests

**Files:**
- Modify: `tests/test_main_window.py:1935-2485`

**Interfaces:**
- Consumes: `MainWindow`, `video_panel`, `annotation_panel`, `task_panel`,
  `workspace_content`, `set_source_path`.
- Produces: regression coverage for a direct root layout and a horizontal
  video-to-annotation workspace at 1120x720 and 1440x900.

- [ ] **Step 1: Write failing fixed-screen layout tests**

```python
@pytest.mark.parametrize(("width", "height"), ((1120, 720), (1440, 900)))
def test_workspace_has_no_global_vertical_scroll_area(qt_app, width, height):
    window = MainWindow()
    window.resize(width, height)
    window.show()
    qt_app.processEvents()

    assert not hasattr(window, "main_content_scroll")
    assert not window.findChildren(QScrollArea)


def test_importing_video_keeps_fixed_screen_workspace_unclipped(
    qt_app, tmp_path
):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    window.set_source_path(tmp_path / "source.mp4")
    qt_app.processEvents()

    window_rect = window.centralWidget().contentsRect()
    assert window_rect.contains(window.workspace_row.geometry())
    assert window.video_panel.isVisible()
    assert window.annotation_workspace.isVisible()
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "no_global_vertical_scroll_area or fixed_screen_workspace_unclipped"
```

Expected: FAIL because the current window owns `main_content_scroll` and has
no `workspace_row` or `annotation_workspace`.

- [ ] **Step 3: Replace stale splitter/scroll layout expectations**

Update existing tests that currently require `main_content_scroll`,
`annotation_scroll`, `editor_splitter`, and `workspace_splitter`:

```python
def test_workspace_uses_two_parallel_panels(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    layout = window.workspace_row.layout()
    assert layout.count() == 2
    assert layout.itemAt(0).widget() is window.video_panel
    assert layout.itemAt(1).widget() is window.annotation_workspace


def test_video_panel_receives_about_fifty_two_percent_of_workspace(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    video_width = window.video_panel.width()
    annotation_width = window.annotation_workspace.width()
    assert video_width / (video_width + annotation_width) == pytest.approx(
        0.52, abs=0.04
    )
```

Remove assertions that require a global scroll bar or a vertical splitter.
Keep tests for detached task-table synchronization, video controls, behavior
selection, custom tags, and all business interactions.

- [ ] **Step 4: Run only the revised layout tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "workspace_has_no_global or fixed_screen or two_parallel_panels or fifty_two_percent"
```

Expected: FAIL until Task 2 creates the direct workspace row.

- [ ] **Step 5: Commit the red test contract**

```powershell
git add tests/test_main_window.py
git commit -m "test: define fixed-screen workspace layout"
```

### Task 2: Build The Direct Two-Pane Workspace

**Files:**
- Modify: `video_labeler/ui/main_window.py:374-466, 1066-1107, 1228-1241,
  1475-1480`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `_build_project_header()`, `_build_video_panel()`,
  `_build_clip_editor()`, `_build_task_table()`, `_build_export_status()`.
- Produces: `workspace_content`, `workspace_row`, and
  `annotation_workspace` widgets.
- Replaces: `main_content_scroll`, `main_content_viewport`,
  `annotation_scroll`, `editor_splitter`, `workspace_splitter`, and
  `_update_editor_splitter_orientation()`.

- [ ] **Step 1: Build the root without a global scroll area**

```python
def _build_ui(self) -> None:
    self.workspace_content = QWidget()
    self.workspace_content.setObjectName("workspaceContent")
    root_layout = QVBoxLayout(self.workspace_content)
    root_layout.setContentsMargins(14, 12, 14, 12)
    root_layout.setSpacing(10)

    self.project_header = self._build_project_header()
    root_layout.addWidget(self.project_header)

    self.workspace_row = QWidget()
    self.workspace_row.setObjectName("workspaceRow")
    workspace_layout = QHBoxLayout(self.workspace_row)
    workspace_layout.setContentsMargins(0, 0, 0, 0)
    workspace_layout.setSpacing(12)

    self.video_panel = self._build_video_panel()
    self.annotation_workspace = QWidget()
    self.annotation_workspace.setObjectName("annotationWorkspace")
    workspace_layout.addWidget(self.video_panel, 13)
    workspace_layout.addWidget(self.annotation_workspace, 12)

    root_layout.addWidget(self.workspace_row, 1)
    root_layout.addLayout(self._build_export_status())
    self.setCentralWidget(self.workspace_content)
```

- [ ] **Step 2: Move the editor and task card into the right pane**

```python
self.annotation_panel = self._build_clip_editor()
self.annotation_panel.setObjectName("annotationCard")
self.task_panel = self._build_task_table()
self.task_panel.setObjectName("taskCard")

self.annotation_workspace_layout = QVBoxLayout(self.annotation_workspace)
self.annotation_workspace_layout.setContentsMargins(0, 0, 0, 0)
self.annotation_workspace_layout.setSpacing(10)
self.annotation_workspace_layout.addWidget(self.annotation_panel)
self.annotation_workspace_layout.addWidget(self.task_panel, 1)
```

Set `video_panel` and `annotation_workspace` expanding size policies.
Lower the video preview minimum height to 280 pixels and keep the controls
below it. Set a practical minimum width for the annotation workspace, but do
not use a height that forces global scrolling.

- [ ] **Step 3: Remove obsolete resize and event-filter paths**

Delete `main_content_viewport` installation and the branch in `eventFilter()`
that resizes the old viewport. Replace
`_update_editor_splitter_orientation()` with no call sites. Update
`set_source_path()` to avoid a removed splitter call. Keep the video-viewport
resize path unchanged.

- [ ] **Step 4: Preserve task-table detachment and restoration**

```python
def _restore_task_panel(self, *_args: object) -> None:
    if self.task_panel.parentWidget() is self.annotation_workspace:
        return
    dialog_layout = self.task_table_dialog.layout()
    if dialog_layout is not None:
        dialog_layout.removeWidget(self.task_panel)
    self.task_panel.setParent(None)
    self.annotation_workspace_layout.addWidget(self.task_panel, 1)
    self.task_panel.show()
```

Leave `_show_task_table_dialog()`, task-table signals, record selection, and
filters unchanged.

- [ ] **Step 5: Run layout and table synchronization tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "workspace or task_table or video_preview or fixed_screen"
```

Expected: PASS.

- [ ] **Step 6: Commit the direct workspace**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: keep video and annotation workspace on screen"
```

### Task 3: Make Right-Side Blocks Compact And Collapsible

**Files:**
- Modify: `video_labeler/ui/main_window.py:812-1065, 1109-1227`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `CollapsibleGroupBox`, `behavior_tag_combo`, `lighting_combo`,
  `polarity_combo`, custom-tag controls, task table, task filters, and
  table-action bar.
- Produces: `task_panel: CollapsibleGroupBox` with
  `task_panel_content: QWidget`.

- [ ] **Step 1: Write failing group and table-height tests**

```python
def test_right_side_modules_are_collapsible_groups(qt_app):
    window = MainWindow()

    assert isinstance(window.behaviors_group, CollapsibleGroupBox)
    assert isinstance(window.custom_tags_group, CollapsibleGroupBox)
    assert isinstance(window.lighting_group, CollapsibleGroupBox)
    assert isinstance(window.polarity_group, CollapsibleGroupBox)
    assert isinstance(window.task_panel, CollapsibleGroupBox)


def test_task_table_receives_remaining_right_pane_height(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert window.task_panel.isChecked()
    assert window.task_table.height() > 120
    assert window.task_table.height() > window.behaviors_group.height()
```

- [ ] **Step 2: Run the new tests and confirm task-panel failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "right_side_modules_are_collapsible_groups or task_table_receives_remaining"
```

Expected: FAIL because the task panel is still a regular `QGroupBox`.

- [ ] **Step 3: Convert the task card into a collapsible group**

```python
def _build_task_table(self) -> CollapsibleGroupBox:
    group = CollapsibleGroupBox("片段任务")
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)
    # Move the existing filter bars, QTableWidget, and action bar here.
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(6, 6, 6, 6)
    group_layout.addWidget(content)
    group.set_content(content)
    return group
```

Keep the table’s existing filters, columns, selection behavior, batch-edit,
batch-delete, and detach controls. Set the table’s vertical size policy to
`Expanding` and the task panel’s size policy to `Expanding, Expanding`.

- [ ] **Step 4: Set compact group defaults**

```python
self.behaviors_group.setChecked(True)
self.custom_tags_group.setChecked(False)
self.lighting_group.setChecked(False)
self.polarity_group.setChecked(False)
self.task_panel.setChecked(True)
```

Apply these states before each group receives `set_content()` so initial
construction has no unnecessary animation. Keep group widgets intact during
record selection and custom-tag refreshes.

- [ ] **Step 5: Preserve partial refresh behavior**

Extend the existing custom-tag refresh test:

```python
assert window.lighting_combo.currentText() == "night_full_color"
assert window.polarity_combo.currentText() == "neg"
assert window.lighting_group.isChecked() is False
assert window.polarity_group.isChecked() is False
```

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "custom_tag or partial_refresh or collapsible_groups or task_table_receives"
```

Expected: PASS.

- [ ] **Step 6: Commit compact right-side modules**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: compact annotation modules and task table"
```

### Task 4: Polish The Fixed-Screen Theme

**Files:**
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `tests/test_themes.py`

**Interfaces:**
- Consumes: semantic object names `workspaceContent`, `workspaceRow`,
  `annotationWorkspace`, `videoCard`, `annotationCard`, and `taskCard`.
- Produces: compact spacing and visual distinction for direct panels without
  adding scroll-area styling requirements.

- [ ] **Step 1: Write a failing theme coverage test**

```python
def test_light_theme_styles_fixed_screen_workspace_panels():
    theme = load_light_fresh_theme()

    assert "QWidget#workspaceRow" in theme
    assert "QWidget#annotationWorkspace" in theme
    assert "QGroupBox#taskCard" in theme
```

- [ ] **Step 2: Run the new theme test and confirm failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py -v -k fixed_screen_workspace_panels
```

Expected: FAIL because the direct workspace selectors do not exist.

- [ ] **Step 3: Add compact panel selectors**

```css
QWidget#workspaceContent,
QWidget#workspaceRow,
QWidget#annotationWorkspace {
    background: #f7f8fa;
}

QWidget#workspaceRow {
    border: 0;
}

QGroupBox#videoCard,
QGroupBox#annotationCard,
QGroupBox#taskCard {
    border: 1px solid #e5e6eb;
    border-radius: 8px;
}
```

Reduce only the header and card padding needed to fit the fixed workspace:
toolbar content uses 10px margins and 8px spacing; direct panel content uses
12px margins and 10px spacing. Do not add a root scrollbar selector or reduce
button and input text sizes.

- [ ] **Step 4: Run UI theme tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py tests/test_main_window.py -v -k "theme or visual_sections or refined_video_controls"
```

Expected: PASS.

- [ ] **Step 5: Commit theme polish**

```powershell
git add video_labeler/themes/light_fresh.qss tests/test_themes.py
git commit -m "style: compact fixed-screen annotation workspace"
```

### Task 5: Full Regression And Local Review

**Files:**
- Modify: no source files expected

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: verified local workspace ready for visual review.

- [ ] **Step 1: Run the complete test suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: all UI, CSV, project, FFmpeg, export-worker, history, and theme
tests pass.

- [ ] **Step 2: Compile and inspect the working tree**

Run:

```powershell
D:\Python311\python.exe -m compileall -q app.py video_labeler
git diff --check
git status --short
```

Expected: compilation exits zero, no diff whitespace errors, and only the
pre-existing `.superpowers/brainstorm/` path remains untracked.

- [ ] **Step 3: Launch the desktop application**

Run:

```powershell
D:\Python311\python.exe app.py
```

Expected: the project settings are above a 52:48 two-pane workspace; no
global vertical scrollbar appears after importing a video; video controls are
below the preview; the task table remains in the right panel and can be
collapsed or detached.

- [ ] **Step 4: Deliver locally**

Report the changed files, verification results, running process identifier,
and preserve all code locally without push, merge, rebase, or pull request.
