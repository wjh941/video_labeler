# Light Fresh Theme Design

## Goal

Replace the current dark, inline MainWindow styling with a unified fresh light
theme. The application, its Qt dialogs, tooltips, and non-native file choosers
must share the same visual language while all clip annotation, playback, CSV,
and FFmpeg behavior remains unchanged.

## Scope And Boundaries

This is Phase 2 and begins only after the accepted post-save interaction
changes. It covers visual styling, the behavior-tag expand/collapse transition,
and style code extraction.

The implementation modifies only the visual bootstrap and UI layer:

- `app.py`
- `video_labeler/themes/__init__.py` (new)
- `video_labeler/themes/light_fresh.qss` (new)
- `video_labeler/ui/main_window.py`
- `tests/test_main_window.py`
- theme-specific tests if a separate test module improves clarity

It must not change:

- clip creation, update, table selection, or post-save draft behavior;
- video playback controls or player wiring;
- CSV schema, import, or export;
- output filename construction;
- FFmpeg command construction or export-worker behavior;
- English label values in `BEHAVIOR_LABELS`, `POLARITIES`,
  `LIGHTING_VALUES`, or `VIEW_TYPES`;
- user-visible Chinese workflow copy outside text that is necessary for the
  themed behavior.

No merge, push, or pull request is part of this phase.

## Theme Architecture

Create the `video_labeler/themes` package.

`video_labeler/themes/light_fresh.qss` is the single source for all stylesheet
rules. It defines the visual system for main windows, panels, labels, form
controls, tables, buttons, scrollbars, sliders, progress bars, dialogs,
message boxes, input dialogs, file dialogs, and tooltips.

`video_labeler/themes/__init__.py` exposes:

- `load_light_fresh_theme() -> str`, which reads the QSS file as UTF-8.
- `apply_light_fresh_theme(app: QApplication) -> None`, which selects Qt's
  Fusion widget style and applies the loaded stylesheet to the application.

`app.py` creates the `QApplication`, calls `apply_light_fresh_theme(app)`, and
only then constructs `MainWindow`. Applying at application scope is required so
top-level `QDialog`, `QMessageBox`, `QInputDialog`, and `QToolTip` instances
inherit the same theme rather than only widgets descending from the main
window.

`main_window.py` imports no QSS strings. It removes every
`setStyleSheet()` call and uses only semantic `objectName` values where a
selector needs a specialized surface, including:

- `mutedLabel` for source and output-path helper text;
- `videoSurface` for the player viewport;
- existing action names such as `primaryButton`, `addClipButton`, and
  `dangerButton`;
- `collapsibleBehaviorGroup` for the animated behavior-tag container.

Qt controls the operating-system title bar and window frame; QSS cannot
repaint those platform-owned pixels. All dialog content, controls, lists,
buttons, messages, and file-picker panels use Fusion plus the application
stylesheet, so no dark native widget interior remains.

## Visual System

The QSS uses this stable palette:

- application background: `#F5F7FA`;
- surface and editable controls: white or near-white;
- primary accent and active focus: `#409EFF`;
- soft selected-row and list highlight: a pale blue such as `#ECF5FF`;
- primary text: dark gray such as `#303133`;
- secondary text: gray such as `#909399`;
- borders and separators: light gray such as `#DCDFE6`;
- hover backgrounds: light blue-gray with sufficient text contrast.

The stylesheet applies rounded, restrained geometry:

- panels and group boxes have white surfaces, thin borders, and 8px-or-less
  corner radii;
- inputs, combo boxes, spin boxes, and buttons share a 6px radius and
  consistent control heights;
- normal buttons use white surfaces, primary actions use `#409EFF`, add actions
  use the same light-blue family, and destructive actions use a subdued
  error treatment without a saturated full-background red;
- table headers are light gray-white, table rows receive a soft blue selected
  background, and grid lines stay thin and low contrast;
- sliders, progress bars, checkboxes, and scrollbars use light surfaces and
  the blue accent without black borders;
- the video viewport remains a neutral dark display surface for video contrast
  while surrounding controls and panel chrome use the light theme.

Layouts keep the existing widget hierarchy and controls. The root, project
header, video panel, clip editor, table area, and status area receive
consistent margins and spacing so controls have room at the supported minimum
window size. The responsive two-column/three-column behavior-tag reflow and
the outer annotation scroll area remain unchanged.

## Global Dialog And File-Chooser Styling

The application-level stylesheet includes rules for `QDialog`, `QMessageBox`,
`QInputDialog`, `QFileDialog`, `QToolTip`, `QDialogButtonBox`, and the
controls they contain. Existing shortcut-help and batch-edit dialogs retain
their current tables, labels, and button logic; only their appearance changes.
Existing confirmation and error calls retain their standard buttons, return
values, and status updates.

Every use of `QFileDialog.getOpenFileName`, `getSaveFileName`, and
`getExistingDirectory` passes `QFileDialog.Option.DontUseNativeDialog`.
`getExistingDirectory` also retains its existing directory-selection option.
This keeps the selected path and cancel behavior identical while ensuring
import, export, and output-folder dialogs are rendered by the themed Qt
widgets.

## Animated Behavior Tag Group

`CollapsibleGroupBox` remains the behavior-tag container type and keeps its
existing `set_content()` calling interface, `QGroupBox` inheritance, checkable
state, and checked/unchecked semantics.

The immediate `content.setVisible(expanded)` toggle is replaced by a 300ms
parallel animation:

1. The content widget's `maximumHeight` animates from its current expanded
   height to zero when collapsing, or from zero to its current size hint when
   expanding.
2. A custom chevron drawn in the group header animates from down to right when
   collapsing and from right to down when expanding. The chevron uses the
   theme accent rather than a hard-coded dark-theme color.
3. Content stays visible during the collapse animation and is hidden only in
   the animation-finished handler. On expansion it becomes visible before the
   height animation begins.
4. The animation uses a smooth easing curve and is stopped/restarted safely if
   the user toggles quickly.
5. On animation completion, the expanded content's maximum height is released
   so behavior-checkbox reflow can continue responding to window resize.

The native group-box indicator is visually suppressed by QSS. The group title
continues to toggle the checkable group, so keyboard and existing signal
connections remain compatible.

## Error Handling And Compatibility

The theme loader reads a bundled local QSS file. If that file is missing or
unreadable during development, application startup should fail with the
underlying file error instead of silently falling back to the previous dark
theme. This makes a broken theme package visible immediately.

The visual refactor must not add modal behavior, alter validation paths, or
change record state. The existing test doubles for `QFileDialog`,
`QInputDialog`, and `QMessageBox` continue to work because the production
methods retain the same calls and results, adding only the non-native dialog
option where applicable.

## Verification

Extend or add UI tests to verify:

- the external light theme loads into `QApplication`, uses the requested
  background and accent values, and includes styling selectors for dialogs,
  message boxes, input dialogs, file dialogs, and tooltips;
- the behavior group still starts expanded, collapses and expands after the
  300ms transition, retains the same checkbox content, and exposes the
  animated chevron state;
- file chooser calls request `DontUseNativeDialog` without changing the
  returned paths or cancellation behavior;
- existing responsive tag layout, interaction refresh rules, shortcuts, batch
  table operations, CSV import behavior, and filename behavior continue to
  pass.

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
D:\Python311\python.exe -m pytest tests -v
```

The previous 54-test suite must remain green; new focused visual tests may
increase the total count.

## Manual Visual Review

After automated verification, start the application from the Phase 2 worktree
and review:

- main-window light surfaces, spacing, selected task row, timeline, and player
  panel;
- behavior-tag expansion and collapse at normal and narrow window widths;
- shortcut-help, batch-edit, error, confirmation, custom-value, import/export,
  and folder-selection dialogs;
- tooltip appearance and controls in focused, hovered, selected, disabled, and
  scrolling states.

The refactor ends at this visual-review handoff. It does not merge, push, or
open a pull request.

## Self-Review

This design places visual data in a standalone QSS asset and applies it at
application scope, which covers all required Qt dialog types. It explicitly
preserves the UI control hierarchy and all business contracts. The animation
keeps the existing collapsible-group interface while defining exact timing,
visibility, and resize behavior. The visual and automated acceptance criteria
are separate, explicit, and limited to Phase 2.
