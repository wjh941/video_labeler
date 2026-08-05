# Two-Panel Annotation Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertically stacked annotation workspace with a
video-first, two-panel PySide6 layout and a multi-select behavior-tag combo
without changing annotation, CSV, project, or export business behavior.

**Architecture:** Keep `MainWindow` as the UI owner. Reuse the outer horizontal
`editor_splitter` for video on the left and a vertical `workspace_splitter` on
the right for the annotation form and task table. Replace the visible behavior
checkbox grid with a small `BehaviorTagComboBox` widget in `main_window.py`;
the widget owns check states while `MainWindow` remains responsible for
records, tag persistence, historical labels, and custom tag removal.

**Tech Stack:** Python 3.11, PySide6, Qt QSS, pytest.

## Global Constraints

- Do not change CSV headers, segment fields, `.labelproj` schema, filename
  construction, FFmpeg commands, or export-worker behavior.
- Preserve multi-value behavior tags, historical deleted-tag display, custom
  tag persistence, existing action signals, `S`/`E` player shortcuts, and
  table detach/restore behavior.
- Keep project settings above the two-panel workspace and preserve its
  existing collapsible card behavior.
- Keep the light fresh QSS theme; use only light, Ant-style controls.
- Do not push, merge, rebase, or create a pull request.

---

### Task 1: Add A Multi-Select Behavior Combo

**Files:**
- Modify: `video_labeler/ui/main_window.py:1-290, 795-1055, 1869-1955`
- Modify: `tests/test_main_window.py:65-145, 880-1110, 1750-1840`

**Interfaces:**
- Produces: `BehaviorTagComboBox(QComboBox)`.
- `set_tags(tags: Collection[str], selected: Collection[str]) -> None`
  replaces available choices and checks the supplied values.
- `checked_tags() -> tuple[str, ...]` returns checked values in displayed
  order.
- `selectionChanged` is emitted after a user toggles a popup item.
- `MainWindow.selected_behaviors() -> tuple[str, ...]` returns
  `(*behavior_tag_combo.checked_tags(), *historical_behavior_tags)` without
  duplicates.

- [ ] **Step 1: Write failing widget tests**

```python
def test_behavior_selector_holds_multiple_checked_tags(qt_app):
    window = MainWindow()

    window.behavior_tag_combo.set_tags(
        ("dog_out", "fall", "delivery_dropoff"),
        ("dog_out", "delivery_dropoff"),
    )

    assert window.behavior_tag_combo.checked_tags() == (
        "dog_out",
        "delivery_dropoff",
    )
    assert "2" in window.behavior_tag_combo.currentText()


def test_behavior_selector_popup_contains_all_available_tags(qt_app):
    window = MainWindow()
    window.project.custom_behavior_tags.append("delivery_dropoff")
    window._rebuild_behavior_controls(())

    assert window.behavior_tag_combo.count() == len(
        (*BEHAVIOR_LABELS, "delivery_dropoff")
    )
    assert window.behavior_tag_combo.itemText(
        window.behavior_tag_combo.findData("delivery_dropoff")
    ) == "delivery_dropoff"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "behavior_selector_holds_multiple_checked_tags or behavior_selector_popup_contains_all_available_tags"
```

Expected: FAIL because `behavior_tag_combo` does not exist.

- [ ] **Step 3: Implement the combo**

```python
class BehaviorTagComboBox(QComboBox):
    selectionChanged = Signal()

    def set_tags(
        self, tags: Collection[str], selected: Collection[str]
    ) -> None:
        ...

    def checked_tags(self) -> tuple[str, ...]:
        ...
```

Use a `QStandardItemModel` with `ItemIsUserCheckable` rows. On popup row
press, toggle the row's check state, update a read-only summary such as
`"已选 2 项"`, emit `selectionChanged`, and keep the popup open for
multiple choices. Configure `maxVisibleItems` to show all supplied tags.

Replace the visible grid construction in `_rebuild_behavior_controls()` with
`behavior_tag_combo.set_tags()`. Retain `historical_tag_labels` in a compact
read-only layout below the combo. Remove grid-specific reflow and event-filter
code. Keep `_rebuild_behavior_controls(selected)` as the existing refresh
entry point.

- [ ] **Step 4: Update selection and custom-tag wiring**

```python
def selected_behaviors(self) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            (
                *self.behavior_tag_combo.checked_tags(),
                *self.historical_behavior_tags,
            )
        )
    )
```

Connect `behavior_tag_combo.selectionChanged` to `_update_filename_preview`.
Keep `add_custom_behavior_tag()`, `_register_imported_behavior_tags()`, and
`_remove_custom_behavior_tag()` calling `_rebuild_behavior_controls(selected)`
so project and CSV flows keep their current behavior.

- [ ] **Step 5: Run targeted tests to verify they pass**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "behavior_selector or custom_behavior_tag or historical_custom_tag"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: use multi-select behavior dropdown"
```

### Task 2: Build The Fixed Two-Panel Workspace

**Files:**
- Modify: `video_labeler/ui/main_window.py:301-380, 1070-1110, 1204-1235`
- Modify: `tests/test_main_window.py:2000-2470`

**Interfaces:**
- Consumes: `video_panel`, `annotation_scroll`, `task_panel`,
  `task_table_dialog`, and `_restore_task_panel()`.
- Produces: `editor_splitter` as an always-horizontal 55:45 splitter with
  `video_panel` at index 0 and `workspace_splitter` at index 1.
- Produces: `workspace_splitter` as a vertical right-side splitter with
  `annotation_scroll` at index 0 and `task_panel` at index 1.

- [ ] **Step 1: Write failing layout tests**

```python
def test_workspace_uses_two_parallel_panels_with_right_side_table(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert window.editor_splitter.orientation() == Qt.Orientation.Horizontal
    assert window.editor_splitter.widget(0) is window.video_panel
    assert window.editor_splitter.widget(1) is window.workspace_splitter
    assert window.workspace_splitter.widget(0) is window.annotation_scroll
    assert window.workspace_splitter.widget(1) is window.task_panel


def test_video_panel_receives_about_fifty_five_percent_of_workspace(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    left, right = window.editor_splitter.sizes()
    assert left > right
    assert left / (left + right) == pytest.approx(0.55, abs=0.08)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "two_parallel_panels or fifty_five_percent"
```

Expected: FAIL because the old vertical workspace splitter owns the editor
splitter and task table separately.

- [ ] **Step 3: Restructure `_build_ui()`**

```python
self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
self.editor_splitter.setChildrenCollapsible(False)
self.editor_splitter.addWidget(self.video_panel)

self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
self.workspace_splitter.setChildrenCollapsible(False)
self.workspace_splitter.addWidget(self.annotation_scroll)
self.workspace_splitter.addWidget(self.task_panel)

self.editor_splitter.addWidget(self.workspace_splitter)
self.editor_splitter.setSizes([550, 450])
self.editor_splitter.setStretchFactor(0, 11)
self.editor_splitter.setStretchFactor(1, 9)
```

Keep the project header before `editor_splitter`, and keep the export status
after it. Give the video panel and right-side workspace explicit practical
minimum widths. Remove the automatic editor-splitter orientation change; the
workspace stays horizontal at all supported window sizes.

- [ ] **Step 4: Preserve detached-table restoration**

```python
def _restore_task_panel(self, *_args: object) -> None:
    if self.task_panel.parentWidget() is self.workspace_splitter:
        return
    ...
    self.workspace_splitter.insertWidget(1, self.task_panel)
    self.workspace_splitter.setSizes([470, 360])
```

Do not change task-table selection, table actions, filters, or table signal
connections.

- [ ] **Step 5: Run targeted layout and table tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "two_parallel_panels or fifty_five_percent or task_table or video_preview"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: place annotation table beside video"
```

### Task 3: Add Collapsible Custom Fields And Theme Coverage

**Files:**
- Modify: `video_labeler/ui/main_window.py:795-872, 1370-1390`
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `tests/test_main_window.py`
- Modify: `tests/test_themes.py`

**Interfaces:**
- Produces: `custom_tags_group: CollapsibleGroupBox`.
- Produces: `custom_tag_library_combo: QComboBox` and
  `remove_custom_behavior_tag_button: QPushButton`.
- `remove_custom_behavior_tag_button` removes its selected custom tag by
  calling `_remove_custom_behavior_tag(tag)`.

- [ ] **Step 1: Write failing form-group tests**

```python
def test_annotation_options_use_four_independent_collapsible_groups(qt_app):
    window = MainWindow()

    assert isinstance(window.behaviors_group, CollapsibleGroupBox)
    assert isinstance(window.lighting_group, CollapsibleGroupBox)
    assert isinstance(window.polarity_group, CollapsibleGroupBox)
    assert isinstance(window.custom_tags_group, CollapsibleGroupBox)


def test_custom_tag_add_preserves_fixed_selection_and_group_states(qt_app):
    window = MainWindow()
    window.set_clip_range(3.0, 5.0)
    window.lighting_combo.setCurrentText("night_full_color")
    window.polarity_combo.setCurrentText("neg")
    window.lighting_group.setChecked(False)
    window.polarity_group.setChecked(False)
    window.behaviors_group.setChecked(False)
    window.custom_behavior_tag_edit.setText("delivery_dropoff")

    window.add_custom_behavior_tag()

    assert window.lighting_combo.currentText() == "night_full_color"
    assert window.polarity_combo.currentText() == "neg"
    assert not window.lighting_group.isChecked()
    assert not window.polarity_group.isChecked()
    assert not window.behaviors_group.isChecked()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "four_independent_collapsible_groups or custom_tag_add_preserves_fixed_selection"
```

Expected: FAIL because there is no custom-fields group.

- [ ] **Step 3: Add custom-field management**

```python
self.custom_tags_group = CollapsibleGroupBox("自定义字段")
custom_content = QWidget()
custom_layout = QVBoxLayout(custom_content)
custom_layout.addLayout(add_tag_layout)
custom_layout.addLayout(remove_tag_layout)
self.custom_tags_group.set_content(custom_content)
```

Move `custom_behavior_tag_edit` and `add_custom_behavior_tag_button` from the
former tag-grid layout into `custom_tags_group`. Rebuild
`custom_tag_library_combo` after project custom tag changes. Keep the existing
remove warning and historical-record behavior in `_remove_custom_behavior_tag`.

- [ ] **Step 4: Add QSS selectors**

```css
QComboBox#behaviorTagCombo {
    background: #ffffff;
    border: 1px solid #e5e6eb;
    border-radius: 8px;
}

QComboBox#behaviorTagCombo QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
}
```

Style the custom-field card and selector with the existing light palette.
Remove obsolete selectors for the visible behavior button grid only after the
new combo is rendered and tested.

- [ ] **Step 5: Run targeted UI/theme tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py tests/test_themes.py -v -k "collapsible_groups or custom_tag or light_theme"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_main_window.py tests/test_themes.py
git commit -m "style: refine two-panel annotation controls"
```

### Task 4: Full Regression And Local Delivery

**Files:**
- Modify: no source files expected

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: local commits with evidence that the layout refactor retained all
  supported behavior.

- [ ] **Step 1: Run the complete test suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: all tests pass, including CSV, project I/O, FFmpeg, history, UI, and
theme coverage.

- [ ] **Step 2: Compile and inspect the working tree**

Run:

```powershell
D:\Python311\python.exe -m compileall -q app.py video_labeler
git diff --check
git status --short --branch
```

Expected: compilation exits zero; `git diff --check` has no errors; only
intended local commits and pre-existing unrelated untracked files remain.

- [ ] **Step 3: Launch the application for visual review**

Run:

```powershell
D:\Python311\python.exe app.py
```

Expected: a responsive two-panel window opens without an exception. The top
project settings card is above the workspace, the left video panel is wider,
and all annotation controls and table are in the right panel.

- [ ] **Step 4: Deliver locally**

Report the modified source locations, test results, and any intentionally
preserved untracked files. Do not push, merge, rebase, or create a pull
request.
