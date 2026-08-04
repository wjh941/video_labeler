# Card Workspace UI Design

## Goal

Refine the PySide6 annotation application into a focused card-style workspace:
make the video preview the dominant surface, keep playback controls outside
the picture, improve the annotation panel hierarchy, provide a manually
detachable task table, and add an effective preset-plus-custom playback-rate
control without changing annotation, CSV, or FFmpeg behavior.

## Scope

This change is limited to presentation, layout, task-table presentation
ownership, and playback-rate input. Existing segment records, refresh rules,
table signal handlers, project files, CSV import/export, filename generation,
single-clip export, batch export, FFmpeg commands, and video loading remain
unchanged.

The current active-video segment list remains `self.records`. The existing
`task_table` remains the sole task table. No second model, record copy, or
parallel selection state is introduced.

## Layout

### Top Toolbar Card

The project header becomes a compact, card-style toolbar with visually
separated action groups:

- Project: create, open, save, and restore project actions.
- Data: import video, import CSV, select output folder, and export actions.
- Assistance: shortcut help and other secondary controls.

Primary actions use the existing soft blue accent. Secondary actions use
neutral outlined controls. The layout uses consistent gaps and avoids a long
unstructured row of equally prominent buttons.

### Video-First Work Area

The outer vertically scrollable workspace remains the containment boundary.
The editor splitter continues to place the video card on the left and the
annotation card on the right.

The video card keeps a `QGraphicsView` backed by the existing
`QGraphicsVideoItem`. Its preview surface retains a minimum height of at
least 420 pixels. Playback progress, time labels, seek controls, start/end
actions, and playback-rate controls remain inside `video_controls_panel`,
which is below the preview surface and never overlays it.

The annotation panel remains the existing scrollable editor. It receives
larger, consistent inner spacing and light card shadow/border treatment only;
its widget hierarchy, behavior-tag flow layout, collapsible behavior group,
and data bindings remain unchanged.

### Bottom Task Table Card

The task table remains embedded by default as the second widget of
`workspace_splitter`, below the editor splitter. It keeps the existing
filters, sort controls, batch controls, selection mode, headers, and model
data.

The task-card toolbar gains a Chinese `弹出表格` action. It is manually
activated only; the application never opens this dialog automatically when
the window is narrow.

At narrow main-window widths, the embedded task card remains in the vertical
scrolling workspace. Its table can be horizontally scrolled through the
existing table behavior; users may choose `弹出表格` for a larger separate
surface.

## Detachable Task Table

`MainWindow` owns one modeless task-table dialog and one `task_panel` widget.
When the user chooses `弹出表格`:

1. The current `task_panel` widget is removed from `workspace_splitter`.
2. The same widget is added to the dialog layout and shown.
3. The dialog is raised and activated without replacing the existing table,
   selection model, filters, or callbacks.

When the dialog closes:

1. The same `task_panel` is removed from the dialog layout.
2. It is inserted back at index 1 of `workspace_splitter`.
3. The splitter restores its video-first sizing constraints.

Because the widget itself moves rather than its contents being recreated,
selected rows, table edits, filtering, sorting, and editor synchronization
continue to use the original `task_table` and its existing signal handlers.
Closing the dialog does not discard records, clear filters, reset selection,
or modify active-video data.

## Playback-Rate Control

The control panel exposes:

- A preset `QComboBox` with `0.25x`, `0.5x`, `0.75x`, `1.0x`, `1.25x`,
  `1.5x`, `2.0x`, `3.0x`, `4.0x`, and `自定义`.
- A `QDoubleSpinBox` with range 0.1 through 4.0, three decimal places, and
  an `x` suffix.

The preset combo starts at `1.0x`. Selecting a numeric preset updates the
spin box and applies that value through one playback-rate method. Editing
the spin box applies its value when Enter is pressed or focus leaves the
control. A spin-box value matching a preset selects that preset; all other
valid values select `自定义`.

The shared apply method validates the range before calling
`QMediaPlayer.setPlaybackRate`. An invalid or unparsable edit restores the
last valid rate and shows a Chinese validation message. Playback speed is a
UI/player setting only; it never affects stored segment times or export
commands.

## Styling

All refinements extend `video_labeler/themes/light_fresh.qss`. The existing
palette stays intact:

- Application background: `#F5F7FA`
- Accent: `#409EFF`
- Main text: `#303133`
- Borders/dividers: `#DCDFE6` and `#EBEEF5`
- Selected table items: `#ECF5FF`

Cards use white backgrounds, restrained rounded corners, thin borders, and a
subtle `QGraphicsDropShadowEffect` applied through a presentation-only helper
for the header, video, annotation, and task cards. No inline QSS is added to
`main_window.py`.

The task-table dialog uses the globally applied light theme and retains normal
window controls. Existing file dialogs, message boxes, input dialogs,
tooltips, and other popups remain unchanged functionally.

## Testing

New and updated tests must prove:

1. Video controls remain below the preview surface after the card-layout
   refinements.
2. Selecting every preset applies the corresponding player playback rate.
3. Valid custom values in the 0.1 to 4.0 range apply, preserve their value,
   and select `自定义` when not a preset.
4. Invalid custom values restore the last valid rate without changing
   annotation data.
5. The embedded task table is the default state.
6. Opening the task-table dialog reparents the original `task_panel` without
   replacing `task_table`.
7. Selecting a row while the table is detached loads the existing editor
   fields; closing the dialog reparents the same panel back to the bottom
   workspace and retains that state.
8. A narrow main window preserves the video-first scrollable workspace and
   lets the task table be detached manually.
9. Existing project, annotation refresh, CSV, export, FFmpeg, and theme tests
   continue to pass.

The final verification command is:

```powershell
D:\Python311\python.exe -m pytest tests -v
```

## Cleanup And Delivery

After a green test suite, cleanup is restricted to:

- `%TEMP%`
- `C:\Users\16102\AppData\Local\Temp`
- project test and screenshot temporary artifacts
- Windows recycle bin

The cleanup excludes `C:\Windows`, `C:\Program Files`, project source and
Git files, the Downloads directory, browser profiles, and user documents.
Files in use are skipped and reported rather than forcing deletion.

After verification and cleanup, create local commits for the approved work
and push only `feature/video-segment-labeler-zh` to `origin`. Do not merge,
rebase, or create a pull request.
