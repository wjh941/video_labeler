# Scrollable Annotation Workspace Design

## Goal

Keep the video preview and the core segment editor visible together in the
same initial workspace. Move lower-priority content below that workspace so
it remains reachable through normal vertical scrolling instead of compressing
or clipping annotation controls.

## Root Cause

The fixed-screen layout places the complete editor, four collapsible groups,
and the fragment task table in the same fixed-height right pane. Even when
groups are collapsed, the available vertical space is insufficient after a
video is loaded, so labels and table controls compete for height.

## Layout

- The central widget uses one vertical `QScrollArea` for the application
  page. Its viewport contains the project toolbar, a top workspace row, the
  fragment task panel, and export status.
- The top workspace row is a `QHBoxLayout`:
  - Left: the existing video panel with preview, timeline, playback controls,
    speed controls, and start/end capture controls.
  - Right: the existing annotation editor card with time fields, segment
    actions, behavior picker, custom-tag tools, lighting, polarity, and
    filename preview.
- The video and core editor retain approximately the current 52:48 width
  balance. They are siblings in the same row and remain visible together
  before the user scrolls.
- The fragment task panel is placed below the top workspace row at page
  width. Its collapsible state, filters, table, batch actions, and detached
  dialog behavior remain unchanged.
- Export status remains below the task panel.

## Interaction And Compatibility

- Keep `self.records` as the active-video segment list.
- Do not change clip CRUD, selection synchronization, partial editor refresh,
  undo/redo, table filters/sort/batch actions, keyboard shortcuts, CSV,
  `.labelproj`, naming, FFmpeg, or export-worker behavior.
- Adding a custom behavior tag continues to refresh only start time, end
  time, and behavior controls. Lighting, polarity, and their collapse states
  remain unchanged.
- Continue to use the existing `BehaviorTagComboBox`; no tag data changes.
- Retain the task table's standalone dialog option and correct reparenting
  on close.

## Visual Rules

- Preserve the existing light Ant-style QSS and semantic object names.
- The page scroll bar is the only new primary scrolling mechanism. Table rows
  may keep their own vertical scroll bar when necessary.
- Keep the video controls below the video surface and retain their existing
  clearance.
- The top row must not introduce horizontal clipping at the supported minimum
  width of 1120 pixels.

## Tests

- At 1120x720 after `set_source_path`, the central page owns a vertical scroll
  area and the video panel plus annotation editor are visible in the same
  top workspace row.
- The task panel is below that workspace row rather than inside the right
  editor card.
- Existing table detach/restore and partial-refresh tests remain unchanged
  and pass.
- Existing video-control clearance and behavior selector tests remain green.
