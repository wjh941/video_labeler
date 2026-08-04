# Next Clip State Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a deterministic next-clip draft after every successful add or update without changing stored records or export behavior.

**Architecture:** Keep the behavior in `MainWindow`, where record persistence already occurs. Add one private post-save helper that resets only the next-draft fields, call it after the existing table refresh, and preserve the independent full-record restore behavior in `_load_selected_clip()`.

**Tech Stack:** Python 3.11, PySide6, pytest, existing `ClipRecord` and filename services.

## Global Constraints

- Modify only `video_labeler/ui/main_window.py` and `tests/test_main_window.py`.
- Do not change video playback, import/export behavior, CSV persistence, FFmpeg commands, filename construction, or shared data models.
- Do not change `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, `VIEW_TYPES`, CSV headers or contents, or output filename syntax.
- UI-facing text remains Simplified Chinese; stored label values remain English.
- After every successful add or update: start and end equal the saved end time, behavior selection is empty, polarity/lighting/view are retained, and sequence selects the next available value.
- Selecting exactly one table row continues to load timing, behavior, polarity, lighting, and recoverable view metadata from the record.

---

### Task 1: Specify And Verify The Post-Save Draft State

**Files:**
- Modify: `tests/test_main_window.py:40-61`
- Modify: `tests/test_main_window.py` after the existing add-clip state test
- Modify: `video_labeler/ui/main_window.py:882-931`
- Modify: `video_labeler/ui/main_window.py` near `clear_editor()`

**Interfaces:**
- Consumes: `MainWindow.add_or_update_clip()`, `MainWindow.set_clip_range()`, `MainWindow.selected_behaviors()`, `MainWindow.records`, and existing PySide6 controls.
- Produces: `MainWindow._prepare_next_clip(saved_end_seconds: float) -> None`, called after a successful append or replacement.

- [ ] **Step 1: Replace the obsolete add-state test with a failing next-draft test**

Replace `test_add_clip_keep_label_selected` with this assertion set:

```python
def test_add_clip_prepares_next_clip_and_keeps_fixed_metadata(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.behavior_checks["dog_out"].setChecked(True)
    window.behavior_checks["fall"].setChecked(True)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.set_clip_range(1.0, 2.0)

    window.add_or_update_clip()

    assert len(window.records) == 1
    assert window.sequence_spin.value() == 2
    assert window.start_spin.value() == pytest.approx(2.0)
    assert window.end_spin.value() == pytest.approx(2.0)
    assert window.selected_behaviors() == ()
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window._editing_index is None
    assert window.add_button.text() == "添加片段"
```

- [ ] **Step 2: Add a failing test for updating a record and preparing the next draft**

Add this test directly after the add-state test:

```python
def test_update_clip_prepares_next_clip_and_keeps_fixed_metadata(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.behavior_checks["dog_out"].setChecked(True)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.set_clip_range(1.0, 2.0)
    window.add_or_update_clip()

    window.task_table.selectRow(0)
    qt_app.processEvents()
    window.set_clip_range(1.0, 6.5)
    window.behavior_checks["fall"].setChecked(True)
    window.add_or_update_clip()

    assert len(window.records) == 1
    assert window.records[0].end_seconds == pytest.approx(6.5)
    assert window.sequence_spin.value() == 2
    assert window.start_spin.value() == pytest.approx(6.5)
    assert window.end_spin.value() == pytest.approx(6.5)
    assert window.selected_behaviors() == ()
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window._editing_index is None
    assert window.add_button.text() == "添加片段"
```

- [ ] **Step 3: Run the two tests and verify the current behavior fails**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -q -k "prepares_next_clip"
```

Expected: FAIL because the current implementation neither clears the behavior
checkboxes nor replaces the time range after saving; the update path also
leaves the sequence value on the edited record.

- [ ] **Step 4: Add the shared post-save state helper**

Near `clear_editor()`, add:

```python
def _prepare_next_clip(self, saved_end_seconds: float) -> None:
    self._editing_index = None
    self.add_button.setText("添加片段")
    self.set_clip_range(saved_end_seconds, saved_end_seconds)
    for checkbox in self.behavior_checks.values():
        checkbox.setChecked(False)
    self.sequence_spin.setValue(
        next_sequence([record.sequence for record in self.records])
    )
    self._update_filename_preview()
```

Do not reset `view_combo`, `polarity_combo`, or `lighting_combo` in this
helper. Do not alter `clear_editor()`, whose full-reset behavior remains
independent.

- [ ] **Step 5: Route both persistence branches through the helper**

In `add_or_update_clip()`, keep the existing append-or-replace logic and its
Chinese status message. Remove the append-only `sequence_spin.setValue(...)`
call. After the branch, refresh the table and prepare the next draft from the
record that was just saved:

```python
self._refresh_table()
self._prepare_next_clip(record.end_seconds)
```

The helper must be below the validation `try` block and after the mutation of
`self.records`, so validation errors cannot change the current editor state.

- [ ] **Step 6: Run the focused post-save tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "prepares_next_clip"
```

Expected: PASS. The add and update paths both create a zero-length next draft,
clear behaviors, retain the three fixed metadata selectors, and select the
next available sequence.

- [ ] **Step 7: Commit the post-save transition**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "fix: prepare next clip after save"
```

### Task 2: Protect Full Selected-Row Restoration

**Files:**
- Modify: `tests/test_main_window.py` after the post-save state tests
- Modify: `video_labeler/ui/main_window.py:1119-1150` only if the new test
  exposes an incomplete restoration path

**Interfaces:**
- Consumes: `MainWindow._refresh_table()`, `MainWindow._load_selected_clip()`,
  `ClipRecord`, and the existing table selection signal.
- Produces: A regression guarantee that row selection restores all editable
  fields and remains distinct from post-save preparation.

- [ ] **Step 1: Add a selected-row restoration regression test**

Add this test:

```python
def test_selecting_clip_restores_all_annotation_fields(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="source.mp4",
            start_seconds=12.5,
            end_seconds=18.75,
            output=(
                "20260729-cam02_indoor-dog_out+fall-neg-"
                "night_full_color-007.mp4"
            ),
            behaviors=("dog_out", "fall"),
            polarity="neg",
            lighting="night_full_color",
            sequence=7,
        )
    ]
    window._refresh_table()
    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window._editing_index == 0
    assert window.start_spin.value() == pytest.approx(12.5)
    assert window.end_spin.value() == pytest.approx(18.75)
    assert window.sequence_spin.value() == 7
    assert set(window.selected_behaviors()) == {"dog_out", "fall"}
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
    assert window.view_combo.currentText() == "indoor"
    assert window.add_button.text() == "更新片段"
```

- [ ] **Step 2: Run the selected-row test and verify its baseline**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "selecting_clip_restores_all_annotation_fields"
```

Expected: PASS if `_load_selected_clip()` already restores every field. If it
fails, the failure identifies the missing restore operation; do not change any
post-save reset behavior to address it.

- [ ] **Step 3: Apply only the minimal restoration fix if needed**

Keep the existing responsibilities in `_load_selected_clip()`:

```python
self.start_spin.setValue(record.start_seconds)
self.end_spin.setValue(record.end_seconds)
for behavior, checkbox in self.behavior_checks.items():
    checkbox.setChecked(behavior in record.behaviors)
if parsed is not None:
    self._restore_parsed_metadata(parsed)
```

Use the existing `_set_custom_combo_value()` calls for the record's polarity
and lighting. Do not call `_prepare_next_clip()` from this method.

- [ ] **Step 4: Run the complete UI test module**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
```

Expected: PASS, including the replacement post-save test, update-path test,
selected-row restoration test, shortcut tests, batch-operation tests, and
existing filename/import/UI layout coverage.

- [ ] **Step 5: Run the complete test suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: PASS. This confirms the UI-only interaction change has not changed
CSV, naming, service, export-worker, or other module behavior.

- [ ] **Step 6: Commit the selected-row regression coverage if it changed**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' status --short
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "test: cover annotation editor state transitions"
```

Skip this commit only when Task 2 confirms no source or test changes beyond
the commit created in Task 1; do not create an empty commit.

## Plan Self-Review

Spec coverage:

- Task 1 implements and tests identical post-save state transitions for append
  and update paths, including timing, behavior reset, retained metadata, next
  sequence, edit mode, and button state.
- Task 2 verifies selected-row loading remains a complete record restoration
  path and is not conflated with the post-save reset.
- Task 2 runs both required pytest commands to protect unrelated workflows.

No placeholders:

- The helper signature, call location, test bodies, commands, and commit
  messages are concrete.
- No shared model, CSV, filename, playback, or FFmpeg file appears in the
  modification list.

Type consistency:

- `_prepare_next_clip()` receives the `float` from `record.end_seconds`.
- `next_sequence()` continues to consume the existing list of integer record
  sequence values.
- Tests use the existing `MainWindow`, `ClipRecord`, PySide6 table selection,
  and `pytest.approx` interfaces.
