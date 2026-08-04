# Card Workspace UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved video-first card workspace, a detachable task table, and working preset-plus-custom playback-rate controls while preserving every validated annotation and export workflow.

**Architecture:** Keep `MainWindow` as the UI owner. The existing `speed_combo` remains the preset selector and gains a `custom_speed_spin`; all UI paths call one playback-rate method. The existing `task_panel` and `task_table` are moved between `workspace_splitter` and one modeless `QDialog`, so selection and data signals never duplicate. Card geometry and colors stay in `light_fresh.qss`; a small presentation helper only attaches `QGraphicsDropShadowEffect` instances.

**Tech Stack:** Python 3.11, PySide6, Qt Style Sheets, pytest, Git for local commits and final branch push.

## Global Constraints

- Do not alter verified new-segment refresh behavior, `self.records`, active-video switching, annotation editing, CSV data, filenames, project persistence, FFmpeg command construction, or export-worker behavior.
- Keep the current `QGraphicsView` and `QGraphicsVideoItem` video output. Playback controls must remain below the preview surface.
- Keep `task_table` as the sole table object and retain all existing filters, sorting, batch operations, edit signals, and selection model.
- Keep `speed_combo` as a public `QComboBox` attribute for existing callers and tests.
- Add no inline `setStyleSheet()` calls to `video_labeler/ui/main_window.py`; write card styles only in `video_labeler/themes/light_fresh.qss`.
- The table is embedded by default. It opens in a modeless dialog only after the user presses `弹出表格`; closing the dialog returns the same widget to `workspace_splitter` index 1.
- The custom playback range is exactly `0.1` through `4.0`; invalid values restore the previous valid rate and show a Chinese status message.
- Do not merge, rebase, or create a pull request. After all verification and authorized cleanup, commit the approved local work and push only `feature/video-segment-labeler-zh` to `origin`.
- Cleanup is restricted to `%TEMP%`, `C:\Users\16102\AppData\Local\Temp`, project test/screenshot artifacts, and the recycle bin. Exclude Windows, Program Files, source/Git files, Downloads, browser profiles, and user documents.

---

### Task 0: Commit The Verified Video-First Layout Baseline

**Files:**
- Modify: `video_labeler/ui/main_window.py`
- Modify: `video_labeler/themes/light_fresh.qss`
- Modify: `tests/test_main_window.py`
- Create: `docs/superpowers/plans/2026-08-04-video-first-scroll-layout.md`

**Interfaces:**
- Preserves: current `main_content_scroll`, `workspace_content`, `task_panel`,
  `video_controls_panel`, and `QGraphicsVideoItem` output.
- Produces: a clean baseline commit so later commits contain only this plan's
  playback-rate, detachable-table, and card-style changes.

- [ ] **Step 1: Verify the existing video-first baseline**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "video_first_workspace or video_preview or video_progress or behavior_checks_splitter_reflow" -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Inspect the baseline diff before staging**

Run:

```powershell
git status --short
git diff --check
git diff -- video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_main_window.py docs/superpowers/plans/2026-08-04-video-first-scroll-layout.md
```

Expected: only the verified video-first layout, file-dialog contrast, and
behavior-tag reflow test support changes are staged. The local
`.superpowers/brainstorm/` visual-design artifacts and this plan remain
untracked at this point and must not be staged.

- [ ] **Step 3: Commit the verified baseline locally**

Run:

```powershell
git add video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_main_window.py docs/superpowers/plans/2026-08-04-video-first-scroll-layout.md
git commit -m "fix: improve video-first workspace controls"
```

### Task 1: Add Preset And Custom Playback-Rate Controls

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `video_labeler/ui/main_window.py:409-487, 895-905, 1529-1535`

**Interfaces:**
- Preserves: `MainWindow.speed_combo: QComboBox`
- Produces: `MainWindow.custom_speed_spin: QDoubleSpinBox`
- Produces: `MainWindow._apply_playback_rate(rate: float) -> bool`
- Produces: `MainWindow._on_speed_preset_changed() -> None`
- Produces: `MainWindow._on_custom_speed_committed() -> None`
- Produces: `MainWindow._sync_playback_rate_controls(rate: float) -> None`

- [ ] **Step 1: Write failing tests for the expanded control surface**

Add:

```python
def test_playback_rate_controls_apply_presets_and_custom_values(qt_app):
    window = MainWindow()

    assert [
        window.speed_combo.itemText(index)
        for index in range(window.speed_combo.count())
    ] == [
        "0.25x", "0.5x", "0.75x", "1.0x", "1.25x",
        "1.5x", "2.0x", "3.0x", "4.0x", "自定义",
    ]
    assert window.custom_speed_spin.minimum() == pytest.approx(0.1)
    assert window.custom_speed_spin.maximum() == pytest.approx(4.0)

    window.speed_combo.setCurrentText("1.5x")
    assert window.player.playbackRate() == pytest.approx(1.5)
    assert window.custom_speed_spin.value() == pytest.approx(1.5)

    window.custom_speed_spin.setValue(1.7)
    window._on_custom_speed_committed()
    assert window.player.playbackRate() == pytest.approx(1.7)
    assert window.speed_combo.currentText() == "自定义"
```

Add:

```python
def test_invalid_playback_rate_restores_the_last_valid_value(qt_app):
    window = MainWindow()
    window.custom_speed_spin.setValue(1.7)
    window._on_custom_speed_committed()

    assert not window._apply_playback_rate(4.1)
    assert window.player.playbackRate() == pytest.approx(1.7)
    assert window.custom_speed_spin.value() == pytest.approx(1.7)
    assert "0.1x" in window.status_label.text()
    assert "4.0x" in window.status_label.text()
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "playback_rate_controls or invalid_playback_rate" -v
```

Expected: fail because `custom_speed_spin` and the playback-rate methods do not exist.

- [ ] **Step 3: Build the controls and a single rate-application path**

In `_build_video_panel()`:

```python
self.speed_combo.clear()
for rate in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0):
    self.speed_combo.addItem(f"{rate:g}x", rate)
self.speed_combo.addItem("自定义", None)
self.speed_combo.setCurrentText("1.0x")

self.custom_speed_spin = QDoubleSpinBox()
self.custom_speed_spin.setRange(0.1, 4.0)
self.custom_speed_spin.setDecimals(3)
self.custom_speed_spin.setSingleStep(0.1)
self.custom_speed_spin.setSuffix("x")
self.custom_speed_spin.setValue(1.0)
```

Add the spin box after the preset combo in the existing `controls` layout.

Add a constant for the preset rates and implement:

```python
def _apply_playback_rate(self, rate: float) -> bool:
    if not 0.1 <= rate <= 4.0:
        self._sync_playback_rate_controls(self._last_playback_rate)
        self._set_status("播放速度需在 0.1x 到 4.0x 之间")
        return False
    self.player.setPlaybackRate(rate)
    self._last_playback_rate = rate
    self._sync_playback_rate_controls(rate)
    return True
```

Use `QSignalBlocker` inside `_sync_playback_rate_controls()` so changing one
control never recursively emits the other control's handler. Numeric preset
selection calls `_apply_playback_rate`; selecting `自定义` gives focus to
`custom_speed_spin` without changing the current player rate. Connect
`custom_speed_spin.editingFinished` to `_on_custom_speed_committed()`.

- [ ] **Step 4: Run the playback-rate tests and the existing UI-copy test**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "playback_rate_controls or invalid_playback_rate or editable_metadata_combos" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit only the playback-rate implementation and tests**

Run:

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: add custom playback rate control"
```

### Task 2: Make The Existing Task Table Detachable

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `video_labeler/ui/main_window.py:254-317, 710-780, 895-930`

**Interfaces:**
- Preserves: `MainWindow.task_panel: QGroupBox`
- Preserves: `MainWindow.task_table: QTableWidget`
- Produces: `MainWindow.detach_table_button: QPushButton`
- Produces: `MainWindow.task_table_dialog: QDialog`
- Produces: `MainWindow._show_task_table_dialog() -> None`
- Produces: `MainWindow._restore_task_panel(*args: object) -> None`

- [ ] **Step 1: Write failing tests for default, detached, and restored table ownership**

Add:

```python
def test_task_table_defaults_to_bottom_card_and_can_detach_and_restore(qt_app):
    window = MainWindow()
    window.records = [_clip_record("source.mp4", 1)]
    window._refresh_table()

    assert window.workspace_splitter.indexOf(window.task_panel) == 1
    assert window.task_panel.parentWidget() is window.workspace_splitter

    window._show_task_table_dialog()
    qt_app.processEvents()
    assert window.task_table_dialog.isVisible()
    assert window.task_panel.parentWidget() is window.task_table_dialog
    assert window.task_table_dialog.findChild(QTableWidget) is window.task_table

    window.task_table.selectRow(0)
    qt_app.processEvents()
    assert window._editing_index == 0

    window.task_table_dialog.close()
    qt_app.processEvents()
    assert window.workspace_splitter.indexOf(window.task_panel) == 1
    assert window.task_panel.parentWidget() is window.workspace_splitter
    assert window.task_table.currentRow() == 0
```

Add:

```python
def test_narrow_window_keeps_embedded_table_until_user_detaches_it(qt_app):
    window = MainWindow()
    window.resize(1120, 720)
    window.show()
    qt_app.processEvents()

    assert window.main_content_scroll.verticalScrollBar().maximum() > 0
    assert window.task_panel.parentWidget() is window.workspace_splitter
    window.detach_table_button.click()
    assert window.task_table_dialog.isVisible()
```

- [ ] **Step 2: Run the table-dialog tests and verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "task_table_defaults_to_bottom_card or narrow_window_keeps_embedded_table" -v
```

Expected: fail because the detach button, dialog, and reparenting methods do not exist.

- [ ] **Step 3: Reparent the original task panel into one modeless dialog**

In `_build_task_table()` create:

```python
self.detach_table_button = QPushButton("弹出表格")
self.detach_table_button.setObjectName("secondaryButton")
toolbar.addStretch(1)
toolbar.addWidget(self.detach_table_button)
```

In `_build_ui()` after `task_panel` is created:

```python
self.task_table_dialog = QDialog(self)
self.task_table_dialog.setWindowTitle("片段任务")
self.task_table_dialog.setModal(False)
self.task_table_dialog.setMinimumSize(900, 500)
self.task_table_dialog.setLayout(QVBoxLayout())
self.task_table_dialog.finished.connect(self._restore_task_panel)
```

Implement `_show_task_table_dialog()` with a guard that returns when the
panel is already detached. Remove `task_panel` from `workspace_splitter`,
set its parent to `None`, add it to the dialog layout, then call
`show()`, `raise_()`, and `activateWindow()`.

Implement `_restore_task_panel()` with a guard that returns when the panel is
already embedded. Remove it from the dialog layout, set its parent to `None`,
insert it at `workspace_splitter` index 1, and restore
`workspace_splitter.setSizes([560, 320])`.

Connect `detach_table_button.clicked` to `_show_task_table_dialog()` in
`_connect_signals()`.

- [ ] **Step 4: Run all table, filter, batch, and selection tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "task_table or table_batch or filtering or sort_clears or delete_clears or selecting_clip" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit only the detachable-table implementation and tests**

Run:

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: add detachable task table"
```

### Task 3: Refine The Card Layout And External QSS

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `tests/test_themes.py`
- Modify: `video_labeler/ui/main_window.py:30-50, 254-500, 710-780`
- Modify: `video_labeler/themes/light_fresh.qss`

**Interfaces:**
- Produces: `MainWindow._apply_card_shadow(widget: QWidget) -> None`
- Produces: semantic object names `toolbarCard`, `videoCard`, `annotationCard`,
  `taskCard`, `toolbarActionGroup`, `videoControlsPanel`, and `mainContentScroll`.
- Preserves: current widget ownership and business signal connections.

- [ ] **Step 1: Write failing tests for card semantics and video-control separation**

Add:

```python
def test_card_workspace_uses_semantic_cards_without_overlapping_video_controls(qt_app):
    window = MainWindow()
    window.resize(1280, 900)
    window.show()
    qt_app.processEvents()

    assert window.project_header.objectName() == "toolbarCard"
    assert window.video_panel.objectName() == "videoCard"
    assert window.annotation_panel.objectName() == "annotationCard"
    assert window.task_panel.objectName() == "taskCard"
    assert window.video_controls_panel.geometry().top() > (
        window.video_widget.geometry().bottom()
    )
    assert window.video_panel.graphicsEffect() is not None
```

Extend `tests/test_themes.py`:

```python
def test_light_theme_contains_card_workspace_selectors():
    stylesheet = load_light_fresh_theme()
    for selector in (
        "QGroupBox#toolbarCard",
        "QGroupBox#videoCard",
        "QGroupBox#annotationCard",
        "QGroupBox#taskCard",
        "QWidget#videoControlsPanel",
    ):
        assert selector in stylesheet
```

- [ ] **Step 2: Run the new card-style tests and verify they fail**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_card_workspace_uses_semantic_cards_without_overlapping_video_controls tests/test_themes.py::test_light_theme_contains_card_workspace_selectors -v
```

Expected: fail because the semantic card object names and shadow helper do not exist.

- [ ] **Step 3: Restructure only the visual hierarchy**

In `_build_ui()`, replace
`content_layout.addWidget(self._build_project_header())` with:

```python
self.project_header = self._build_project_header()
content_layout.addWidget(self.project_header)
```

In `_build_project_header()` keep the existing widgets and handlers, set the
returned group object name to `toolbarCard`, and regroup its grid contents
into a compact two-row layout. Import `QFrame` and use vertical separators
with `toolbarActionGroup` object names between project, data, and assistance
actions. Do not nest card group boxes inside the header.

Store the video group in `self.video_panel` and set object name `videoCard`.
Set `annotation_panel` object name to `annotationCard` and `task_panel` object
name to `taskCard`. Preserve the video control widget below `video_widget`;
retain the 420-pixel minimum preview and the 16-pixel vertical gap.

Import `QGraphicsDropShadowEffect` and implement:

```python
def _apply_card_shadow(self, widget: QWidget) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(18)
    effect.setOffset(0, 3)
    effect.setColor(QColor(31, 45, 61, 28))
    widget.setGraphicsEffect(effect)
```

Call this helper after each top-level card is created. Do not apply effects to
cells, controls, behavior checkboxes, or the video viewport.

- [ ] **Step 4: Add card QSS only to `light_fresh.qss`**

Add selectors for the four card object names, toolbar action groups, the
detachable-table button, the custom speed spin box, and `mainContentScroll`.
Keep existing palette values and use thin `#DCDFE6` borders, white cards,
`#ECF5FF` hover treatment, and the existing `#409EFF` accent. Do not alter
QFileDialog `QAbstractItemView` rules.

- [ ] **Step 5: Run card, theme, layout, and popup regressions**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "card_workspace or video_preview or video_progress or video_first_workspace or popup or theme" -v
D:\Python311\python.exe -m pytest tests/test_themes.py -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit only the card-style implementation and tests**

Run:

```powershell
git add video_labeler/ui/main_window.py video_labeler/themes/light_fresh.qss tests/test_main_window.py tests/test_themes.py
git commit -m "feat: refine card workspace UI"
```

### Task 4: Full Verification, Authorized Cleanup, And Branch Push

**Files:**
- Modify: `docs/superpowers/plans/2026-08-04-card-workspace-ui.md`

**Interfaces:**
- Consumes: completed Tasks 1 through 3 and the existing full pytest suite.
- Produces: a locally committed, tested branch and a successful push of
  `feature/video-segment-labeler-zh`.

- [ ] **Step 1: Run the complete suite**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

Expected: zero failures.

- [ ] **Step 2: Start the application for visual acceptance**

Run:

```powershell
Start-Process -FilePath 'D:\Python311\python.exe' -ArgumentList 'app.py' -WorkingDirectory 'C:\Users\16102\Downloads\video_labeler\.worktrees\chinese-ui-localization' -PassThru
```

Confirm that the process has a nonzero main-window handle. Visually check that
the controls sit below the video, the table is initially embedded, the
detachable dialog returns the table when closed, and the custom speed input
updates the player.

- [ ] **Step 3: Inspect the cleanup candidates before deletion**

Run:

```powershell
$paths = @(
  [IO.Path]::GetFullPath($env:TEMP),
  [IO.Path]::GetFullPath("$env:LOCALAPPDATA\Temp"),
  'C:\Users\16102\Downloads\video_labeler\.worktrees\chinese-ui-localization\.pytest_cache'
) | Select-Object -Unique
$paths | ForEach-Object {
  if (Test-Path -LiteralPath $_) {
    $size = (Get-ChildItem -LiteralPath $_ -Force -Recurse -ErrorAction SilentlyContinue |
      Measure-Object -Property Length -Sum).Sum
    [PSCustomObject]@{ Path = $_; Bytes = $size }
  }
} | Format-Table -AutoSize
```

Verify every printed path matches the approved cleanup list before the next
step. Do not inspect or delete any other C-drive directory.

- [ ] **Step 4: Clean only the approved temporary contents**

Run:

```powershell
$paths = @(
  [IO.Path]::GetFullPath($env:TEMP),
  [IO.Path]::GetFullPath("$env:LOCALAPPDATA\Temp"),
  'C:\Users\16102\Downloads\video_labeler\.worktrees\chinese-ui-localization\.pytest_cache'
) | Select-Object -Unique
foreach ($path in $paths) {
  if (Test-Path -LiteralPath $path) {
    Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue |
      Remove-Item -Recurse -Force -ErrorAction Continue
  }
}
Get-ChildItem -LiteralPath 'C:\Users\16102\Downloads\video_labeler' -Filter 'ui-smoke-*.png' -File -ErrorAction SilentlyContinue |
  Remove-Item -Force -ErrorAction Continue
Clear-RecycleBin -Force -ErrorAction Continue
```

Report deleted/skipped files and never retry removal of in-use files with
forced process termination.

- [ ] **Step 5: Stage the implementation plan and commit it locally**

Run:

```powershell
git status --short
git add docs/superpowers/plans/2026-08-04-card-workspace-ui.md
git commit -m "docs: plan card workspace UI"
```

Before staging, verify the status output contains only files from this
approved work. Do not stage `.superpowers` artifacts.

- [ ] **Step 6: Push the branch without merge, rebase, or pull request**

Run:

```powershell
git push -u origin feature/video-segment-labeler-zh
```

Expected: the local branch tracks `origin/feature/video-segment-labeler-zh`.
