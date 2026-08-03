# Custom Annotation Dropdowns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the built-in `indoor` view and let operators add valid custom
view, polarity, and lighting values that work in filenames, CSV imports, and
selected task editing.

**Architecture:** Keep metadata token rules in `video_labeler.naming`, where
filename building and parsing already meet. The PySide6 main window receives a
small reusable dropdown helper that opens a Chinese prompt, normalizes and
validates input through the naming module, and inserts the value before a
non-data custom action. CSV handling stays structurally unchanged because it
already delegates filename metadata recovery to `parse_filename`.

**Tech Stack:** Python 3.11, PySide6 6.7+, pytest 8, standard-library `re`.

## Global Constraints

- Built-in view values are exactly `panorama`, `closeup`, and `indoor`.
- Only view, polarity, and lighting receive a custom action; export mode and
  playback speed remain fixed controls.
- Custom values are trimmed and lowercased before storing.
- Views must match `[a-z0-9]+`; polarity and lighting must match `[a-z0-9_]+`.
- Behavior labels stay the fixed English preset list.
- UI feedback is Chinese while stored tags and filename tokens remain English.
- Custom options are session-local, but importing a CSV restores valid values
  required by that project.
- The existing CSV columns and filename format remain unchanged.

---

## File Structure

- Modify: `video_labeler/models.py`
  - Adds `indoor` to the built-in `VIEW_TYPES` tuple.
- Modify: `video_labeler/naming.py`
  - Normalizes/validates editable metadata tokens and parses the final
    `camera_view` separator safely.
- Modify: `video_labeler/ui/main_window.py`
  - Adds the custom dropdown action, prompt handling, option insertion, and
    metadata restoration for imported and selected records.
- Modify: `tests/test_naming.py`
  - Covers built-in `indoor`, custom filename tokens, parsing, and rejection.
- Modify: `tests/test_csv_io.py`
  - Proves a CSV row restores custom parsed metadata.
- Modify: `tests/test_main_window.py`
  - Covers dropdown setup, prompting, invalid/cancel restoration, and CSV/task
    editing behavior.

### Task 1: Metadata Token Rules And Filename Parsing

**Files:**
- Modify: `video_labeler/models.py:14`
- Modify: `video_labeler/naming.py:15-104`
- Modify: `tests/test_naming.py`
- Modify: `tests/test_csv_io.py`

**Interfaces:**
- Produces `normalize_view_token(value: str) -> str`.
- Produces `normalize_label_token(value: str, field_name: str) -> str`.
- `build_filename(...)` returns normalized view, polarity, and lighting tokens
  in the filename.
- `parse_filename(filename: str) -> ParsedFilename | None` returns normalized
  `ProjectMetadata.view`, polarity, and lighting values for valid files.

- [ ] **Step 1: Write the failing domain and CSV tests**

Add these imports and tests to `tests/test_naming.py`:

```python
from video_labeler.models import VIEW_TYPES


def test_indoor_is_a_builtin_view_option():
    assert "indoor" in VIEW_TYPES


def test_build_and_parse_filename_supports_custom_metadata_tokens():
    metadata = ProjectMetadata(date="20260729", camera="cam_02", view="Doorway")

    filename = build_filename(
        metadata,
        ("dog_out",),
        "Needs_Review",
        "Night_Red",
        7,
    )

    assert filename == (
        "20260729-cam_02_doorway-dog_out-needs_review-night_red-007.mp4"
    )
    parsed = parse_filename(filename)
    assert parsed is not None
    assert parsed.metadata.camera == "cam_02"
    assert parsed.metadata.view == "doorway"
    assert parsed.polarity == "needs_review"
    assert parsed.lighting == "night_red"


@pytest.mark.parametrize(
    ("metadata", "polarity", "lighting", "field"),
    (
        (
            ProjectMetadata("20260729", "cam02", "indoor_room"),
            "pos",
            "daytime",
            "view",
        ),
        (
            ProjectMetadata("20260729", "cam02", "indoor"),
            "needs review",
            "daytime",
            "polarity",
        ),
        (
            ProjectMetadata("20260729", "cam02", "indoor"),
            "pos",
            "night-red",
            "lighting",
        ),
    ),
)
def test_build_filename_rejects_invalid_editable_metadata_tokens(
    metadata, polarity, lighting, field
):
    with pytest.raises(ValueError, match=field):
        build_filename(metadata, ("dog_out",), polarity, lighting, 1)
```

Add this test to `tests/test_csv_io.py`:

```python
def test_read_clip_csv_restores_custom_filename_labels(tmp_path):
    csv_path = tmp_path / "custom-clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:02.500,00:00:04.000,"
            "20260729-cam_02_doorway-dog_out-needs_review-night_red-007.mp4\n"
        ),
        encoding="utf-8-sig",
    )

    record = read_clip_csv(csv_path)[0]

    assert record.behaviors == ("dog_out",)
    assert record.polarity == "needs_review"
    assert record.lighting == "night_red"
    assert record.sequence == 7
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests\test_naming.py tests\test_csv_io.py -v
```

Expected: failure because `indoor` is absent and custom metadata tokens are
rejected by the current fixed tuples.

- [ ] **Step 3: Implement shared token normalization and parsing**

In `video_labeler/models.py`, replace the view tuple with:

```python
VIEW_TYPES = ("panorama", "closeup", "indoor")
```

In `video_labeler/naming.py`, add lower-case token patterns and public
normalizers:

```python
_VIEW_TOKEN_PATTERN = re.compile(r"^[a-z0-9]+$")
_LABEL_TOKEN_PATTERN = re.compile(r"^[a-z0-9_]+$")


def normalize_view_token(value: str) -> str:
    normalized = value.strip().lower()
    if not _VIEW_TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError("view must use lowercase English letters and digits")
    return normalized


def normalize_label_token(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not _LABEL_TOKEN_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"{field_name} must use lowercase English letters, digits, or underscores"
        )
    return normalized
```

Make `_validate_metadata` return a normalized `ProjectMetadata`, make
`_validate_labels` return normalized polarity and lighting, and use the returned
values in `build_filename`:

```python
def _validate_metadata(metadata: ProjectMetadata) -> ProjectMetadata:
    if not _DATE_PATTERN.fullmatch(metadata.date):
        raise ValueError("date must use YYYYMMDD format")
    if not _TOKEN_PATTERN.fullmatch(metadata.camera):
        raise ValueError("camera must use English letters, digits, or underscores")
    return ProjectMetadata(
        date=metadata.date,
        camera=metadata.camera,
        view=normalize_view_token(metadata.view),
    )
```

Keep behavior validation fixed. Replace the polarity and lighting tuple
membership checks with this exact return value:

```python
def _validate_labels(
    behaviors: tuple[str, ...],
    polarity: str,
    lighting: str,
    sequence: int,
) -> tuple[str, str]:
    if not behaviors:
        raise ValueError("at least one behavior label is required")
    if any(behavior not in BEHAVIOR_LABELS for behavior in behaviors):
        raise ValueError("unknown behavior label")
    if sequence < 1:
        raise ValueError("sequence must be at least 1")
    return (
        normalize_label_token(polarity, "polarity"),
        normalize_label_token(lighting, "lighting"),
    )
```

Assign `metadata = _validate_metadata(metadata)` and
`polarity, lighting = _validate_labels(...)` at the beginning of
`build_filename`, then use those local values in its returned string.

In `parse_filename`, replace suffix matching against `VIEW_TYPES` with final
underscore splitting:

```python
camera, separator, view = camera_and_view.rpartition("_")
if not separator:
    return None
```

After splitting, validate and retain the normalized values explicitly:

```python
try:
    sequence = int(sequence_text)
    metadata = _validate_metadata(
        ProjectMetadata(date=date, camera=camera, view=view)
    )
    polarity, lighting = _validate_labels(
        behaviors,
        polarity,
        lighting,
        sequence,
    )
except ValueError:
    return None
```

Construct `ParsedFilename` from these normalized `metadata`, `polarity`, and
`lighting` variables. This keeps `cam_02_doorway` unambiguous as camera
`cam_02`, view `doorway`.

- [ ] **Step 4: Run the focused tests and verify success**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests\test_naming.py tests\test_csv_io.py -v
```

Expected: all naming and CSV tests pass, including built-in `indoor`, normalized
custom metadata, invalid-token rejection, and custom CSV recovery.

- [ ] **Step 5: Commit the domain change**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\models.py `
  video_labeler\naming.py `
  tests\test_naming.py `
  tests\test_csv_io.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m 'feat: support custom metadata filename tokens'
```

### Task 2: Custom Dropdown Prompt And Option Registration

**Files:**
- Modify: `video_labeler/ui/main_window.py:1-490`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Produces `CUSTOM_OPTION_TEXT`, the final non-data dropdown entry.
- Produces `_configure_custom_combo(...) -> None` to attach the action to a
  `QComboBox`.
- Produces `_set_custom_combo_value(...) -> None` to validate, add, and select
  a real value before `CUSTOM_OPTION_TEXT`.
- Leaves `mode_combo` and `speed_combo` with their existing fixed values only.

- [ ] **Step 1: Write the failing interactive-control tests**

Add `QInputDialog` to the Qt widget imports in `tests/test_main_window.py`. Add:

```python
def test_editable_metadata_combos_include_custom_action(qt_app):
    window = MainWindow()

    assert window.view_combo.itemText(window.view_combo.count() - 1) == "自定义..."
    assert window.polarity_combo.itemText(window.polarity_combo.count() - 1) == "自定义..."
    assert window.lighting_combo.itemText(window.lighting_combo.count() - 1) == "自定义..."
    assert [window.mode_combo.itemText(index) for index in range(window.mode_combo.count())] == [
        "encode",
        "copy",
    ]
    assert [window.speed_combo.itemText(index) for index in range(window.speed_combo.count())] == [
        "0.5x",
        "1.0x",
        "1.5x",
        "2.0x",
    ]


@pytest.mark.parametrize(
    ("combo_name", "entered", "expected"),
    (
        ("view_combo", " DoorWay ", "doorway"),
        ("polarity_combo", " Needs_Review ", "needs_review"),
        ("lighting_combo", " Night_Red ", "night_red"),
    ),
)
def test_custom_metadata_prompt_normalizes_adds_and_selects_value(
    qt_app, monkeypatch, combo_name, entered, expected
):
    window = MainWindow()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: (entered, True)),
    )
    combo = getattr(window, combo_name)

    combo.setCurrentIndex(combo.count() - 1)

    assert combo.currentText() == expected
    assert combo.itemText(combo.count() - 2) == expected
    assert combo.itemText(combo.count() - 1) == "自定义..."


def test_invalid_custom_view_restores_previous_selection(qt_app, monkeypatch):
    window = MainWindow()
    messages = []
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: ("indoor_room", True)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: messages.append((title, text))),
    )

    window.view_combo.setCurrentText("panorama")
    window.view_combo.setCurrentIndex(window.view_combo.count() - 1)

    assert window.view_combo.currentText() == "panorama"
    assert messages
    assert "仅支持小写英文和数字" in messages[0][1]


def test_canceling_custom_value_restores_previous_selection(qt_app, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *_args, **_kwargs: ("", False)),
    )

    window.polarity_combo.setCurrentText("neg")
    window.polarity_combo.setCurrentIndex(window.polarity_combo.count() - 1)

    assert window.polarity_combo.currentText() == "neg"
```

- [ ] **Step 2: Run the focused UI tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests\test_main_window.py -v
```

Expected: failure because the three editable dropdowns have no custom action and
selecting their final built-in item does not invoke a prompt.

- [ ] **Step 3: Implement the reusable custom dropdown behavior**

In `video_labeler/ui/main_window.py`, add `QInputDialog` and
`collections.abc.Callable` imports. Import `normalize_label_token` and
`normalize_view_token` from `video_labeler.naming`. Define:

```python
CUSTOM_OPTION_TEXT = "自定义..."
```

After adding built-in values in `_build_project_header` and `_build_clip_editor`,
call `_configure_custom_combo` with the field name, validator, and Chinese
guidance:

```python
self._configure_custom_combo(
    self.view_combo,
    "视角",
    normalize_view_token,
    "仅支持小写英文和数字。",
)
self._configure_custom_combo(
    self.polarity_combo,
    "正负性",
    lambda value: normalize_label_token(value, "polarity"),
    "仅支持小写英文、数字和下划线。",
)
self._configure_custom_combo(
    self.lighting_combo,
    "光照",
    lambda value: normalize_label_token(value, "lighting"),
    "仅支持小写英文、数字和下划线。",
)
```

Implement `_configure_custom_combo` so it appends `CUSTOM_OPTION_TEXT`, records
the current valid index in a widget property, and calls
`_request_custom_combo_value` only when that sentinel is selected:

```python
def _configure_custom_combo(
    self,
    combo: QComboBox,
    field_name: str,
    normalize: Callable[[str], str],
    guidance: str,
) -> None:
    combo.addItem(CUSTOM_OPTION_TEXT)
    combo.setProperty("last_valid_index", combo.currentIndex())
    combo.currentIndexChanged.connect(
        lambda index: self._request_custom_combo_value(
            combo, index, field_name, normalize, guidance
        )
    )
```

Use the following method shapes:

```python
def _request_custom_combo_value(
    self,
    combo: QComboBox,
    index: int,
    field_name: str,
    normalize: Callable[[str], str],
    guidance: str,
) -> None:
    if combo.itemText(index) != CUSTOM_OPTION_TEXT:
        combo.setProperty("last_valid_index", index)
        return

    previous_index = int(combo.property("last_valid_index"))
    value, accepted = QInputDialog.getText(
        self,
        "添加自定义选项",
        f"请输入自定义{field_name}：",
    )
    if not accepted:
        combo.setCurrentIndex(previous_index)
        return
    try:
        self._set_custom_combo_value(combo, value, normalize)
    except ValueError:
        combo.setCurrentIndex(previous_index)
        self._show_error("自定义选项无效", f"{field_name}无效：{guidance}")


def _set_custom_combo_value(
    self,
    combo: QComboBox,
    value: str,
    normalize: Callable[[str], str],
) -> None:
    normalized = normalize(value)
    index = combo.findText(normalized)
    if index < 0:
        index = combo.findText(CUSTOM_OPTION_TEXT)
        combo.insertItem(index, normalized)
    combo.setCurrentIndex(index)
    combo.setProperty("last_valid_index", index)
```

The `ValueError` is intentionally handled by the prompt path. Import and
record-loading paths only call this method with values already validated by
`parse_filename`.

- [ ] **Step 4: Run the focused UI tests and verify success**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests\test_main_window.py -v
```

Expected: all existing UI tests plus the custom-action, normalization, invalid
input, and fixed-control tests pass.

- [ ] **Step 5: Commit the interactive control change**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\ui\main_window.py `
  tests\test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m 'feat: add custom metadata dropdown values'
```

### Task 3: Restore Custom Metadata During Import And Editing

**Files:**
- Modify: `video_labeler/ui/main_window.py:524-545,770-787`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes `_set_custom_combo_value(combo, value, normalize)` from Task 2.
- Updates `import_csv() -> None` to register every valid parsed metadata value
  in imported records before setting the project controls.
- Updates `_load_selected_clip() -> None` to restore parsed date, camera, view,
  polarity, and lighting using the same combo helper.

- [ ] **Step 1: Write the failing import and selection tests**

Add `QFileDialog` to the Qt widget imports in `tests/test_main_window.py`. Add
these tests:

```python
def test_import_csv_registers_custom_metadata_values(qt_app, tmp_path, monkeypatch):
    csv_path = tmp_path / "custom-clips.csv"
    csv_path.write_text(
        (
            "source,start,end,output\n"
            "cam02.mp4,00:00:01.000,00:00:02.000,"
            "20260729-cam_02_doorway-dog_out-needs_review-night_red-001.mp4\n"
        ),
        encoding="utf-8-sig",
    )
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(csv_path), "CSV 文件 (*.csv)")),
    )

    window.import_csv()

    assert window.view_combo.currentText() == "doorway"
    assert window.polarity_combo.findText("needs_review") >= 0
    assert window.lighting_combo.findText("night_red") >= 0


def test_selecting_custom_metadata_record_restores_all_metadata_combos(qt_app):
    window = MainWindow()
    window.records = [
        ClipRecord(
            source="cam02.mp4",
            start_seconds=1,
            end_seconds=2,
            output=(
                "20260729-cam_02_doorway-dog_out-needs_review-night_red-001.mp4"
            ),
            behaviors=("dog_out",),
            polarity="needs_review",
            lighting="night_red",
            sequence=1,
        )
    ]
    window._refresh_table()

    window.task_table.selectRow(0)
    qt_app.processEvents()

    assert window.date_edit.text() == "20260729"
    assert window.camera_edit.text() == "cam_02"
    assert window.view_combo.currentText() == "doorway"
    assert window.polarity_combo.currentText() == "needs_review"
    assert window.lighting_combo.currentText() == "night_red"
```

- [ ] **Step 2: Run the focused UI tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests\test_main_window.py -v
```

Expected: failure because import only selects the view of the first record
without registering it, and selecting a record does not restore date, camera, or
custom dropdown values.

- [ ] **Step 3: Restore valid parsed metadata through the common helper**

Extend the existing `from ..naming import (...)` block with `ParsedFilename`.
Add a private helper that handles a parsed filename:

```python
def _restore_parsed_metadata(self, parsed: ParsedFilename) -> None:
    self.date_edit.setText(parsed.metadata.date)
    self.camera_edit.setText(parsed.metadata.camera)
    self._set_custom_combo_value(
        self.view_combo,
        parsed.metadata.view,
        normalize_view_token,
    )
    self._set_custom_combo_value(
        self.polarity_combo,
        parsed.polarity,
        lambda value: normalize_label_token(value, "polarity"),
    )
    self._set_custom_combo_value(
        self.lighting_combo,
        parsed.lighting,
        lambda value: normalize_label_token(value, "lighting"),
    )
```

In `import_csv`, parse every record output. For each successful result, register
its view, polarity, and lighting with `_set_custom_combo_value`; retain the first
parsed filename and call `_restore_parsed_metadata(first_parsed)` after the loop.
Keep the current `next_sequence` and table refresh behavior.

In `_load_selected_clip`, parse `record.output`. When parsing succeeds, call
`_restore_parsed_metadata(parsed)`. When parsing does not succeed, keep the
existing behavior checkbox and start/end/sequence restoration, but do not
register arbitrary empty or malformed metadata values.

- [ ] **Step 4: Run the complete test suite and verify success**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest -v
```

Expected: the complete suite passes. This covers naming, CSV, UI localization,
custom dropdown prompts, imported custom tokens, clip selection restoration, and
existing FFmpeg/export behavior.

- [ ] **Step 5: Perform a visible UI smoke test**

Run:

```powershell
Start-Process -FilePath 'D:\Python311\python.exe' -ArgumentList 'app.py' -WorkingDirectory 'C:\Users\16102\Downloads\video_labeler\.worktrees\chinese-ui-localization'
```

Expected: the Chinese application opens. Confirm that `视角`, `正负性`, and
`光照` each end with the custom action; entering a value adds it before the
action; `模式` and `播放速度` have no custom action.

- [ ] **Step 6: Commit the restore behavior**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add `
  video_labeler\ui\main_window.py `
  tests\test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m 'feat: restore custom metadata from project records'
```

## Final Verification

- [ ] Run `& 'D:\Python311\python.exe' -m pytest -v` and confirm all tests pass.
- [ ] Run `& 'C:\Program Files\Git\cmd\git.exe' diff --check` and confirm no
  whitespace errors.
- [ ] Run `& 'C:\Program Files\Git\cmd\git.exe' status --short` and confirm the
  implementation worktree is clean.
