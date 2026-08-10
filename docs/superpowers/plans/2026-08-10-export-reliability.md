# Export Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve complete annotation data and make batch FFmpeg export
cancelable, validated, and resource-safe.

**Architecture:** Extend the existing CSV layer with explicit clip fields while
retaining four-column legacy imports. Add a versioned project manifest module
for in-progress work. The FFmpeg service owns temporary outputs, process
control, and ffprobe validation; the worker owns batch scheduling; the Qt
window owns user interactions and preflight feedback.

**Tech Stack:** Python 3.11, PySide6, pytest, FFmpeg, ffprobe, standard-library
CSV, JSON, subprocess, pathlib, threading, and concurrent.futures.

## Global Constraints

- Preserve the existing annotation taxonomy and generated filename format.
- Continue to accept legacy CSV headers `source,start,end,output`.
- Treat the project as a single-source exporter and refuse mixed-source export.
- Do not treat FFmpeg zero exit status as a successful export without ffprobe
  validation.
- Use `.part.mp4` temporary outputs and remove them after failed or canceled
  jobs.
- Keep `workers=0` as an automatic setting that resolves to exactly two jobs.
- Keep existing tests passing and add focused tests for each new behavior.

---

## Planned File Structure

- Create: `video_labeler/project_io.py`
  - Defines `ProjectState`, manifest versioning, and JSON read/write validation.
- Modify: `video_labeler/naming.py`
  - Exposes label validation for CSV and manifest readers.
- Modify: `video_labeler/csv_io.py`
  - Writes explicit label/status fields and reads both extended and legacy CSV.
- Modify: `video_labeler/ffmpeg_service.py`
  - Adds ffprobe discovery, temporary output handling, process control, and
    output validation.
- Modify: `video_labeler/export_worker.py`
  - Adds single-source preflight and uses the managed FFmpeg control object.
- Modify: `video_labeler/ui/main_window.py`
  - Adds project save/open actions and passes preflight/ffprobe data into the
    export worker.
- Modify: `tests/test_naming.py`
  - Covers the public label-validation API.
- Modify: `tests/test_csv_io.py`
  - Covers extended CSV round trips and legacy compatibility.
- Create: `tests/test_project_io.py`
  - Covers manifest round trips and invalid manifests.
- Modify: `tests/test_ffmpeg_service.py`
  - Covers temporary paths, ffprobe checks, and cancel cleanup.
- Modify: `tests/test_export_worker.py`
  - Covers conservative automatic workers and mixed-source refusal.
- Modify: `tests/test_main_window.py`
  - Covers project actions and loaded project state.

---

### Task 1: Preserve Explicit Clip Data in CSV

**Files:**
- Modify: `video_labeler/naming.py:42-57`
- Modify: `video_labeler/csv_io.py:9-91`
- Modify: `tests/test_naming.py`
- Modify: `tests/test_csv_io.py`

**Interfaces:**
- Produces `validate_labels(behaviors: tuple[str, ...], polarity: str,
  lighting: str, sequence: int) -> None` from `video_labeler.naming`.
- Produces `CSV_FIELDS` containing `source`, `start`, `end`, `output`,
  `behaviors`, `polarity`, `lighting`, `sequence`, `status`, and `error`.
- `read_clip_csv(path: Path) -> list[ClipRecord]` accepts either the legacy
  required fields or the extended fields.

- [ ] **Step 1: Write failing label-validation and CSV round-trip tests**

```python
def test_validate_labels_rejects_empty_behavior_list():
    with pytest.raises(ValueError, match="at least one"):
        validate_labels((), "pos", "daytime", 1)


def test_extended_csv_round_trip_preserves_custom_output_and_labels(tmp_path):
    record = ClipRecord(
        source="cam02.mp4",
        start_seconds=2.5,
        end_seconds=4.0,
        output="manual-review-01.mp4",
        behaviors=("dog_out",),
        polarity="pos",
        lighting="daytime",
        sequence=7,
        status="fail",
        error="source missing",
    )
    path = tmp_path / "clips.csv"

    write_clip_csv(path, [record])

    assert read_clip_csv(path) == [record]
```

Add a separate test that writes the original four-column CSV fixture and
asserts it still parses labels from a standard filename and assigns
`status="queued"` with an empty error.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_naming.py tests/test_csv_io.py -v
```

Expected: FAIL because `validate_labels` is unavailable and the current CSV
writer omits explicit annotation fields.

- [ ] **Step 3: Expose label validation and implement extended CSV parsing**

```python
# video_labeler/naming.py
def validate_labels(
    behaviors: tuple[str, ...],
    polarity: str,
    lighting: str,
    sequence: int,
) -> None:
    _validate_labels(behaviors, polarity, lighting, sequence)
```

```python
# video_labeler/csv_io.py
CSV_FIELDS = (
    "source", "start", "end", "output", "behaviors", "polarity",
    "lighting", "sequence", "status", "error",
)
LEGACY_CSV_FIELDS = ("source", "start", "end", "output")


def _labels_from_row(row: dict[str, str | None], index: int, output: str):
    explicit = tuple((row.get(name) or "").strip() for name in
                     ("behaviors", "polarity", "lighting", "sequence"))
    if any(explicit):
        if not all(explicit):
            raise ValueError(f"CSV row {index} has incomplete label values")
        behaviors = tuple(explicit[0].split("+"))
        sequence = int(explicit[3])
        validate_labels(behaviors, explicit[1], explicit[2], sequence)
        return behaviors, explicit[1], explicit[2], sequence
    parsed = parse_filename(output)
    if parsed is None:
        return (), "", "", 0
    return parsed.behaviors, parsed.polarity, parsed.lighting, parsed.sequence
```

Write all ten fields in `write_clip_csv`. Require the four legacy columns, but
do not require the six added fields. Store `status` as `queued` when absent
and `error` as an empty string when absent.

- [ ] **Step 4: Run focused tests and the complete suite**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_naming.py tests/test_csv_io.py -v
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: all focused tests and all pre-existing tests pass.

- [ ] **Step 5: Commit the CSV data-contract change**

```powershell
git add video_labeler/naming.py video_labeler/csv_io.py tests/test_naming.py tests/test_csv_io.py
git commit -m "feat: preserve explicit clip data in CSV"
```

### Task 2: Add Versioned Project Manifests

**Files:**
- Create: `video_labeler/project_io.py`
- Create: `tests/test_project_io.py`

**Interfaces:**
- Produces `PROJECT_MANIFEST_VERSION = 1`.
- Produces `ProjectState(source_path: Path | None, output_dir: Path | None,
  metadata: ProjectMetadata, records: list[ClipRecord])`.
- Produces `write_project_manifest(path: Path, state: ProjectState) -> None`.
- Produces `read_project_manifest(path: Path) -> ProjectState`.

- [ ] **Step 1: Write failing manifest tests**

```python
def test_project_manifest_round_trip_preserves_paths_metadata_and_records(tmp_path):
    state = ProjectState(
        source_path=Path("C:/videos/cam02.mp4"),
        output_dir=Path("C:/clips"),
        metadata=ProjectMetadata("20260729", "cam02", "panorama"),
        records=[_record(output="manual-review-01.mp4")],
    )
    path = tmp_path / "project.json"

    write_project_manifest(path, state)

    assert read_project_manifest(path) == state


def test_read_project_manifest_rejects_unknown_version(tmp_path):
    path = tmp_path / "project.json"
    path.write_text('{"version": 99, "records": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="version"):
        read_project_manifest(path)
```

Add one malformed-record test with a non-list `behaviors` value and assert a
row-specific `ValueError`.

- [ ] **Step 2: Run the manifest tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_project_io.py -v
```

Expected: FAIL during collection because `video_labeler.project_io` does not
exist.

- [ ] **Step 3: Implement JSON serialization and validation**

```python
PROJECT_MANIFEST_VERSION = 1


@dataclass(eq=True)
class ProjectState:
    source_path: Path | None
    output_dir: Path | None
    metadata: ProjectMetadata
    records: list[ClipRecord]


def write_project_manifest(path: Path, state: ProjectState) -> None:
    payload = {
        "version": PROJECT_MANIFEST_VERSION,
        "source_path": str(state.source_path) if state.source_path else None,
        "output_dir": str(state.output_dir) if state.output_dir else None,
        "metadata": {
            "date": state.metadata.date,
            "camera": state.metadata.camera,
            "view": state.metadata.view,
        },
        "records": [_record_to_payload(record) for record in state.records],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

Implement `_record_to_payload` and `_record_from_payload`. Require the exact
manifest version, a mapping for `metadata`, a list for `records`, numeric
start/end values with `end > start`, and validated explicit labels when a
record contains labels. Convert `null` source/output paths to `None`.

- [ ] **Step 4: Run manifest and full regression tests**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_project_io.py -v
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: all manifest tests and all existing tests pass.

- [ ] **Step 5: Commit project persistence**

```powershell
git add video_labeler/project_io.py tests/test_project_io.py
git commit -m "feat: add versioned project manifests"
```

### Task 3: Validate FFmpeg Output Before Publishing It

**Files:**
- Modify: `video_labeler/ffmpeg_service.py:1-163`
- Modify: `tests/test_ffmpeg_service.py`

**Interfaces:**
- Extends `ExportRequest` with `ffprobe: str`.
- Produces `resolve_ffprobe(ffmpeg_path: str) -> str`.
- Produces `temporary_output_path(output_path: Path) -> Path`.
- Produces `validate_output_media(ffprobe: str, path: Path,
  expected_duration: float) -> None`.
- Produces `ExportControl` with `cancel() -> None`, `is_canceled() -> bool`,
  `register(process: subprocess.Popen[str]) -> None`, and
  `unregister(process: subprocess.Popen[str]) -> None`.
- Changes `run_clip_export(request: ExportRequest,
  control: ExportControl | None = None) -> ExportResult` to publish the final
  filename only after validation and to remove temporary output after
  cancellation.

- [ ] **Step 1: Write failing temporary-output and ffprobe tests**

```python
def test_temporary_output_path_keeps_mp4_extension(tmp_path):
    assert temporary_output_path(tmp_path / "clip.mp4").name == "clip.part.mp4"


def test_validate_output_media_rejects_missing_video_stream(tmp_path, monkeypatch):
    path = tmp_path / "clip.part.mp4"
    path.write_bytes(b"x" * 2048)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(
            args, 0, '{"format":{"duration":"2.0"},"streams":[]}', ""
        ),
    )

    with pytest.raises(RuntimeError, match="video stream"):
        validate_output_media("ffprobe.exe", path, 2.0)
```

Add tests for a valid video stream/duration, duration outside the tolerance,
FFmpeg success that writes the temporary file then atomically creates the final
file, and a canceled managed process that removes its `.part.mp4` output.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_ffmpeg_service.py -v
```

Expected: FAIL because temporary path and ffprobe validation APIs do not exist.

- [ ] **Step 3: Implement ffprobe resolution and validation**

```python
def temporary_output_path(output_path: Path) -> Path:
    return output_path.with_name(
        f"{output_path.stem}.part{output_path.suffix}"
    )


def validate_output_media(
    ffprobe: str, path: Path, expected_duration: float
) -> None:
    completed = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries",
            "format=duration:stream=codec_type", "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    payload = json.loads(completed.stdout)
    if not any(stream.get("codec_type") == "video"
               for stream in payload.get("streams", [])):
        raise RuntimeError("output does not contain a video stream")
    duration = float(payload["format"]["duration"])
    tolerance = max(0.25, min(2.0, expected_duration * 0.10))
    if duration <= 0 or abs(duration - expected_duration) > tolerance:
        raise RuntimeError("output duration is outside the allowed tolerance")
```

Resolve a configured sibling `ffprobe.exe` when the configured FFmpeg path is
a file; otherwise resolve `ffprobe` from `PATH`. Build FFmpeg commands with
the temporary output. On successful validation call
`temporary_path.replace(request.output_path)`. Remove the temporary file on
FFmpeg failure, validation failure, and cancellation.

```python
class ExportControl:
    def __init__(self) -> None:
        self._canceled = threading.Event()
        self._processes: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._canceled.set()
        with self._lock:
            for process in tuple(self._processes):
                if process.poll() is None:
                    process.terminate()
```

Run FFmpeg with `subprocess.Popen`, register the process before waiting, and
call `communicate(timeout=0.1)` in a loop. If cancellation is requested,
terminate, wait up to three seconds, then call `kill()` if still running.
Return `ExportResult(status="canceled")` rather than a failure for an
interrupted process.

- [ ] **Step 4: Run focused tests and the full suite**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_ffmpeg_service.py -v
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: all FFmpeg service tests and all existing tests pass.

- [ ] **Step 5: Commit verified output publishing**

```powershell
git add video_labeler/ffmpeg_service.py tests/test_ffmpeg_service.py
git commit -m "feat: validate media before publishing exports"
```

### Task 4: Make Batch Export Cancelable and Source-Safe

**Files:**
- Modify: `video_labeler/export_worker.py:1-151`
- Modify: `tests/test_export_worker.py`

**Interfaces:**
- Produces `validate_batch_source(records: Sequence[ClipRecord],
  input_path: Path) -> None`.
- `ExportWorker.cancel()` delegates to its `ExportControl`.
- `ExportWorker(..., workers=0)` uses `self._workers == 2`.

- [ ] **Step 1: Write failing cancellation, worker default, and source tests**

```python
def test_automatic_worker_count_is_two(tmp_path):
    worker = ExportWorker(
        records=[],
        input_path=tmp_path / "cam02.mp4",
        output_dir=tmp_path / "out",
        ffmpeg="ffmpeg.exe",
        ffprobe="ffprobe.exe",
        mode="encode",
        overwrite=False,
        workers=0,
    )

    assert worker._workers == 2


def test_validate_batch_source_rejects_rows_from_another_video(tmp_path):
    records = [_record(), replace(_record(), source="cam03.mp4")]

    with pytest.raises(ValueError, match="cam03.mp4"):
        validate_batch_source(records, tmp_path / "cam02.mp4")
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_export_worker.py -v
```

Expected: FAIL because `validate_batch_source` does not exist and automatic
workers use the machine CPU count.

- [ ] **Step 3: Implement managed process cancellation and source preflight**

```python
def validate_batch_source(
    records: Sequence[ClipRecord], input_path: Path
) -> None:
    expected = input_path.name.casefold()
    mismatches = sorted({
        record.source for record in records
        if Path(record.source).name.casefold() != expected
    })
    if mismatches:
        raise ValueError(
            "All clips must use the selected source video; mismatched rows: "
            + ", ".join(mismatches)
        )
```

Instantiate one control per worker, pass it to every submitted export, and
set `self._workers = workers or 2`. `ExportWorker.cancel()` calls the shared
control, which stops active exports implemented in Task 3. Preserve `canceled`
results for tasks that were never submitted.

- [ ] **Step 4: Run focused tests and full regression**

Run:

```powershell
& 'D:\Python311\python.exe' -m pytest tests/test_export_worker.py -v
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: worker cancellation integration, source validation, concurrency
default, and all existing tests pass.

- [ ] **Step 5: Commit export scheduling controls**

```powershell
git add video_labeler/export_worker.py tests/test_export_worker.py
git commit -m "feat: make batch export cancelable and source-safe"
```

### Task 5: Integrate Project Persistence and Export Preflight in the UI

**Files:**
- Modify: `video_labeler/ui/main_window.py:56-871`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- `MainWindow.save_project() -> None` writes the current `ProjectState`.
- `MainWindow.open_project() -> None` reads a manifest and calls
  `MainWindow.apply_project_state(state: ProjectState) -> None`.
- `MainWindow.project_state() -> ProjectState` creates the state to persist.
- `MainWindow.start_export()` resolves both FFmpeg and ffprobe, calls
  `validate_batch_source`, and passes `ffprobe` into `ExportWorker`.

- [ ] **Step 1: Write failing UI state and action tests**

```python
def test_project_actions_are_available(qt_app):
    window = MainWindow()

    assert window.open_project_button.text() == "Open Project"
    assert window.save_project_button.text() == "Save Project"


def test_apply_project_state_restores_annotation_data(qt_app, tmp_path):
    window = MainWindow()
    state = ProjectState(
        source_path=tmp_path / "cam02.mp4",
        output_dir=tmp_path / "out",
        metadata=ProjectMetadata("20260729", "cam02", "panorama"),
        records=[_record()],
    )

    window.apply_project_state(state)

    assert window.source_path == state.source_path
    assert window.output_dir == state.output_dir
    assert window.records == state.records
    assert window.date_edit.text() == "20260729"
```

Add a test that calls `validate_batch_source` through UI preflight with a
mismatched row and asserts the worker is not created.

- [ ] **Step 2: Run focused UI tests and verify failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& 'D:\Python311\python.exe' -m pytest tests/test_main_window.py -v
```

Expected: FAIL because project action widgets and state application APIs do
not exist.

- [ ] **Step 3: Implement project actions and preflight integration**

```python
def project_state(self) -> ProjectState:
    return ProjectState(
        source_path=self.source_path,
        output_dir=self.output_dir,
        metadata=ProjectMetadata(
            self.date_edit.text().strip(),
            self.camera_edit.text().strip(),
            self.view_combo.currentText(),
        ),
        records=list(self.records),
    )


def apply_project_state(self, state: ProjectState) -> None:
    self.source_path = state.source_path
    self.output_dir = state.output_dir
    self.records = list(state.records)
    self.date_edit.setText(state.metadata.date)
    self.camera_edit.setText(state.metadata.camera)
    self.view_combo.setCurrentText(state.metadata.view)
    self.source_name = state.source_path.name if state.source_path else ""
    self.source_label.setText(self.source_name or "No video selected")
    self.output_folder_label.setText(
        str(state.output_dir) if state.output_dir else "No output folder selected"
    )
    self._refresh_table()
```

Add `Open Project` and `Save Project` buttons to the project header and connect
them to file dialogs that call `read_project_manifest` and
`write_project_manifest`. When a loaded source path exists, set it on
`QMediaPlayer`; when it does not, retain the path and show an actionable
status message.

In `start_export`, resolve `ffprobe` immediately after resolving FFmpeg, call
`validate_batch_source(self.records, self.source_path)`, then pass
`ffprobe=ffprobe` to the worker.

- [ ] **Step 4: Run UI tests and full regression**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& 'D:\Python311\python.exe' -m pytest tests/test_main_window.py -v
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: project action/state tests, existing UI tests, and the full suite
pass.

- [ ] **Step 5: Commit UI integration**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: add project persistence and export preflight UI"
```

### Task 6: Final Integration Verification

**Files:**
- Modify only if verification exposes a defect:
  `video_labeler/naming.py`, `video_labeler/csv_io.py`,
  `video_labeler/project_io.py`, `video_labeler/ffmpeg_service.py`,
  `video_labeler/export_worker.py`, `video_labeler/ui/main_window.py`, or
  their associated test files.

**Interfaces:**
- The public application entry point remains `app.py`.
- No test or production import references an undefined interface from Tasks
  1-5.

- [ ] **Step 1: Run the complete test suite from a clean process**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
& 'D:\Python311\python.exe' -m pytest -q
```

Expected: all tests pass with no Qt platform errors.

- [ ] **Step 2: Inspect the final diff and working tree**

Run:

```powershell
git diff --check HEAD~5..HEAD
git status --short
git log --oneline -6
```

Expected: no whitespace errors, no uncommitted generated artifacts, and one
commit for each implementation task plus the design/plan commits.

- [ ] **Step 3: Commit only an integration fix if required**

```powershell
git add video_labeler/naming.py video_labeler/csv_io.py video_labeler/project_io.py video_labeler/ffmpeg_service.py video_labeler/export_worker.py video_labeler/ui/main_window.py tests/test_naming.py tests/test_csv_io.py tests/test_project_io.py tests/test_ffmpeg_service.py tests/test_export_worker.py tests/test_main_window.py
git commit -m "fix: complete export reliability integration"
```

Only perform this step when Steps 1 or 2 require a code correction. Otherwise
leave the history at the five task commits.

## Plan Self-Review

### Spec Coverage

- Project manifest persistence: Task 2 and Task 5.
- Legacy and extended CSV round trips: Task 1.
- Single-source preflight: Task 4 and Task 5.
- Temporary output, ffprobe stream/duration validation, and atomic publish:
  Task 3.
- Managed cancellation and cleanup: Task 4.
- Conservative automatic concurrency: Task 4.
- Error reporting and full regression: Tasks 3-6.

### Placeholder Scan

The plan contains no unresolved placeholders, deferred implementation markers,
or unnamed interfaces. The final integration task names the exact condition
under which its optional commit is allowed.

### Type Consistency

`ProjectState`, `validate_labels`, `ExportControl`, `validate_batch_source`,
`resolve_ffprobe`, and `ExportRequest.ffprobe` are each introduced before
their consuming UI task. `ClipRecord` remains the shared record type across
CSV, manifests, worker scheduling, and UI state.
