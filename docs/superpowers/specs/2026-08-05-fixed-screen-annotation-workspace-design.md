# Fixed-Screen Annotation Workspace Design

## Goal

Keep the project toolbar above an always-visible, horizontal video and
annotation workspace. The main window must not use a global vertical scroll
bar after a video is imported.

## Layout

- The root central widget uses a `QVBoxLayout`, not an outer `QScrollArea`.
- The compact project settings card remains above the workspace. It keeps
  import, CSV, export, date, camera, and view controls without changing their
  signal wiring.
- `editor_splitter` remains horizontal at every supported size.
  - Left pane: `video_panel`, initial width ratio 52.
  - Right pane: annotation workspace, initial width ratio 48.
- The left pane continues to own the video surface, timeline, playback,
  seek, playback-rate, and start/end capture controls. The video surface
  receives all remaining vertical space above its fixed control panel.
- The right pane is a vertical layout, not a nested scrolling form:
  - source/time/action controls
  - collapsible behavior-tags group
  - collapsible custom-fields group
  - collapsible lighting group
  - collapsible polarity group
  - collapsible fragment-task group
- The task group owns the existing filters, table, batch actions, and detach
  action. It receives the remaining right-pane height and the table keeps its
  own row scrollbar.

## Compact Defaults

- Behavior tags are expanded by default so annotation begins immediately.
- Lighting, polarity, and custom fields start collapsed to preserve table
  height on a 720px-tall window. Their current values remain visible in the
  group title summary.
- The fragment-task group starts expanded and retains the existing detach
  table dialog.
- The group state remains stable while selecting or creating records.

## Compatibility

- Keep `self.records` as the active-video segment collection.
- Do not change CSV headers, clip record fields, project-file schema,
  filename generation, FFmpeg services, export workers, or table signals.
- Keep the behavior multi-select combo, custom-tag persistence, deleted
  historical tag presentation, partial refresh rule, undo/redo, filters,
  sort, batch actions, and keyboard shortcuts.
- Adding a custom tag may rebuild only the behavior selector and reset only
  the next clip range as already verified; lighting and polarity remain
  unchanged.

## Visual Rules

- Reuse the light Ant-style QSS palette and existing semantic object names.
- Compress only layout margins, spacing, and fixed control heights. Do not
  hide controls or reduce text below the current readable UI scale.
- Give splitter handles a subtle border and use low-contrast scrollbars only
  for table rows and combo popup options.

## Tests

- The root must not contain `main_content_scroll`; no top-level vertical
  scrollbar may appear at 1120x720 or after `set_source_path`.
- The horizontal workspace uses an approximately 52:48 video-to-annotation
  ratio.
- All right-side functional blocks are `CollapsibleGroupBox` instances.
- The task table remains inside its group, receives positive available
  height, and retains selection/edit synchronization.
- Existing partial-refresh, CSV/project, FFmpeg, history, shortcut, filter,
  and batch-operation tests remain green.
