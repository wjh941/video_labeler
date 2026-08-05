# Two-Panel Annotation Layout Design

## Scope

Refactor the PySide6 annotation UI into a fixed side-by-side workspace while
preserving all existing segment, project, CSV, and FFmpeg behavior.

## Layout

- Keep the existing collapsible project settings card at the top of the
  window. It continues to contain video/CSV actions and date, camera, view,
  output, and batch export controls.
- Replace the current top-editor plus bottom-table workspace with a horizontal
  `editor_splitter`.
  - Left: `video_panel`, containing the current graphics video preview,
    timeline, playback, seek, start/end capture, and playback-rate controls.
  - Right: a vertical `workspace_splitter`, containing the annotation form
    above the fragment task table.
- Set the horizontal splitter to a 55:45 initial ratio and make both panes
  non-collapsible. The application minimum width remains sufficient to avoid
  clipping either pane. The layout no longer automatically stacks video and
  annotation panes vertically at a narrow content viewport.
- Keep the task-table detach dialog. Restoring the dialog moves the existing
  table card back to the right-side vertical splitter.

## Behavior Tag Selection

- Replace the visible behavior checkbox grid with a multi-select
  `BehaviorTagComboBox` implemented inside `main_window.py`.
- The closed combo displays a concise selection summary. Its popup displays
  every built-in and project custom behavior tag as checkable items.
- The selected tag list remains multi-valued and continues to feed
  `selected_behaviors()`, filename generation, records, CSV export, and
  `.labelproj` persistence without schema changes.
- The popup is the only normal tag-selection surface. The old visible tag
  button grid and its reflow/scroll logic are removed.
- Deleted historical tags remain read-only gray labels below the selector only
  while the selected record references them. They are not added back to the
  active tag library automatically.

## Collapsible Form Groups

- Keep the animated `CollapsibleGroupBox` implementation and use independent
  groups for Behavior Tags, Lighting Condition, Positive/Negative Example,
  and Custom Fields.
- The behavior group contains the multi-select combo and temporary historical
  labels. The lighting and polarity groups retain their existing combos.
- The custom-fields group contains the existing custom behavior tag input and
  add action plus a custom-tag library selector and remove action. Removing a
  tag continues to use the existing warning and never changes segment data.
- Group expanded/collapsed states persist while selecting records or adding
  custom tags because the group widgets themselves are never rebuilt.

## Refresh And Compatibility Rules

- Adding a custom behavior tag snapshots the active start/end values, rebuilds
  only the behavior selector data, and reapplies the active range.
- Lighting and polarity widgets are not rebuilt, reset, or programmatically
  selected by that operation.
- Existing keyboard shortcuts for `S` and `E` continue to copy player
  position into the start and end inputs.
- CSV headers, segment fields, `.labelproj` data, custom tag persistence,
  filename construction, and FFmpeg commands remain unchanged.

## Style

- Keep the existing light Ant-style palette and apply it to the checkable
  combo popup, collapsed form groups, right-side splitter, and restored task
  table placement.
- Use the existing soft borders, eight-pixel radius, and scrollbars. No dark
  or native-only control styling is introduced.

## Testing

- Replace grid-specific tests with checks for the horizontal two-panel
  workspace, 55:45 initial splitter ratio, and right-side table containment.
- Add behavior-combo tests covering full popup data, multiple selected tags,
  selected-summary text, historical labels, and custom-tag add/remove
  refresh behavior.
- Retain tests for the existing `S`/`E` shortcuts, CSV import/export,
  project persistence, undo/redo, table selection, and detached table.
- Run the complete pytest suite and compileall after implementation.

## Non-Goals

- No changes to business data structures, CSV schema, project schema, FFmpeg
  command construction, or export-worker behavior.
- No Git push, merge, or pull request creation as part of this refactor.
