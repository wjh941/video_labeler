# Stage 1 Productivity UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Chinese annotation workflow with preserved tag state,
collapsible responsive behavior labels, keyboard control, and multi-row task
table actions.

**Architecture:** Keep the entire first-stage implementation in the existing
`MainWindow` and its `QTableWidget`. Add small local helpers for a collapsible
group, shortcut registration, batch updates, filtering, and sorting; do not add
models, controllers, or new modules. `ClipRecord`, `build_filename`, and
`parse_filename` remain the source of truth for row data and standard output
names.

**Tech Stack:** Python 3.11, PySide6 6.7+, pytest 8.

## Global Constraints

- Modify only `video_labeler/ui/main_window.py` and
  `tests/test_main_window.py`.
- Do not change `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, or
  `VIEW_TYPES`.
- Do not change CSV headers or contents, output filename syntax, FFmpeg command
  construction, export-worker behavior, or any other module.
- All new visible UI copy is Simplified Chinese; stored behavior and metadata
  tokens remain English.
- Keep the existing `QTableWidget`; do not introduce `QAbstractTableModel` or
  separate controller files.
- Existing manual output filenames remain intact when they cannot be parsed.

---

## File Structure

- Modify: `video_labeler/ui/main_window.py`
  - Defines `CollapsibleGroupBox` locally and reflows its existing behavior
    checkboxes on resize.
  - Registers window-scoped shortcuts and opens a Chinese help dialog.
  - Extends the task area with extended selection, batch edit/delete, filters,
    clear-filter, and ordering controls.
- Modify: `tests/test_main_window.py`
  - Adds focused regression coverage for each requested Stage 1 UI behavior.

### Task 1: Preserve Labels And Build The Responsive Collapsible Tag Group

**Files:**
- Modify: `video_labeler/ui/main_window.py:80-110,365-437,528-560,714-763`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Produces `CollapsibleGroupBox(QGroupBox)`.
- Produces `MainWindow._reflow_behavior_checks() -> None`.
- Produces
  `MainWindow._set_combo_visible_item_count(combo: QComboBox) -> None`.
- Produces `MainWindow.behavior_checks_container: QWidget`.
- Produces `MainWindow.behavior_columns: int`, always `2` or `3`.
- Overrides `MainWindow.resizeEvent(event) -> None`.

- [ ] **Step 1: Write the failing UI tests**

Add `QGroupBox` to the Qt widget imports, then add:

```python
def test_add_clip_keep_label_selected(qt_app, tmp_path):
    window = MainWindow()
    source_path = tmp_path / "source.mp4"
    window.set_source_path(source_path)
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.behavior_checks["dog_out"].setChecked(True)
    window.behavior_checks["fall"].setChecked(True)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.set_clip_range(1.0, 2.0)

    window.add_or_update_clip()

    assert window.sequence_spin.value() == 2
    assert window.behavior_checks["dog_out"].isChecked()
    assert window.behavior_checks["fall"].isChecked()
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"


def test_collapsible_behavior_group(qt_app):
    window = MainWindow()
    window.show()
    qt_app.processEvents()

    assert isinstance(window.behaviors_group, QGroupBox)
    assert window.behaviors_group.isCheckable()
    assert window.behaviors_group.isChecked()
    assert window.behavior_checks_container.isVisible()

    window.behaviors_group.setChecked(False)
    qt_app.processEvents()
    assert not window.behavior_checks_container.isVisible()

    window.behaviors_group.setChecked(True)
    qt_app.processEvents()
    assert window.behavior_checks_container.isVisible()


def test_tag_area_no_scrollbar(qt_app):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert not window.behaviors_group.findChildren(QScrollArea)
    assert window.behavior_columns == 3

    window.resize(1120, 720)
    qt_app.processEvents()
    assert window.behavior_columns == 2

    assert window.view_combo.maxVisibleItems() == window.view_combo.count()
    assert window.polarity_combo.maxVisibleItems() == window.polarity_combo.count()
    assert window.lighting_combo.maxVisibleItems() == window.lighting_combo.count()
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_collapsible_behavior_group `
  tests\test_main_window.py::test_tag_area_no_scrollbar -v
```

Expected: FAIL because the behavior group is not yet checkable and the window
does not expose a behavior-content container or responsive-column state.

- [ ] **Step 3: Implement the collapsible and responsive behavior group**

In `video_labeler/ui/main_window.py`, add this class after the module
constants:

```python
class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self._content: QWidget | None = None
        self.toggled.connect(self._set_content_visible)

    def set_content(self, content: QWidget) -> None:
        self._content = content
        content.setVisible(self.isChecked())

    def _set_content_visible(self, expanded: bool) -> None:
        if self._content is not None:
            self._content.setVisible(expanded)
```

Replace the direct behavior-checkbox grid in `_build_clip_editor` with an
inner widget owned by the collapsible group:

```python
self.behaviors_group = CollapsibleGroupBox("行为标签")
self.behavior_checks_container = QWidget()
self.behavior_checks_layout = QGridLayout(self.behavior_checks_container)
self.behavior_checks_layout.setContentsMargins(0, 0, 0, 0)
self.behavior_checks_layout.setHorizontalSpacing(10)
self.behavior_checks_layout.setVerticalSpacing(4)
self.behavior_columns = 2

behaviors_layout = QVBoxLayout(self.behaviors_group)
behaviors_layout.setContentsMargins(6, 6, 6, 6)
behaviors_layout.addWidget(self.behavior_checks_container)
self.behaviors_group.set_content(self.behavior_checks_container)
```

Create the current English `QCheckBox` values exactly as they are today, then
call `_reflow_behavior_checks()` after the behavior loop. Implement a reflow
that first removes old layout items before placing existing widgets:

```python
def _reflow_behavior_checks(self) -> None:
    columns = 3 if self.width() >= 1280 else 2
    self.behavior_columns = columns
    while self.behavior_checks_layout.count():
        self.behavior_checks_layout.takeAt(0)
    for index, checkbox in enumerate(self.behavior_checks.values()):
        row, column = divmod(index, columns)
        self.behavior_checks_layout.addWidget(checkbox, row, column)


def resizeEvent(self, event) -> None:
    super().resizeEvent(event)
    if hasattr(self, "behavior_checks_layout"):
        self._reflow_behavior_checks()
```

Set each tag selector to show all of its available entries when opened:

```python
def _set_combo_visible_item_count(self, combo: QComboBox) -> None:
    combo.setMaxVisibleItems(max(1, combo.count()))
```

Call that helper after configuring the view, polarity, and lighting combos and
from `_set_custom_combo_value` after a value is selected or inserted. Do not
create a scroll area inside the behavior group. Do not clear behavior
checkboxes, view, polarity, or lighting in `add_or_update_clip`; retain only
the existing sequence, time, and filename-preview refresh behavior after
appending a record.

- [ ] **Step 4: Run focused tests and verify success**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_add_clip_keep_label_selected `
  tests\test_main_window.py::test_collapsible_behavior_group `
  tests\test_main_window.py::test_tag_area_no_scrollbar -v
```

Expected: PASS. The wide window has three columns, the narrow window has two,
and no nested tag scrollbar exists.

- [ ] **Step 5: Run all tests and commit Task 1**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest -v
```

Expected: PASS for the full suite.

Commit:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\ui\main_window.py `
  tests\test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit `
  -m 'feat: preserve labels in collapsible tag panel'
```

### Task 2: Add Global Shortcuts And Chinese Help

**Files:**
- Modify: `video_labeler/ui/main_window.py:1-34,465-601,790-799`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Produces `SHORTCUT_HELP_ROWS: tuple[tuple[str, str], ...]`.
- Produces `MainWindow.shortcuts: dict[str, QShortcut]`.
- Produces `MainWindow.shortcut_help_button: QPushButton`.
- Produces `MainWindow.shortcut_hint_label: QLabel`.
- Produces `MainWindow._register_shortcuts() -> None`.
- Produces `MainWindow._create_shortcut_help_dialog() -> QDialog`.
- Produces `MainWindow.show_shortcut_help() -> None`.

- [ ] **Step 1: Write the failing shortcut test**

Add `QKeySequence` to the Qt GUI imports and add:

```python
def test_main_window_shortcut_mapping(qt_app):
    window = MainWindow()

    expected = {
        "play_pause": "Space",
        "set_start": "I",
        "set_end": "O",
        "add_clip": "Return",
        "delete_selected": "Del",
        "save_csv": "Ctrl+S",
        "start_export": "Ctrl+E",
        "seek_back_5": "Left",
        "seek_forward_5": "Right",
        "seek_back_30": "Shift+Left",
        "seek_forward_30": "Shift+Right",
    }

    assert set(window.shortcuts) == set(expected)
    assert all(
        window.shortcuts[name].key() == QKeySequence(sequence)
        for name, sequence in expected.items()
    )
    assert window.shortcut_help_button.text() == "快捷键说明"
    assert "空格" in window.shortcut_hint_label.text()

    dialog = window._create_shortcut_help_dialog()
    assert dialog.windowTitle() == "快捷键说明"
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_main_window_shortcut_mapping -v
```

Expected: FAIL because `MainWindow` has no shortcut registry, help button, or
dialog factory.

- [ ] **Step 3: Register window shortcuts and build the help dialog**

Import `QKeySequence` and `QShortcut` from `PySide6.QtGui`, and `QDialog` and
`QDialogButtonBox` from `PySide6.QtWidgets`. Define the fixed Chinese help
rows:

```python
SHORTCUT_HELP_ROWS = (
    ("Space", "播放或暂停"),
    ("I", "设置起始点"),
    ("O", "设置结束点"),
    ("Enter", "添加或更新片段"),
    ("Delete", "删除选中片段"),
    ("Ctrl+S", "保存标注 CSV"),
    ("Ctrl+E", "批量导出"),
    ("Left / Right", "后退或前进 5 秒"),
    ("Shift+Left / Shift+Right", "后退或前进 30 秒"),
)
```

Add a `shortcut_help_button` with text `快捷键说明` to the project-header
command row. Add a separate persistent `shortcut_hint_label` to
`_build_export_status`; use Chinese text that includes `空格`, `I/O`, `Enter`,
`Delete`, `Ctrl+S`, and `Ctrl+E`. `_set_status` must continue to update only
the dynamic `status_label`.

Call `_register_shortcuts()` at the end of `_connect_signals`. Each binding
uses `Qt.ShortcutContext.WindowShortcut`:

```python
def _register_shortcuts(self) -> None:
    bindings = {
        "play_pause": ("Space", self.toggle_playback),
        "set_start": (
            "I",
            lambda: self.start_spin.setValue(self.player.position() / 1000),
        ),
        "set_end": (
            "O",
            lambda: self.end_spin.setValue(self.player.position() / 1000),
        ),
        "add_clip": ("Return", self.add_or_update_clip),
        "delete_selected": ("Del", self.remove_selected_clip),
        "save_csv": ("Ctrl+S", self.save_csv),
        "start_export": ("Ctrl+E", self.start_export),
        "seek_back_5": ("Left", lambda: self._seek_relative(-5000)),
        "seek_forward_5": ("Right", lambda: self._seek_relative(5000)),
        "seek_back_30": ("Shift+Left", lambda: self._seek_relative(-30000)),
        "seek_forward_30": ("Shift+Right", lambda: self._seek_relative(30000)),
    }
    self.shortcuts = {}
    for name, (sequence, callback) in bindings.items():
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts[name] = shortcut
```

Implement `_create_shortcut_help_dialog` with a `QDialog`, a two-column
`QTableWidget`, Chinese headers `快捷键` and `操作`, all
`SHORTCUT_HELP_ROWS`, and a close button using
`QDialogButtonBox.StandardButton.Close`. Connect the header button to
`show_shortcut_help`, which creates the dialog and executes it modally.

- [ ] **Step 4: Run the focused shortcut test**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_main_window_shortcut_mapping -v
```

Expected: PASS for shortcut registration, Chinese help controls, and the
permanent status hint.

- [ ] **Step 5: Run all tests and commit Task 2**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest -v
```

Expected: PASS for the full suite.

Commit:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\ui\main_window.py `
  tests\test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit `
  -m 'feat: add annotation keyboard shortcuts'
```

### Task 3: Extend The Task Table With Batch Edit, Delete, Filters, And Sort

**Files:**
- Modify: `video_labeler/ui/main_window.py:39-55,439-463,561-601,765-775,853-918`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Produces `MainWindow.batch_edit_button`, `batch_delete_button`,
  `behavior_filter_combo`, `polarity_filter_combo`, `status_filter_combo`,
  `sort_combo`, and `clear_filters_button`.
- Produces `MainWindow._selected_record_indexes() -> list[int]`.
- Produces `MainWindow._apply_table_filters() -> None`.
- Produces `MainWindow._sync_filter_options() -> None`.
- Produces `MainWindow.clear_table_filters() -> None`.
- Produces `MainWindow._sort_records() -> None`.
- Produces
  `MainWindow._apply_batch_changes(indexes, behaviors, polarity, lighting, view)
  -> None`, with `None` meaning leave a field unchanged.
- Produces `MainWindow.show_batch_edit_dialog() -> None`.
- Produces `MainWindow._delete_selected_records() -> None`.

- [ ] **Step 1: Write the failing table-control test**

Add `QAbstractItemView` to the Qt widget imports and add:

```python
def test_table_batch_operation_chinese_text(qt_app):
    window = MainWindow()

    assert window.task_table.selectionMode() == (
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    assert window.batch_edit_button.text() == "批量修改选中片段"
    assert window.batch_delete_button.text() == "批量删除选中"
    assert window.clear_filters_button.text() == "清空筛选"
    assert window.behavior_filter_combo.itemText(0) == "全部行为"
    assert window.polarity_filter_combo.itemText(0) == "全部正负例"
    assert window.status_filter_combo.itemText(0) == "全部导出状态"

    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=0,
            end_seconds=2,
            output="20260729-cam02_panorama-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        ),
        ClipRecord(
            source="source.mp4",
            start_seconds=2,
            end_seconds=8,
            output=(
                "20260729-cam02_panorama-fall-neg-night_full_color-002.mp4"
            ),
            behaviors=("fall",),
            polarity="neg",
            lighting="night_full_color",
            sequence=2,
            status="fail",
        ),
    ]
    window._refresh_table()

    window.behavior_filter_combo.setCurrentData("fall")
    assert window.task_table.isRowHidden(0)
    assert not window.task_table.isRowHidden(1)

    window.clear_filters_button.click()
    assert not window.task_table.isRowHidden(0)
    assert not window.task_table.isRowHidden(1)

    window._apply_batch_changes(
        [0],
        behaviors=("fall",),
        polarity="neg",
        lighting=None,
        view=None,
    )
    assert window.records[0].behaviors == ("fall",)
    assert window.records[0].polarity == "neg"

    window.sort_combo.setCurrentIndex(3)
    assert [record.sequence for record in window.records] == [2, 1]


def test_batch_delete_selected_rows_after_confirmation(qt_app, monkeypatch):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=index,
            end_seconds=index + 1,
            output=f"clip-{index}.mp4",
            sequence=index,
        )
        for index in range(1, 4)
    ]
    window._refresh_table()
    window.task_table.selectRow(0)
    window.task_table.selectionModel().select(
        window.task_table.model().index(2, 0),
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes
        ),
    )

    window._delete_selected_records()

    assert [record.sequence for record in window.records] == [2]
```

Add `QItemSelectionModel` to the Qt core imports for the second test.

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_table_batch_operation_chinese_text `
  tests\test_main_window.py::test_batch_delete_selected_rows_after_confirmation -v
```

Expected: FAIL because the current task table is single-selection and the
batch/filter controls do not exist.

- [ ] **Step 3: Create Chinese controls, filters, and ordering**

In `_build_task_table`, use extended row selection:

```python
self.task_table.setSelectionMode(
    QAbstractItemView.SelectionMode.ExtendedSelection
)
```

Place a compact toolbar above the table:

```python
self.batch_edit_button = QPushButton("批量修改选中片段")
self.batch_delete_button = QPushButton("批量删除选中")
self.behavior_filter_combo = QComboBox()
self.polarity_filter_combo = QComboBox()
self.status_filter_combo = QComboBox()
self.sort_combo = QComboBox()
self.clear_filters_button = QPushButton("清空筛选")
```

Store English filter values as item data:

```python
self.behavior_filter_combo.addItem("全部行为", None)
for behavior in BEHAVIOR_LABELS:
    self.behavior_filter_combo.addItem(behavior, behavior)

self.polarity_filter_combo.addItem("全部正负例", None)
for polarity in POLARITIES:
    self.polarity_filter_combo.addItem(polarity, polarity)

self.status_filter_combo.addItem("全部导出状态", None)
for status, label in STATUS_LABELS.items():
    self.status_filter_combo.addItem(label, status)

self.sort_combo.addItem("编号升序", ("sequence", False))
self.sort_combo.addItem("编号降序", ("sequence", True))
self.sort_combo.addItem("时长升序", ("duration", False))
self.sort_combo.addItem("时长降序", ("duration", True))
```

Connect the three filters to `_apply_table_filters`, connect `sort_combo` to
`_sort_records`, connect `clear_filters_button` to `clear_table_filters`, and
connect `batch_edit_button` and `batch_delete_button` to their respective
methods. At the end of `_refresh_table`, call `_sync_filter_options()` then
`_apply_table_filters()`.

`_sync_filter_options` keeps each current filter data value, adds observed
non-empty record polarity and status values not already present, restores the
same selection when it still exists, and calls
`_set_combo_visible_item_count` for every filter and sort combo. This permits
existing custom values without changing shared English constants.

Implement:

```python
def _apply_table_filters(self) -> None:
    behavior = self.behavior_filter_combo.currentData()
    polarity = self.polarity_filter_combo.currentData()
    status = self.status_filter_combo.currentData()
    for row, record in enumerate(self.records):
        visible = (
            (behavior is None or behavior in record.behaviors)
            and (polarity is None or polarity == record.polarity)
            and (status is None or status == record.status)
        )
        self.task_table.setRowHidden(row, not visible)


def clear_table_filters(self) -> None:
    self.behavior_filter_combo.setCurrentIndex(0)
    self.polarity_filter_combo.setCurrentIndex(0)
    self.status_filter_combo.setCurrentIndex(0)
    self._apply_table_filters()


def _sort_records(self) -> None:
    key_name, reverse = self.sort_combo.currentData()
    if key_name == "duration":
        self.records.sort(
            key=lambda record: record.end_seconds - record.start_seconds,
            reverse=reverse,
        )
    else:
        self.records.sort(key=lambda record: record.sequence, reverse=reverse)
    self._editing_index = None
    self._refresh_table()
```

Update `_load_selected_clip` so selecting multiple rows leaves add mode active
instead of loading an arbitrary record:

```python
if len(selected) != 1:
    self._editing_index = None
    self.add_button.setText("添加片段")
    return
```

- [ ] **Step 4: Implement batch update and deletion**

Import `replace` from `dataclasses`. Add:

```python
def _selected_record_indexes(self) -> list[int]:
    return sorted(
        {index.row() for index in self.task_table.selectionModel().selectedRows()}
    )
```

`show_batch_edit_dialog` creates a local `QDialog` with four Chinese
`应用此字段` checkboxes for behavior, polarity, lighting, and view. It supplies
the current English behavior labels and selectors cloned from the main editor,
excluding `CUSTOM_OPTION_TEXT`. On accept, an enabled behavior replacement
requires at least one selected behavior; unchecked fields pass `None`.

Start the method by rejecting an empty selection without opening a dialog:

```python
indexes = self._selected_record_indexes()
if not indexes:
    self._show_error("未选择片段", "请先选择至少一个片段。")
    return
```

Implement `_apply_batch_changes` as an atomic two-pass operation:

```python
def _apply_batch_changes(
    self,
    indexes: list[int],
    behaviors: tuple[str, ...] | None,
    polarity: str | None,
    lighting: str | None,
    view: str | None,
) -> None:
    selected_indexes = set(indexes)
    proposed: dict[int, ClipRecord] = {}
    skipped_manual_view = False

    for index in indexes:
        record = self.records[index]
        next_behaviors = behaviors if behaviors is not None else record.behaviors
        next_polarity = polarity if polarity is not None else record.polarity
        next_lighting = lighting if lighting is not None else record.lighting
        parsed = parse_filename(record.output)
        output = record.output

        if parsed is not None:
            metadata = ProjectMetadata(
                date=parsed.metadata.date,
                camera=parsed.metadata.camera,
                view=view if view is not None else parsed.metadata.view,
            )
            output = build_filename(
                metadata,
                next_behaviors,
                next_polarity,
                next_lighting,
                parsed.sequence,
            )
        elif view is not None:
            skipped_manual_view = True

        proposed[index] = replace(
            record,
            output=output,
            behaviors=next_behaviors,
            polarity=next_polarity,
            lighting=next_lighting,
        )

    existing_outputs = {
        record.output.lower()
        for index, record in enumerate(self.records)
        if index not in selected_indexes
    }
    proposed_outputs: set[str] = set()
    for record in proposed.values():
        output = record.output.lower()
        if output in existing_outputs or output in proposed_outputs:
            raise ValueError(f"批量修改后输出文件名重复：{record.output}")
        proposed_outputs.add(output)

    for index, record in proposed.items():
        self.records[index] = record
    self._editing_index = None
    self._refresh_table()
    if skipped_manual_view:
        self._set_status("批量修改完成；手动命名片段未更新视角")
    else:
        self._set_status(f"已批量修改 {len(indexes)} 个片段")
```

Create the batch dialog using only local widgets:

```python
dialog = QDialog(self)
dialog.setWindowTitle("批量修改选中片段")
layout = QVBoxLayout(dialog)

apply_behaviors = QCheckBox("应用此字段：行为标签")
batch_behavior_checks = {
    behavior: QCheckBox(behavior) for behavior in BEHAVIOR_LABELS
}
apply_polarity = QCheckBox("应用此字段：正负例")
polarity_combo = _copy_data_combo(self.polarity_combo)
apply_lighting = QCheckBox("应用此字段：光照")
lighting_combo = _copy_data_combo(self.lighting_combo)
apply_view = QCheckBox("应用此字段：视角")
view_combo = _copy_data_combo(self.view_combo)
buttons = QDialogButtonBox(
    QDialogButtonBox.StandardButton.Ok
    | QDialogButtonBox.StandardButton.Cancel
)
```

Define `_copy_data_combo` as a local nested function that copies every item
whose text is not `CUSTOM_OPTION_TEXT`, then add each checkbox and its
corresponding controls to `layout`. Connect `buttons.accepted` to
`dialog.accept` and `buttons.rejected` to `dialog.reject`. After
`dialog.exec()`, return unless accepted. Convert controls with:

```python
behaviors = (
    tuple(
        behavior
        for behavior, checkbox in batch_behavior_checks.items()
        if checkbox.isChecked()
    )
    if apply_behaviors.isChecked()
    else None
)
if behaviors == ():
    self._show_error("批量修改失败", "应用行为标签时至少选择一个行为。")
    return

polarity = polarity_combo.currentText() if apply_polarity.isChecked() else None
lighting = lighting_combo.currentText() if apply_lighting.isChecked() else None
view = view_combo.currentText() if apply_view.isChecked() else None
```

Call `_apply_batch_changes` inside `try`/`except ValueError`, and call
`_show_error("批量修改失败", str(error))` in the exception handler:

```python
try:
    self._apply_batch_changes(indexes, behaviors, polarity, lighting, view)
except ValueError as error:
    self._show_error("批量修改失败", str(error))
```

Implement `_delete_selected_records` with `_selected_record_indexes`. With no
selection, show a Chinese no-selection error. Otherwise use
`QMessageBox.question` with the selected count in the Chinese confirmation
text. After approval, remove records in descending index order, clear
`_editing_index`, refresh the table, and show a Chinese status. Route the
existing `remove_selected_clip` method through `_delete_selected_records`, so
the original remove button and Delete shortcut have identical confirmation
semantics.

```python
def _delete_selected_records(self) -> None:
    indexes = self._selected_record_indexes()
    if not indexes:
        self._show_error("未选择片段", "请先选择至少一个片段。")
        return
    answer = QMessageBox.question(
        self,
        "确认批量删除",
        f"确定删除选中的 {len(indexes)} 个片段吗？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    for index in reversed(indexes):
        del self.records[index]
    self._editing_index = None
    self._refresh_table()
    self._set_status(f"已删除 {len(indexes)} 个片段")
```

- [ ] **Step 5: Run the focused table test**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest `
  tests\test_main_window.py::test_table_batch_operation_chinese_text -v
```

Expected: PASS for extended selection, Chinese controls, filtering,
clear-filter behavior, and batch metadata changes.

- [ ] **Step 6: Run all tests and commit Task 3**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest -v
```

Expected: PASS for the full suite.

Commit:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\ui\main_window.py `
  tests\test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit `
  -m 'feat: add batch task controls and filters'
```

## Final Verification

- [ ] Run `& 'D:\Python311\python.exe' -m pytest tests\test_main_window.py -v`.
- [ ] Run `& 'D:\Python311\python.exe' -m pytest tests -v`.
- [ ] Run `& 'D:\Python311\python.exe' -m compileall -q app.py video_labeler`.
- [ ] Run `& 'C:\Program Files\Git\cmd\git.exe' diff --check`.
- [ ] Verify `git status --short` is clean after the Stage 1 commits.
