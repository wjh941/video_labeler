# Ant Desktop UI And Custom Behavior Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an Ant Design Desktop light UI and persistent custom
behavior tags without changing CSV format, segment schema, validated clip
refresh rules, or FFmpeg behavior.

**Architecture:** Keep `LabelProject` as the sole project-level tag-library
owner and keep `ClipRecord.behaviors` unchanged. Let `naming.py` validate
behavior label syntax without needing project state; `MainWindow` registers
CSV-discovered tags, renders available and historical tags, and owns all
layout behavior. Keep presentation values only in `light_fresh.qss`.

**Tech Stack:** Python 3.11, PySide6, pytest, QSS, JSON project persistence.

## Global Constraints

- Do not change CSV header `source,start,end,output`, CSV row format, or
  existing CSV import/export interfaces.
- Do not add, remove, or rename fields inside serialized segment records.
- Preserve filename shape, existing project fields, FFmpeg commands, video
  playback, undo/redo, dirty state, shortcuts, table synchronization, and
  verified next-clip refresh rules.
- A removed custom tag is deleted only from project-level
  `custom_behavior_tags`; never mutate existing `ClipRecord.behaviors`.
- Legacy `.labelproj` files without `custom_behavior_tags` must load with an
  empty custom tag list.
- Use the existing non-native `QFileDialog` configuration and do not add
  direct `QFileDialog QListView` or `QTreeView` QSS selectors.
- Keep all changes local. Do not push, merge, rebase, or create a pull
  request.
- Run `D:\Python311\python.exe -m pytest tests -v` before completion.

---

## File Structure

- `video_labeler/project_io.py`: persist and validate a project-level custom
  behavior tag library while accepting legacy project documents.
- `video_labeler/naming.py`: accept valid custom behavior tokens in existing
  filename building and parsing APIs.
- `video_labeler/ui/main_window.py`: register CSV-discovered tags, render
  custom and historical tag controls, preserve historical selections on
  update, and reorganize existing layouts without changing business flow.
- `video_labeler/themes/light_fresh.qss`: own all Ant Desktop visual tokens,
  toolbar groups, tag states, cards, controls, and scrollbar selectors.
- `tests/test_project_io.py`: validate new and legacy project documents.
- `tests/test_naming.py` and `tests/test_csv_io.py`: prove custom behavior
  names survive existing filename and CSV pathways.
- `tests/test_main_window.py`: test tag lifecycle, partial refresh, toolbar,
  layout, and no-clipping behavior.
- `tests/test_themes.py`: test required Ant selectors and color tokens.

## Task 1: Persist Project-Level Custom Tags And Parse Valid Custom Filenames

**Files:**
- Modify: `video_labeler/project_io.py`
- Modify: `video_labeler/naming.py`
- Test: `tests/test_project_io.py`
- Test: `tests/test_naming.py`
- Test: `tests/test_csv_io.py`

**Interfaces:**
- Produces `LabelProject.custom_behavior_tags: list[str]`.
- Produces unchanged-signature `build_filename(...)` and
  `parse_filename(filename)` behavior that accepts custom syntax-valid tags.
- Consumed by `MainWindow._register_imported_behavior_tags(records)` in Task 2.

- [ ] **Step 1: Write failing persistence and custom-name tests**

```python
def test_project_round_trip_preserves_custom_behavior_tags(tmp_path):
    from video_labeler.project_io import load_project, new_project, save_project

    project = new_project()
    project.custom_behavior_tags = ["vehicle_idle", "delivery_dropoff"]
    target = save_project(tmp_path / "work.labelproj", project)

    assert load_project(target).custom_behavior_tags == [
        "vehicle_idle",
        "delivery_dropoff",
    ]


def test_legacy_project_without_custom_behavior_tags_loads_empty_list(tmp_path):
    from video_labeler.project_io import load_project

    target = tmp_path / "legacy.labelproj"
    target.write_text(
        '{"version":1,"active_video_id":null,"global_settings":{},"videos":[]}',
        encoding="utf-8",
    )

    assert load_project(target).custom_behavior_tags == []


def test_build_and_parse_filename_accepts_custom_behavior_tag():
    metadata = ProjectMetadata(date="20260729", camera="cam02", view="panorama")

    filename = build_filename(
        metadata, ("delivery_dropoff",), "pos", "daytime", 1
    )

    assert filename == (
        "20260729-cam02_panorama-delivery_dropoff-pos-daytime-001.mp4"
    )
    assert parse_filename(filename).behaviors == ("delivery_dropoff",)
```

Add parametrized invalid-project cases for a non-list custom tag value, an
invalid token, a duplicate value, and a built-in value in
`custom_behavior_tags`. Add a CSV assertion that the unchanged four-column
file produces `record.behaviors == ("delivery_dropoff",)`.

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_project_io.py tests/test_naming.py tests/test_csv_io.py -v
```

Expected: FAIL because `LabelProject` lacks `custom_behavior_tags` and
`_validate_labels()` rejects `delivery_dropoff`.

- [ ] **Step 3: Implement the minimal data-layer extension**

In `project_io.py`:

```python
@dataclass
class LabelProject:
    videos: list[ProjectVideo] = field(default_factory=list)
    active_video_id: str | None = None
    global_settings: dict[str, str] = field(default_factory=dict)
    custom_behavior_tags: list[str] = field(default_factory=list)
```

Add a `_validated_custom_behavior_tags(value: Any) -> list[str]` helper that:

- requires a list of strings;
- validates each token through `normalize_label_token(tag, "custom behavior tag")`;
- rejects built-in tags and duplicate values;
- returns the original insertion order.

Import `BEHAVIOR_LABELS` and `normalize_label_token`. In `_validated_document`
accept exactly either the legacy root key set or the new root key set. For a
legacy document, use `[]`; for a new document, validate its list. Include
`custom_behavior_tags` in `project_to_dict()` and the `LabelProject` returned
by `project_from_dict()`.

In `naming.py`, replace the membership test:

```python
if any(behavior not in BEHAVIOR_LABELS for behavior in behaviors):
    raise ValueError("unknown behavior label")
```

with:

```python
for behavior in behaviors:
    normalize_label_token(behavior, "behavior label")
```

Keep the required non-empty behavior condition, sequence validation, metadata
validation, polarity validation, lighting validation, public function names,
and filename output unchanged.

- [ ] **Step 4: Run focused tests to verify success**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_project_io.py tests/test_naming.py tests/test_csv_io.py -v
```

Expected: PASS, including all legacy CSV and project tests.

- [ ] **Step 5: Commit the data foundation locally**

```powershell
git add video_labeler/project_io.py video_labeler/naming.py tests/test_project_io.py tests/test_naming.py tests/test_csv_io.py
git commit -m "feat: persist custom behavior tag library"
```

## Task 2: Add Custom-Tag Lifecycle And Historical-Tag Protection

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes `LabelProject.custom_behavior_tags` from Task 1.
- Adds `MainWindow.add_custom_behavior_tag() -> None`,
  `MainWindow._remove_custom_behavior_tag(tag: str) -> None`, and
  `MainWindow._register_imported_behavior_tags(records: Sequence[ClipRecord]) -> None`.
- Keeps `MainWindow.selected_behaviors() -> tuple[str, ...]` as the editor
  selection API, now including active read-only historical values.

- [ ] **Step 1: Write failing custom-tag lifecycle tests**

```python
def _clip_record_with_behaviors(
    behaviors: tuple[str, ...], sequence: int
) -> ClipRecord:
    return ClipRecord(
        source="source.mp4",
        start_seconds=1.0,
        end_seconds=2.0,
        output=(
            "20260729-cam02_panorama-"
            f"{'+'.join(behaviors)}-pos-daytime-{sequence:03d}.mp4"
        ),
        behaviors=behaviors,
        polarity="pos",
        lighting="daytime",
        sequence=sequence,
    )


def test_custom_behavior_tag_is_registered_rendered_and_persisted(qt_app, tmp_path):
    window = MainWindow()
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    window.add_custom_behavior_tag()

    assert window.project.custom_behavior_tags == ["delivery_dropoff"]
    assert "delivery_dropoff" in window.behavior_checks
    assert window.behavior_checks["delivery_dropoff"].isChecked() is False

    window._project_path = tmp_path / "work.labelproj"
    window.save_project()
    restored = MainWindow()
    assert restored._load_project_path(window._project_path)
    assert "delivery_dropoff" in restored.behavior_checks


def test_removed_custom_tag_stays_in_record_and_renders_historical_capsule(
    qt_app, tmp_path, monkeypatch
):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.project.custom_behavior_tags = ["delivery_dropoff"]
    window._rebuild_behavior_controls()
    window.records.append(
        _clip_record_with_behaviors(("delivery_dropoff",), sequence=1)
    )
    window._refresh_table()
    window.task_table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )

    window._remove_custom_behavior_tag("delivery_dropoff")

    assert window.project.custom_behavior_tags == []
    assert window.records[0].behaviors == ("delivery_dropoff",)
    assert "delivery_dropoff" not in window.behavior_checks
    assert window.historical_behavior_tags == ("delivery_dropoff",)
    assert window.historical_tag_labels["delivery_dropoff"].toolTip().startswith(
        "[Historical Tag]"
    )
    assert not window.historical_tag_labels["delivery_dropoff"].isEnabled()
```

Add focused tests that:

- reject blank and duplicate entries without altering current fixed fields;
- scan references across multiple project videos before prompting;
- preserve a removed historical tag when the selected record is updated;
- remove temporary historical capsules when selecting a record without them;
- turn a historical capsule into a selectable checked control when the same
  name is re-added;
- register a custom tag after importing a CSV whose output filename contains
  `delivery_dropoff`;
- include custom entries in behavior filter and batch-edit tag choices.

- [ ] **Step 2: Run the new main-window tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "custom_behavior or historical_tag or import_csv_registers_behavior" -v
```

Expected: FAIL because the custom control, project-list mutations, and
historical capsule state do not exist.

- [ ] **Step 3: Implement custom-tag controls and safe selection state**

Add a private `RemovableBehaviorCheckBox(QCheckBox)` in
`main_window.py`. It must:

- expose a `removeRequested` signal carrying its tag text;
- create a child `QToolButton` with text `x`, accessible name
  `"删除自定义标签"`, and object name `customTagDeleteButton`;
- position that button at the checkbox top-right during `resizeEvent`;
- leave normal checkbox click/toggle behavior unchanged.

Add and initialize:

```python
self.historical_behavior_tags: tuple[str, ...] = ()
self.historical_tag_labels: dict[str, QLabel] = {}
self.custom_behavior_tag_edit = QLineEdit()
self.add_custom_behavior_tag_button = QPushButton("添加")
```

Refactor built-in checkbox construction into:

```python
def _available_behavior_tags(self) -> tuple[str, ...]:
    return (*BEHAVIOR_LABELS, *self.project.custom_behavior_tags)

def _rebuild_behavior_controls(
    self, selected: Collection[str] = ()
) -> None:
    ...
```

The helper rebuilds only dynamic behavior controls, preserves existing checked
available values, recreates the responsive grid, and schedules the existing
reflow. It adds a read-only `QLabel` with object name
`historicalBehaviorTag` for selected tags not in `_available_behavior_tags()`.
Its tooltip must exactly be:

```text
[Historical Tag] This tag has been removed from tag library, data remains inside this segment, cannot reuse via button
```

Implement:

```python
def _register_imported_behavior_tags(
    self, records: Sequence[ClipRecord]
) -> bool:
    known = set(BEHAVIOR_LABELS) | set(self.project.custom_behavior_tags)
    additions = []
    for record in records:
        for behavior in record.behaviors:
            if behavior not in known:
                additions.append(behavior)
                known.add(behavior)
    if not additions:
        return False
    self.project.custom_behavior_tags.extend(additions)
    self._rebuild_behavior_controls()
    return True
```

Call it immediately after `read_clip_csv()` succeeds and before imported
records are rendered.

`add_custom_behavior_tag()` must normalize with
`normalize_label_token(value, "behavior tag")`, reject empty and duplicates,
append only a new non-built-in value, clear only its input, rebuild the
behavior controls, mark the project dirty, and leave lighting, polarity,
view, ranges, and expander checked states unchanged.

`_remove_custom_behavior_tag()` must scan
`self.project.videos[*].segments` before calling `QMessageBox.question()`.
It removes exactly one top-level custom tag after confirmation, marks dirty,
and rebuilds only behavior controls. It must not edit any `ClipRecord`.

Update `selected_behaviors()` to return checked available tags in grid order
followed by `self.historical_behavior_tags`, removing duplicate strings.
In `_load_selected_clip()`, assign missing selected values to
`historical_behavior_tags` before rebuilding the behavior controls. Clear
that tuple in `_prepare_next_clip()` and `clear_editor()`. When a user
re-adds the same tag, `_rebuild_behavior_controls()` must no longer render its
historical label.

Refresh behavior filter choices from `_available_behavior_tags()` and make
the batch-edit dialog build checks from the same helper.

- [ ] **Step 4: Run focused lifecycle tests to verify success**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "custom_behavior or historical_tag or import_csv_registers_behavior" -v
```

Expected: PASS, with existing behavior-tag tests still selected by:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "behavior_checks or add_clip_prepares or update_clip_prepares" -v
```

- [ ] **Step 5: Commit the custom-tag lifecycle locally**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: add persistent custom behavior tags"
```

## Task 3: Reorganize Existing Workspace Layout Without Changing Workflow

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes the dynamic behavior controls from Task 2.
- Preserves public existing widget attributes used by current tests and
  application signals.
- Produces three toolbar group attributes:
  `import_csv_action_group`, `export_output_action_group`, and
  `settings_operation_action_group`.

- [ ] **Step 1: Write failing layout and partial-refresh tests**

```python
def _same_row(*widgets: QWidget) -> bool:
    y_positions = {widget.mapTo(widget.window(), QPoint(0, 0)).y() for widget in widgets}
    return len(y_positions) == 1


def test_toolbar_uses_three_semantic_action_groups(qt_app):
    window = MainWindow()

    assert window.import_csv_action_group.objectName() == "importCsvActionGroup"
    assert window.export_output_action_group.objectName() == "exportOutputActionGroup"
    assert (
        window.settings_operation_action_group.objectName()
        == "settingsOperationActionGroup"
    )
    assert not window.advanced_export_group.isChecked()


def test_time_fields_and_clip_actions_share_horizontal_rows(qt_app):
    window = MainWindow()
    window.show()
    qt_app.processEvents()

    assert _same_row(window.start_spin, window.end_spin, window.sequence_spin)
    assert _same_row(
        window.add_button,
        window.remove_button,
        window.undo_button,
        window.redo_button,
        window.clear_button,
    )


def test_adding_custom_tag_preserves_fixed_fields_and_expander_states(qt_app):
    window = MainWindow()
    window.set_clip_range(3.0, 5.0)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.behaviors_group.setChecked(False)
    window.lighting_group.setChecked(False)
    window.polarity_group.setChecked(True)
    window.custom_behavior_tag_edit.setText("delivery_dropoff")

    window.add_custom_behavior_tag()

    assert window.start_spin.value() == pytest.approx(3.0)
    assert window.end_spin.value() == pytest.approx(5.0)
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert not window.behaviors_group.isChecked()
    assert not window.lighting_group.isChecked()
    assert window.polarity_group.isChecked()
```

Add a resize test that gives `output_folder_label` a long path, asserts an
ellipsis in its visible text at narrow width, and asserts the full path in its
tooltip. Add a geometry test at `1120x720` and `1440x900` for 5:4 splitter
sizes, no action-row overlap, no tag text clipping, and no dedicated behavior
scroll area.

- [ ] **Step 2: Run the layout tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "toolbar_uses_three or time_fields_and_clip_actions or adding_custom_tag_preserves or output_path" -v
```

Expected: FAIL because the current header has four groups, time/actions use
multiple rows, and light/polarity are not collapsible groups.

- [ ] **Step 3: Implement the layout-only changes**

In `_build_project_header()`:

- replace four visual groups with the three required group widgets while
  retaining every existing button and connection;
- put video import, CSV import, and CSV save in
  `import_csv_action_group`;
- put output picker, output label, and batch export in
  `export_output_action_group`;
- put shortcut help and advanced-export controls in
  `settings_operation_action_group`;
- keep `advanced_export_group.setChecked(False)`.

Replace direct `output_folder_label.setText(...)` calls with:

```python
def _set_output_folder_display(self) -> None:
    full_text = str(self.output_dir) if self.output_dir else "未选择输出文件夹"
    self.output_folder_label.setToolTip(full_text)
    available = max(80, self.output_folder_label.width())
    text = self.output_folder_label.fontMetrics().elidedText(
        full_text, Qt.TextElideMode.ElideMiddle, available
    )
    self.output_folder_label.setText(text)
```

Call it after output-directory changes, project loading, and relevant resize
events. Keep the persisted `output_dir` value unchanged.

In `_build_clip_editor()`:

- replace the time `QFormLayout` with a `QHBoxLayout` of three labeled field
  cells for start, end, and sequence;
- replace the multi-row action grid with one `QHBoxLayout` containing the
  same five existing buttons at fixed equal minimum height;
- retain `addClipButton`, `dangerButton`, `undoButton`, `redoButton`, and
  `clear_button` object names;
- create `self.lighting_group = CollapsibleGroupBox("光照条件")` and
  `self.polarity_group = CollapsibleGroupBox("正负例")`, each with a small
  content widget that owns its existing combo box;
- retain all current combo objects and their signal connections.

Set the existing `editor_splitter` sizes to `5, 4` when it is horizontal.
Keep the existing narrow-window vertical orientation switch and vertical
workspace scroll behavior. Do not change video playback widgets or table
detach/reparent logic.

- [ ] **Step 4: Run focused layout and existing refresh tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "toolbar_uses_three or time_fields_and_clip_actions or adding_custom_tag_preserves or behavior_checks or collapsible or add_clip_prepares or update_clip_prepares or layout" -v
```

Expected: PASS with no widget overlap or text clipping at the tested widths.

- [ ] **Step 5: Commit the layout refactor locally**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: reorganize Ant annotation workspace"
```

## Task 4: Apply The Ant Design Desktop Theme

**Files:**
- Modify: `video_labeler/themes/light_fresh.qss`
- Test: `tests/test_themes.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes semantic object names created in Tasks 2 and 3.
- Produces one globally loaded QSS file; no inline stylesheet is introduced.

- [ ] **Step 1: Write failing theme selector and color-token tests**

```python
def test_light_theme_contains_ant_desktop_tokens_and_custom_tag_states():
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
    for selector in (
        "QWidget#importCsvActionGroup",
        "QWidget#exportOutputActionGroup",
        "QWidget#settingsOperationActionGroup",
        "QCheckBox#behaviorTag:checked",
        "QCheckBox#customBehaviorTag",
        "QLabel#historicalBehaviorTag",
        "QToolButton#customTagDeleteButton",
    ):
        assert selector in stylesheet
```

Add a test that still rejects direct `QFileDialog QListView` and
`QFileDialog QTreeView` selectors while requiring readable
`QFileDialog QAbstractItemView` and viewport styling.

- [ ] **Step 2: Run theme tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py -v
```

Expected: FAIL because the existing palette, 12px/14px radii, and old
toolbar/tag selectors do not satisfy Ant tokens.

- [ ] **Step 3: Replace only QSS presentation values**

Rewrite `light_fresh.qss` around these exact rules:

```css
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog {
    background: #f7f8fa;
    color: #1f2329;
}

QPushButton#primaryButton, QPushButton#addClipButton {
    background: #1677ff;
    border-color: #1677ff;
    color: #ffffff;
}

QPushButton#dangerButton {
    background: #ff7875;
    border-color: #ff7875;
    color: #ffffff;
}

QCheckBox#behaviorTag, QCheckBox#customBehaviorTag {
    background: #e8f3ff;
    border: 1px solid #e5e6eb;
    border-radius: 8px;
    color: #1677ff;
}

QCheckBox#behaviorTag:checked, QCheckBox#customBehaviorTag:checked {
    background: #1677ff;
    border-color: #1677ff;
    color: #ffffff;
}

QLabel#historicalBehaviorTag {
    background: #f2f3f5;
    border: 1px solid #e5e6eb;
    border-radius: 8px;
    color: #86909c;
}
```

Apply `8px` radius and `#e5e6eb` borders to panels, inputs, combo boxes,
tables, sliders, scrollbars, group boxes, and controls. Keep the scoped file
dialog selectors readable with white background and dark text. Retain subtle
existing hover/focus transitions and the no-inline-QSS rule.

- [ ] **Step 4: Run theme and visual geometry tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_themes.py tests/test_main_window.py -k "theme or geometry or clipping or toolbar or behavior_checks" -v
```

Expected: PASS, including file-dialog selector safety and no-clipping tests.

- [ ] **Step 5: Commit the local theme change**

```powershell
git add video_labeler/themes/light_fresh.qss tests/test_themes.py tests/test_main_window.py
git commit -m "style: apply Ant desktop light theme"
```

## Task 5: Complete Regression Verification And Local Review

**Files:**
- Modify only if a test proves a defect: the focused source or test file from
  Tasks 1-4.

**Interfaces:**
- Verifies all existing public application behavior and all new custom-tag
  interactions together.

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run syntax compilation**

Run:

```powershell
D:\Python311\python.exe -m compileall -q app.py video_labeler
```

Expected: exit code `0`.

- [ ] **Step 3: Perform a visual smoke check**

Run the application locally:

```powershell
D:\Python311\python.exe app.py
```

Verify the three toolbar groups, default-collapsed export settings, output
path tooltip, 5:4 desktop splitter, horizontal time/action rows, all three
expanders, custom add/remove controls, historical gray tag capsule, and
no-clipping behavior at both `1120x720` and `1440x900`.

- [ ] **Step 4: Check the final worktree**

Run:

```powershell
git diff --check
git status --short
git log --oneline -5
```

Expected: no whitespace errors; only intentional local work and no Git remote
operation.

- [ ] **Step 5: Commit only any final test-proven fixes locally**

```powershell
git add -- video_labeler/project_io.py video_labeler/naming.py video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_project_io.py tests/test_naming.py tests/test_csv_io.py tests/test_main_window.py tests/test_themes.py
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "fix: complete Ant custom tag regression"
}
```

Do not create an empty commit. Do not push, merge, rebase, or create a pull
request.
