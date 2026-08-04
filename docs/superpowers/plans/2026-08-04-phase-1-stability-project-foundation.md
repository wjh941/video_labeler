# Phase 1 Stability and Project Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the current Qt presentation defects and add local multi-video
`.labelproj` persistence, automatic backups, undo/redo, and the finalized
shortcut mapping without changing the verified CSV or FFmpeg workflows.

**Architecture:** Keep `MainWindow.records` as the active video's mutable
`list[ClipRecord]`. Add focused persistence and history modules, then make
`MainWindow` bind that existing list to the selected `ProjectVideo`. Existing
CSV and immediate FFmpeg methods keep consuming `self.records`,
`self.source_path`, and `self.output_dir` unchanged.

**Tech Stack:** Python 3.11, PySide6 6.7, pytest 8, JSON, Windows Qt runtime.

## Global Constraints

- Base branch is `feature/video-segment-labeler-zh`.
- Do not run `git push`, branch merge, rebase, or pull-request commands.
- All commits remain local pending manual acceptance.
- Do not implement Phase 2 timeline/waveform, Phase 3 reporting/batch export,
  or Phase 4 packaging features.
- Preserve the existing English label constants, CSV headers/content, output
  filename rules, and FFmpeg command/export behavior.
- Preserve the accepted next-clip reset rule: start/end equal saved end,
  behavior checkboxes clear, while lighting, polarity, and view remain.
- Keep `self.records` as the active video's segment list.
- All new widgets and dialogs use the globally applied `light_fresh.qss`
  theme. Do not add inline `setStyleSheet` calls in `main_window.py`.
- Use `D:\Python311\python.exe -m pytest` for all test commands.

---

## File Structure

- Create: `video_labeler/project_io.py`
  - Defines `LabelProject`, `ProjectVideo`, JSON validation, atomic
    save/load, and automatic backup helpers.
- Create: `video_labeler/history.py`
  - Defines immutable active-video segment history entries and the undo/redo
    cursor API. History is UI-session state and is not serialized.
- Create: `tests/test_project_io.py`
  - Covers document round trips, invalid documents, backup retention, and
    missing video-path preservation.
- Create: `tests/test_history.py`
  - Covers push, undo, redo, and redo-branch invalidation.
- Create: `tests/test_app.py`
  - Covers Qt runtime configuration before application creation.
- Modify: `app.py`
  - Calls one testable pre-`QApplication` runtime configuration function.
- Modify: `video_labeler/themes/light_fresh.qss`
  - Keeps dialog chrome light without a conflicting forced file-list
    background; styles new project and history controls.
- Modify: `tests/test_themes.py`
  - Covers the file-dialog exemption and semantic button selectors.
- Modify: `video_labeler/ui/main_window.py`
  - Owns project menu/UI wiring, active video selection, dirty state,
    debounce scheduling, project commands, history controls, finalized
    shortcuts, and responsive checkbox reflow.
- Modify: `tests/test_main_window.py`
  - Replaces obsolete shortcut expectations and adds UI-level project,
    history, layout, and compatibility regression tests.

## Interfaces

```python
# video_labeler/project_io.py
PROJECT_VERSION: int = 1

@dataclass
class ProjectVideo:
    id: str
    path: Path
    segments: list[ClipRecord]

@dataclass
class LabelProject:
    videos: list[ProjectVideo]
    active_video_id: str | None = None
    global_settings: dict[str, str] = field(default_factory=dict)

def new_project() -> LabelProject: ...
def add_or_activate_video(project: LabelProject, path: Path) -> ProjectVideo: ...
def active_video(project: LabelProject) -> ProjectVideo | None: ...
def activate_video(project: LabelProject, video_id: str) -> ProjectVideo: ...
def project_to_dict(project: LabelProject) -> dict[str, object]: ...
def project_from_dict(payload: object) -> LabelProject: ...
def save_project(path: Path, project: LabelProject) -> None: ...
def load_project(path: Path) -> LabelProject: ...
def create_backup(
    project_path: Path,
    project: LabelProject,
    *,
    now: datetime | None = None,
    retention: int = 10,
) -> Path: ...
```

```python
# video_labeler/history.py
@dataclass(frozen=True)
class SegmentHistoryEntry:
    before: tuple[ClipRecord, ...]
    after: tuple[ClipRecord, ...]

class SegmentHistory:
    def push(
        self,
        before: Sequence[ClipRecord],
        after: Sequence[ClipRecord],
    ) -> None: ...
    def can_undo(self) -> bool: ...
    def can_redo(self) -> bool: ...
    def undo(self, current: Sequence[ClipRecord]) -> list[ClipRecord]: ...
    def redo(self, current: Sequence[ClipRecord]) -> list[ClipRecord]: ...
```

```python
# MainWindow additions
def save_project(self) -> None: ...
def new_project(self) -> None: ...
def open_project(self) -> None: ...
def restore_project_from_backup(self) -> None: ...
def switch_active_video(self, video_id: str) -> None: ...
def undo_segments(self) -> None: ...
def redo_segments(self) -> None: ...
def _mark_project_dirty(self) -> None: ...
def _schedule_project_backup(self) -> None: ...
def _write_automatic_backup(self) -> None: ...
def _step_frame(self, direction: int) -> None: ...
```

### Task 1: Fix Qt Runtime Configuration and File-Dialog Styling

**Files:**
- Create: `tests/test_app.py`
- Modify: `app.py`
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `tests/test_themes.py`
- Test: `tests/test_app.py`, `tests/test_themes.py`,
  `tests/test_main_window.py`

**Consumes:** Existing `apply_light_fresh_theme(QApplication)`.

**Produces:** `configure_qt_runtime()` is called before `QApplication` and
the theme has safe non-native `QFileDialog` styling.

- [ ] **Step 1: Write failing runtime and theme tests**

```python
# tests/test_app.py
def test_configure_qt_runtime_sets_software_rendering_before_application(
    monkeypatch,
):
    import app

    attributes = []
    monkeypatch.setattr(
        app.QApplication,
        "setAttribute",
        staticmethod(lambda attribute, enabled=True: attributes.append((attribute, enabled))),
    )
    monkeypatch.delenv("QT_OPENGL", raising=False)
    monkeypatch.delenv("QT_ENABLE_HIGHDPI_SCALING", raising=False)

    app.configure_qt_runtime()

    assert os.environ["QT_OPENGL"] == "software"
    assert os.environ["QT_ENABLE_HIGHDPI_SCALING"] == "1"
    assert any(enabled for _attribute, enabled in attributes)
```

```python
# tests/test_themes.py
def test_light_theme_keeps_file_dialog_browser_views_unforced():
    stylesheet = load_light_fresh_theme()

    assert "QFileDialog QListView" not in stylesheet
    assert "QFileDialog QTreeView" not in stylesheet
    assert "QFileDialog {" in stylesheet
    assert "QFileDialog QLineEdit" in stylesheet
```

- [ ] **Step 2: Run the targeted tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_app.py tests/test_themes.py -v
```

Expected: FAIL because `configure_qt_runtime` and safe file-dialog selectors
do not exist.

- [ ] **Step 3: Implement pre-application runtime configuration**

```python
# app.py
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

def configure_qt_runtime() -> None:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_OPENGL", "software")
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True
    )
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True
    )
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

def main() -> int:
    configure_qt_runtime()
    application = QApplication(sys.argv)
    ...
```

Guard unavailable Qt application attributes with `hasattr` so the program
remains compatible across supported PySide6 point releases. Do not construct
an application inside `configure_qt_runtime`.

- [ ] **Step 4: Make file-dialog QSS safe**

Remove any selector that targets `QFileDialog QListView` or
`QFileDialog QTreeView`. Retain the existing dialog shell rule and add only
the following safe controls:

```css
QFileDialog QLineEdit,
QFileDialog QPushButton,
QFileDialog QComboBox {
    background: #FFFFFF;
    color: #303133;
}
```

Add semantic selectors for `#undoButton`, `#redoButton`, and
`#projectVideoCombo` using the existing rounded light palette. Disabled
buttons must use the existing `QPushButton:disabled` rule.

- [ ] **Step 5: Run targeted tests and current file-dialog regression**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_app.py tests/test_themes.py tests/test_main_window.py::test_file_dialogs_request_non_native_windows -v
```

Expected: PASS.

- [ ] **Step 6: Commit the completed UI-runtime task locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add app.py video_labeler/themes/light_fresh.qss tests/test_app.py tests/test_themes.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "fix: stabilize Qt dialogs and rendering"
```

### Task 2: Implement Project Document Serialization and Automatic Backups

**Files:**
- Create: `video_labeler/project_io.py`
- Create: `tests/test_project_io.py`
- Test: `tests/test_project_io.py`

**Consumes:** `ClipRecord` from `video_labeler.models`.

**Produces:** Validated `.labelproj` save/load and bounded backup files,
independent from Qt widgets.

- [ ] **Step 1: Write failing document and backup tests**

```python
# tests/test_project_io.py
def test_project_round_trip_preserves_absolute_paths_segments_and_settings(
    tmp_path,
):
    project_path = tmp_path / "shift.labelproj"
    source = (tmp_path / "camera.mp4").resolve()
    project = new_project()
    entry = add_or_activate_video(project, source)
    entry.segments.append(
        ClipRecord(
            source=source.name,
            start_seconds=1.25,
            end_seconds=3.5,
            output="20260729-cam02_indoor-dog_out-pos-daytime-001.mp4",
            behaviors=("dog_out",),
            polarity="pos",
            lighting="daytime",
            sequence=1,
        )
    )
    project.global_settings = {"date": "20260729", "camera": "cam02"}

    save_project(project_path, project)
    loaded = load_project(project_path)

    assert loaded.active_video_id == entry.id
    assert loaded.videos[0].path == source
    assert loaded.videos[0].segments == entry.segments
    assert loaded.global_settings == project.global_settings
```

```python
def test_create_backup_keeps_ten_newest_files(tmp_path):
    project_path = tmp_path / "shift.labelproj"
    project = new_project()
    save_project(project_path, project)

    for second in range(12):
        create_backup(
            project_path,
            project,
            now=datetime(2026, 8, 4, 10, 0, second),
        )

    backups = sorted((tmp_path / ".backups").glob("shift_*.labelproj"))
    assert len(backups) == 10
    assert backups[0].name == "shift_20260804-100002.labelproj"
```

```python
def test_project_loader_rejects_invalid_version_but_keeps_missing_paths(
    tmp_path,
):
    invalid_path = tmp_path / "invalid.labelproj"
    invalid_path.write_text('{"version": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_project(invalid_path)

    missing = (tmp_path / "missing.mp4").resolve()
    project = project_from_dict(
        {
            "version": 1,
            "active_video_id": "video-1",
            "global_settings": {},
            "videos": [{"id": "video-1", "path": str(missing), "segments": []}],
        }
    )
    assert project.videos[0].path == missing
    assert not project.videos[0].path.exists()
```

- [ ] **Step 2: Run the project persistence tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_project_io.py -v
```

Expected: FAIL because `video_labeler.project_io` does not exist.

- [ ] **Step 3: Implement project dataclasses and strict JSON conversion**

```python
# video_labeler/project_io.py
PROJECT_VERSION = 1

@dataclass
class ProjectVideo:
    id: str
    path: Path
    segments: list[ClipRecord] = field(default_factory=list)

@dataclass
class LabelProject:
    videos: list[ProjectVideo] = field(default_factory=list)
    active_video_id: str | None = None
    global_settings: dict[str, str] = field(default_factory=dict)

def new_project() -> LabelProject:
    return LabelProject()

def add_or_activate_video(project: LabelProject, path: Path) -> ProjectVideo:
    absolute_path = path.expanduser().resolve(strict=False)
    for video in project.videos:
        if video.path == absolute_path:
            project.active_video_id = video.id
            return video
    video = ProjectVideo(id=str(uuid4()), path=absolute_path)
    project.videos.append(video)
    project.active_video_id = video.id
    return video
```

Serialize every `ClipRecord` field explicitly. Reject documents whose root is
not an object, whose version differs from `PROJECT_VERSION`, whose video IDs
are empty or duplicated, whose active ID is not present, or whose segment
records do not contain valid primitive field values. Do not require the video
path to exist during loading.

- [ ] **Step 4: Implement atomic save and bounded backup helper**

```python
def save_project(path: Path, project: LabelProject) -> None:
    target = path.with_suffix(".labelproj")
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(project_to_dict(project), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)

def create_backup(
    project_path: Path,
    project: LabelProject,
    *,
    now: datetime | None = None,
    retention: int = 10,
) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup_dir = project_path.parent / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{project_path.stem}_{timestamp}.labelproj"
    save_project(backup_path, project)
    _keep_newest_backups(backup_dir, project_path.stem, retention)
    return backup_path
```

Use the Windows hidden-directory attribute best-effort after `mkdir`; failure
must not make backup creation fail. Ensure the helper preserves the requested
backup filename instead of appending a second `.labelproj` suffix.

- [ ] **Step 5: Run project persistence tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_project_io.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the completed persistence task locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/project_io.py tests/test_project_io.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: add label project persistence"
```

### Task 3: Implement Per-Video Segment Undo/Redo History

**Files:**
- Create: `video_labeler/history.py`
- Create: `tests/test_history.py`
- Test: `tests/test_history.py`

**Consumes:** `ClipRecord`.

**Produces:** A session-only history object that restores copied segment lists
without exposing mutable saved snapshots.

- [ ] **Step 1: Write failing history tests**

```python
# tests/test_history.py
def test_undo_and_redo_restore_independent_segment_snapshots():
    history = SegmentHistory()
    before = [_record(1)]
    after = [_record(1), _record(2)]

    history.push(before, after)

    assert history.can_undo()
    assert history.undo(after) == before
    assert history.can_redo()
    assert history.redo(before) == after

def test_new_change_after_undo_discards_redo_branch():
    history = SegmentHistory()
    original = [_record(1)]
    added = [_record(1), _record(2)]
    replacement = [_record(3)]
    history.push(original, added)
    assert history.undo(added) == original
    history.push(original, replacement)

    assert not history.can_redo()
    assert history.undo(replacement) == original
```

- [ ] **Step 2: Run the history test to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_history.py -v
```

Expected: FAIL because `video_labeler.history` does not exist.

- [ ] **Step 3: Implement copy-safe cursor history**

```python
# video_labeler/history.py
def _snapshot(records: Sequence[ClipRecord]) -> tuple[ClipRecord, ...]:
    return tuple(replace(record) for record in records)

class SegmentHistory:
    def __init__(self) -> None:
        self._entries: list[SegmentHistoryEntry] = []
        self._cursor = 0

    def push(self, before, after) -> None:
        if tuple(before) == tuple(after):
            return
        del self._entries[self._cursor :]
        self._entries.append(
            SegmentHistoryEntry(_snapshot(before), _snapshot(after))
        )
        self._cursor = len(self._entries)

    def undo(self, current) -> list[ClipRecord]:
        if not self.can_undo():
            return [replace(record) for record in current]
        self._cursor -= 1
        return [replace(record) for record in self._entries[self._cursor].before]
```

Implement `redo()` symmetrically. `current` remains in the public method
signature so the UI can call undo/redo safely even when no history exists.

- [ ] **Step 4: Run the history tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_history.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the completed history task locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/history.py tests/test_history.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: add segment undo redo history"
```

### Task 4: Bind MainWindow to a Multi-Video Label Project

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Modify: `tests/test_main_window.py`
- Test: `tests/test_main_window.py`, `tests/test_csv_io.py`,
  `tests/test_export_worker.py`, `tests/test_ffmpeg_service.py`

**Consumes:** `LabelProject`, `ProjectVideo`, and persistence helpers from
Task 2; existing `self.records` methods.

**Produces:** New/Open/Save/Restore commands, active-video selector, dirty
state, backup debounce, and active list binding.

- [ ] **Step 1: Write failing UI-level project tests**

```python
# tests/test_main_window.py
def _clip_record(source: str, sequence: int) -> ClipRecord:
    return ClipRecord(
        source=source,
        start_seconds=float(sequence),
        end_seconds=float(sequence + 1),
        output=(
            f"20260729-cam02_indoor-dog_out-pos-daytime-{sequence:03d}.mp4"
        ),
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=sequence,
    )

def test_switching_project_video_rebinds_records_without_cross_video_leakage(
    qt_app, tmp_path
):
    window = MainWindow()
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"

    window.set_source_path(first)
    window.records.append(_clip_record(first.name, 1))
    window.set_source_path(second)
    window.records.append(_clip_record(second.name, 2))
    window.switch_active_video(window.project.videos[0].id)

    assert window.records[0].source == first.name
    assert len(window.records) == 1
    assert len(window.project.videos[1].segments) == 1
    assert window.project_video_combo.currentData() == window.project.videos[0].id

def test_project_save_open_and_restore_backup_keep_active_video_segments(
    qt_app, tmp_path, monkeypatch
):
    project_path = tmp_path / "work.labelproj"
    window = MainWindow()
    window.set_source_path(tmp_path / "camera.mp4")
    window.records.append(_clip_record("camera.mp4", 1))
    window._project_path = project_path
    window._mark_project_dirty()
    window.save_project()
    window._write_automatic_backup()

    restored = MainWindow()
    restored._load_project_path(project_path)
    assert restored.records == window.records
    assert list((tmp_path / ".backups").glob("work_*.labelproj"))
```

```python
def test_annotation_change_starts_or_resets_backup_debounce(qt_app, tmp_path):
    window = MainWindow()
    window._project_path = tmp_path / "work.labelproj"
    window._mark_project_dirty()

    assert window._project_dirty
    assert window._backup_timer.isActive()
    assert window._backup_timer.interval() == 30_000
```

- [ ] **Step 2: Run UI project tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "project or backup or switching" -v
```

Expected: FAIL because no project state, selector, or backup timer exists.

- [ ] **Step 3: Add project menu, active-video selector, and initialization**

In `MainWindow.__init__`, create these state fields before `_build_ui()`:

```python
self.project = new_project()
self._project_path: Path | None = None
self._project_dirty = False
self._active_video_histories: dict[str, SegmentHistory] = {}
self._backup_timer = QTimer(self)
self._backup_timer.setSingleShot(True)
self._backup_timer.setInterval(30_000)
self._backup_timer.timeout.connect(self._write_automatic_backup)
```

Create a `工程` menu with `新建工程`, `打开工程`, `保存工程`,
`从备份文件恢复工程`. Add `self.project_video_combo` beside the source label;
its item data is the `ProjectVideo.id`. Add the combo and menu actions to the
same signal-registration path as existing controls.

- [ ] **Step 4: Implement active list binding and source loading**

```python
def set_source_path(self, path: Path) -> None:
    entry = add_or_activate_video(self.project, path)
    self._bind_active_video(entry)
    self._mark_project_dirty()

def _bind_active_video(self, entry: ProjectVideo) -> None:
    self.project.active_video_id = entry.id
    self.records = entry.segments
    self.source_path = entry.path
    self.source_name = entry.path.name
    self.source_label.setText(entry.path.name)
    self._sync_project_video_combo()
    self._refresh_table()
```

`switch_active_video()` resolves the selected entry, calls
`_bind_active_video()`, clears the editing selection, and sets
`QMediaPlayer` source only when the path exists. It must not mark a project
dirty merely for switching views.

Change `open_video()` only so the existing picker's selected path is registered
through `set_source_path()` before it is supplied to `QMediaPlayer`. It must
not change the non-native picker, CSV export, or FFmpeg export configuration.

- [ ] **Step 5: Implement project command and backup methods**

```python
def _mark_project_dirty(self) -> None:
    self._project_dirty = True
    self._schedule_project_backup()

def _schedule_project_backup(self) -> None:
    if self._project_path is not None:
        self._backup_timer.start()

def _write_automatic_backup(self) -> None:
    if self._project_path is None:
        return
    try:
        create_backup(self._project_path, self._project_snapshot())
    except OSError as error:
        self._set_status(f"自动备份失败：{error}")
```

`save_project()` must open a non-native save picker only when
`self._project_path` is `None`, update global settings before save, call
`project_io.save_project()`, and clear `_project_dirty` only after a
successful write. `open_project()` and `restore_project_from_backup()` use
the same non-native open picker and `_load_project_path()` helper. Before
discarding a dirty project, use a Chinese `QMessageBox` confirmation.

`_project_snapshot()` copies the active UI settings (`date`, `camera`, `view`,
and output folder) into `project.global_settings` and returns the project.
`_load_project_path()` applies those settings only when present, resets
per-video history, selects the saved active video, and leaves missing sources
unplayed.

Override `closeEvent()` to confirm if dirty, accept only after user approval,
and otherwise ignore the close event.

- [ ] **Step 6: Mark all annotation mutations dirty without changing behavior**

After a successful add/update, delete, batch edit, CSV import replacement, or
table output-name edit, call `_mark_project_dirty()`. Do not move
`_prepare_next_clip(record.end_seconds)` or alter its field resets. Do not
schedule a backup for selection, filter, sort, playback, or video switching.

- [ ] **Step 7: Run project and compatibility regressions**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "project or backup or switching or add_clip or update_clip or selecting_clip" -v
D:\Python311\python.exe -m pytest tests/test_csv_io.py tests/test_export_worker.py tests/test_ffmpeg_service.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit the completed MainWindow project integration locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: add multi-video label projects"
```

### Task 5: Wire Undo/Redo Controls and Finalized Shortcuts

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Modify: `tests/test_main_window.py`
- Test: `tests/test_main_window.py`

**Consumes:** `SegmentHistory` from Task 3 and active-video bindings from
Task 4.

**Produces:** Active-video history buttons, correct enabled states, final
shortcut map, and Chinese help text.

- [ ] **Step 1: Write failing undo/redo and shortcut tests**

```python
# tests/test_main_window.py
def _add_valid_clip(
    window: MainWindow, *, start: float, end: float, behavior: str
) -> None:
    window.date_edit.setText("20260729")
    window.camera_edit.setText("cam02")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("pos")
    window.lighting_combo.setCurrentText("daytime")
    window.set_clip_range(start, end)
    window.behavior_checks[behavior].setChecked(True)
    window.add_or_update_clip()

def test_undo_redo_restore_added_updated_and_deleted_segments(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")
    _add_valid_clip(window, start=3, end=4, behavior="fall")

    window.task_table.selectRow(1)
    window.remove_selected_clip()
    assert len(window.records) == 1
    assert window.undo_button.isEnabled()

    window.undo_segments()
    assert [record.sequence for record in window.records] == [1, 2]
    assert window.redo_button.isEnabled()

    window.redo_segments()
    assert [record.sequence for record in window.records] == [1]

def test_main_window_shortcut_mapping(qt_app):
    window = MainWindow()
    expected = {
        "play_pause": "Space",
        "previous_frame": "A",
        "next_frame": "D",
        "set_start": "S",
        "set_end": "E",
        "delete_selected": "Del",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "save_project": "Ctrl+S",
    }
    assert set(window.shortcuts) == set(expected)
    assert all(
        window.shortcuts[name].key() == QKeySequence(sequence)
        for name, sequence in expected.items()
    )
```

```python
def test_undo_does_not_change_verified_next_clip_reset_fields(qt_app, tmp_path):
    window = MainWindow()
    window.set_source_path(tmp_path / "source.mp4")
    window.view_combo.setCurrentText("indoor")
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    _add_valid_clip(window, start=1, end=2, behavior="dog_out")

    window.undo_segments()

    assert window.selected_behaviors() == ()
    assert window.start_spin.value() == pytest.approx(2)
    assert window.end_spin.value() == pytest.approx(2)
    assert window.view_combo.currentText() == "indoor"
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
```

- [ ] **Step 2: Run the targeted tests to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "undo or redo or shortcut_mapping" -v
```

Expected: FAIL because the current shortcuts and controls use the obsolete
mapping and history is not wired into mutations.

- [ ] **Step 3: Capture before/after snapshots around add, update, and delete**

In `add_or_update_clip()`, snapshot `self.records` before mutation, preserve
the existing validation and post-save `_prepare_next_clip()` call, then push
the post-mutation snapshot to the history object for the active video:

```python
before = list(self.records)
# existing append or replacement
self._active_history().push(before, self.records)
self._mark_project_dirty()
self._refresh_table()
self._prepare_next_clip(record.end_seconds)
self._update_history_controls()
```

In `_delete_selected_records()`, snapshot before deleting, retain the existing
confirmation and selection reset, then push only after at least one record
was deleted. Do not add batch-edit history because Phase 1 only promises
create/update/delete history.

- [ ] **Step 4: Implement history application and controls**

```python
def undo_segments(self) -> None:
    history = self._active_history()
    if not history.can_undo():
        return
    self.records[:] = history.undo(self.records)
    self._editing_index = None
    self.task_table.clearSelection()
    self._refresh_table()
    self._mark_project_dirty()
    self._update_history_controls()

def redo_segments(self) -> None:
    history = self._active_history()
    if not history.can_redo():
        return
    self.records[:] = history.redo(self.records)
    self._editing_index = None
    self.task_table.clearSelection()
    self._refresh_table()
    self._mark_project_dirty()
    self._update_history_controls()
```

Use slice assignment so the `ProjectVideo.segments` list retains object
identity. Add `撤销` and `重做` `QPushButton`s with object names
`undoButton` and `redoButton`; set their enabled state in
`_update_history_controls()` and after every active-video switch.

- [ ] **Step 5: Replace global shortcuts and help text**

Replace `SHORTCUT_HELP_ROWS`, `shortcut_hint_label`, and `_register_shortcuts`
with only the finalized mappings:

```python
bindings = {
    "play_pause": ("Space", self.toggle_playback),
    "previous_frame": ("A", lambda: self._step_frame(-1)),
    "next_frame": ("D", lambda: self._step_frame(1)),
    "set_start": ("S", self._set_start_from_player),
    "set_end": ("E", self._set_end_from_player),
    "delete_selected": ("Del", self.remove_selected_clip),
    "undo": ("Ctrl+Z", self.undo_segments),
    "redo": ("Ctrl+Y", self.redo_segments),
    "save_project": ("Ctrl+S", self.save_project),
}
```

Implement `_step_frame(direction)` as a 33 ms bounded position adjustment.
Keep the existing on-screen 5-second buttons; only their old global keyboard
bindings are removed.

- [ ] **Step 6: Run undo/redo, shortcut, and post-save regression tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "undo or redo or shortcut or add_clip_prepares or update_clip_prepares" -v
```

Expected: PASS.

- [ ] **Step 7: Commit the completed history UI task locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: add project shortcuts and undo redo"
```

### Task 6: Reflow Behavior Tags Without Clipping and Run Full Regression

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Modify: `tests/test_main_window.py`
- Test: `tests/test_main_window.py`, `tests/test_themes.py`, full `tests`

**Consumes:** Existing `CollapsibleGroupBox` animation and current
checkbox dictionary.

**Produces:** No scrollbar in behavior content, responsive whole-column
layout, and completed Phase 1 regression coverage.

- [ ] **Step 1: Write failing responsive layout tests**

```python
# tests/test_main_window.py
def test_behavior_checks_reflow_to_available_width_without_text_clipping(
    qt_app,
):
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    qt_app.processEvents()

    assert not window.behaviors_group.findChildren(QScrollArea)
    assert window.behavior_columns >= 3
    assert all(
        checkbox.sizeHint().width() <= window.behavior_checks_container.width()
        for checkbox in window.behavior_checks.values()
    )

    window.resize(1120, 720)
    qt_app.processEvents()
    assert window.behavior_columns >= 2
```

```python
def test_collapsible_behavior_group_recalculates_expanded_height_after_reflow(
    qt_app,
):
    window = MainWindow()
    window.show()
    window.resize(1440, 900)
    qt_app.processEvents()

    assert window.behavior_checks_container.height() >= (
        window.behavior_checks_container.sizeHint().height()
    )
```

- [ ] **Step 2: Run the layout tests to verify failure or expose current clipping**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "tag_area_no_scrollbar or behavior_checks_reflow or collapsible_behavior_group_recalculates" -v
```

Expected: the new tests fail until reflow is based on actual container width
and the animation target is refreshed.

- [ ] **Step 3: Implement container-width reflow and geometry refresh**

```python
def _reflow_behavior_checks(self) -> None:
    available = max(
        self.behavior_checks_container.width(),
        self.behavior_checks_container.sizeHint().width(),
    )
    minimum_column_width = max(
        checkbox.sizeHint().width()
        for checkbox in self.behavior_checks.values()
    ) + 16
    columns = max(2, min(4, available // minimum_column_width))
    self.behavior_columns = columns
    # remove all current layout items, then add each checkbox by divmod.
    for column in range(columns):
        self.behavior_checks_layout.setColumnStretch(column, 1)
    self.behavior_checks_container.updateGeometry()
    self.behaviors_group.updateGeometry()
```

Call reflow from `resizeEvent()` through a zero-delay single-shot timer so
Qt has assigned the splitter width first. Keep the current
`CollapsibleGroupBox.set_content()` call and animation duration unchanged.
When expanded, reset its content maximum height to unrestricted after the
reflow. Never introduce a scroll area around behavior checkboxes.

- [ ] **Step 4: Verify component and regression tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py tests/test_themes.py -v
D:\Python311\python.exe -m pytest tests -v
```

Expected: all tests PASS. Record the exact passed-test count in the final
delivery note.

- [ ] **Step 5: Perform a manual smoke check without adding Phase 2-4 work**

Run:

```powershell
D:\Python311\python.exe app.py
```

Verify manually:

1. File picker directory and file list render normally.
2. Behavior tags are fully readable when expanded and collapse smoothly.
3. Create a project, add two videos, switch between them, and save/open it.
4. Add, update, delete, undo, and redo a segment.
5. Wait 30 seconds after a segment change and confirm one timestamped backup.
6. Confirm the existing `保存标注 CSV` button and single-video export controls
   still operate from the active video.

- [ ] **Step 6: Commit the final Phase 1 layout and test changes locally**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "fix: complete phase 1 project foundation"
& 'C:\Program Files\Git\cmd\git.exe' status --short --branch
```

Do not run any remote Git command after the commit.

## Plan Self-Review

| Specification requirement | Plan task |
| --- | --- |
| QFileDialog black screen and light controls | Task 1 |
| High-DPI and software rendering startup configuration | Task 1 |
| Responsive collapse tag layout and usable buttons | Tasks 1 and 6 |
| Multi-video `.labelproj` structure and active `self.records` binding | Tasks 2 and 4 |
| New/open/save/restore, dirty confirmation, and 30-second backups | Tasks 2 and 4 |
| Backup naming, retention, hidden directory, and write failure behavior | Task 2 and Task 4 |
| Segment create/update/delete undo and redo | Tasks 3 and 5 |
| Final shortcut map, help dialog, and disabled history controls | Task 5 |
| Preserve post-save fields, CSV, and FFmpeg workflows | Tasks 4, 5, and 6 regression runs |
| Do not implement later phases or remote Git operations | Global constraints and every task |

The plan has no unfinished placeholders. All named interfaces are defined
before their consuming task, and no Task 2-6 step requires a Phase 2, 3, or 4
module.
