# Collapsible Project Settings And Partial Refresh Design

## Scope

Refine the existing PySide6 annotation UI without changing CSV schemas,
project data, FFmpeg commands, or segment editing and export behavior.

## Design

- Convert the existing top-level `project_header` card to the established
  `CollapsibleGroupBox` implementation. It remains expanded by default and
  retains the existing toolbar, metadata controls, and advanced export panel.
- Keep behavior tags as the existing animated collapsible, responsive two or
  three column grid. No new scroll container is introduced.
- When a custom behavior tag is added, preserve the current start/end range
  while rebuilding the behavior tag controls. Preserve the current lighting
  and polarity selections exactly.
- Keep the existing `S` and `E` shortcuts and their player-position bindings.
- Preserve all existing action buttons and their connections.

## Responsive Behavior

- The project settings card can collapse to reduce vertical usage.
- Existing content-viewport responsive splitter behavior remains unchanged:
  narrow content stacks video and annotation areas vertically; wider content
  retains the video-first horizontal layout.

## Testing

- Add a regression test covering custom-tag partial refresh: range and
  behavior controls refresh while lighting and polarity remain selected.
- Add a regression test proving the project settings card is an expanded
  collapsible group with the existing controls still attached.
- Run the full pytest suite and compileall before commit and push.

## Non-Goals

- No CSV header, segment field, project schema, FFmpeg, or export-worker
  changes.
- No removal or renaming of existing controls or shortcuts.
