# Refined Desktop App Visual Implementation Plan

> **For implementation:** Execute in this worktree and keep all commits local
> on `feature/video-segment-labeler-zh`. Do not push, merge, or create a PR.

**Goal:** Give the existing video-first annotation application a cohesive,
brand-accented desktop-app finish while preserving all annotation, project,
export, playback, and synchronization behavior.

**Architecture:** Keep the existing `MainWindow`, `QGraphicsView`, card
containers, `QTableWidget`, and signal bindings. Add only visual hierarchy,
display-only player feedback, standard icons, and button hover elevation inside
the UI layer. Put every static color and widget rule in the global QSS file.

**Tech stack:** PySide6, Qt Fusion, QSS, QGraphicsScene,
QGraphicsDropShadowEffect, QPropertyAnimation, pytest-qt.

---

## Task 1: Add visual-regression coverage for the refined workbench

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `tests/test_light_theme.py`

1. Update the playback-rate expectation to the approved eight presets followed
   by `自定义`; verify that an arbitrary custom valid value changes the badge
   and returns the combo to `自定义`.
2. Add a player-scene overlay test for the empty, loading, and loaded states.
   The test must verify the overlay stays centered within the graphics scene.
3. Add a visual-semantic test that verifies:
   - toolbar groups have `importActionGroup`, `csvActionGroup`,
     `exportActionGroup`, and `settingsActionGroup` object names;
   - the toolbar captions, rate badge, table filter bar, and table action bar
     exist;
   - transport controls have a standard icon and retain their Chinese text.
4. Add non-clipping geometry regression tests at `1120x720` and `1440x900`:
   - video controls must remain below the `QGraphicsView`;
   - text controls must be at least their size-hint width when visible;
   - controls remain inside their parent layouts;
   - behavior labels retain their existing complete-text two/three-column
     behavior.
5. Add QSS selector coverage for refined cards, toolbar groups, video surface,
   playback-rate component, behavior pills, alternating table rows, and hover
   interaction states.
6. Run the targeted tests and confirm the new assertions fail before UI code is
   changed.

## Task 2: Refine `MainWindow` presentation without changing workflows

**Files:**
- Modify: `video_labeler/ui/main_window.py`

1. Replace `PLAYBACK_RATE_PRESETS` with the approved sequence:
   `0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0`.
2. Build the toolbar as four compact, captioned action groups using existing
   button instances and existing signal connections:
   - Import: `open_video_button`;
   - CSV: `import_csv_button`, `save_csv_button`;
   - Export: `output_folder_button`, `output_folder_label`, `export_button`;
   - Settings: `shortcut_help_button`, with the existing export settings
     remaining available below the toolbar row.
   Enable output-path wrapping; do not replace any action or handler.
3. Add a non-interactive `QGraphicsSimpleTextItem` in the existing video scene
   for empty/loading media status. Reposition it from `_resize_video_item()`;
   connect it to media status changes. It must only indicate display state and
   must not affect playback.
4. Refine the below-preview controls into progress and transport rows. Keep the
   existing widgets, player APIs, shortcut methods, and signal connections.
   Add a display-only `playbackRateBadge`; update it only from
   `_sync_playback_rate_controls()`.
5. Add native Qt standard icons and tooltips to transport buttons while
   retaining their Chinese text labels. Update the play icon together with its
   existing state text.
6. Keep the current behavior-checkbox responsive layout intact. Assign a
   semantic object name to each behavior checkbox for QSS pill styling.
7. Move existing table filters into a top `tableFilterBar` and existing batch
   actions plus the detach button into a bottom `tableActionBar`. Preserve the
   exact table object, row-selection behavior, filters, sort handlers, and
   reparenting behavior. Enable comfortable rows and alternate row colors.
8. Add an internal presentation-only button-hover helper:
   - attach a `QGraphicsDropShadowEffect` and 180ms blur animation;
   - handle Enter/Leave in the existing event filter without consuming events;
   - attach it to the main primary, transport, clip-boundary, and task-action
     buttons.
   Do not change button click connections or state logic.

## Task 3: Apply the refined global theme

**Files:**
- Modify: `video_labeler/themes/light_fresh.qss`

1. Retain the existing QFileDialog `QAbstractScrollArea` / viewport rules that
   prevent the Windows file-browser black-screen regression.
2. Replace the flat white visual system with the approved palette:
   - canvas `#F3F6FA`;
   - primary `#4F97E8`;
   - secondary `#20A39E`;
   - headings `#253042`;
   - labels `#5B687A`;
   - card `#FCFDFE`;
   - border `#E5EAF1`.
3. Create clear 12–16px card tiers for toolbar, video, annotation, and task
   cards. Preserve their semantic object names and their applied shadow
   effects.
4. Style toolbar captions/groups, gradient-highlight primary export action,
   input focus state, video scene/control component, rate badge, behavior-tag
   pills, and table filter/action bars.
5. Give the table 34px rows, comfortable header styling, alternate rows, and
   soft selected-row feedback. Keep dialog and pop-up inherited styles.
6. Define concise 180ms hover/focus/checked transitions through QSS while
   leaving physical animation to Task 2.
7. Do not add QSS strings to Python modules.

## Task 4: Verify presentation and behavior

**Files:**
- Verify: `tests/test_main_window.py`
- Verify: `tests/test_light_theme.py`
- Verify: all existing test modules

1. Run targeted UI and theme tests:

   ```powershell
   D:\Python311\python.exe -m pytest tests/test_main_window.py tests/test_light_theme.py -v
   ```

2. Run the full suite:

   ```powershell
   D:\Python311\python.exe -m pytest tests -v
   ```

3. Launch `python app.py` using `D:\Python311\python.exe` for visual
   acceptance. Confirm the card hierarchy, player prominence, controls, rate
   input, table bars, and behavior pills fit without text clipping at both
   normal and narrow window sizes.
4. Commit only implementation and test files locally after verification. Leave
   `.superpowers/brainstorm/` untracked and do not push.
