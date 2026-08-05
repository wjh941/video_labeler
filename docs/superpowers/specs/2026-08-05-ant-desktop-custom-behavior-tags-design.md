# Ant Desktop UI And Custom Behavior Tag Design

## Goal

Refine the existing PySide6 video annotation workspace into an Ant Design
Desktop inspired light interface while adding project-persistent custom
behavior tags. The result keeps the existing annotation workflow, CSV format,
single-clip FFmpeg export, project records, and refresh rules intact.

## Scope And Non-Negotiable Compatibility

The implementation may update:

- `video_labeler/project_io.py` for the project-level custom tag library.
- `video_labeler/naming.py` for syntax-based behavior tag validation.
- `video_labeler/ui/main_window.py` for layout and custom-tag interactions.
- `video_labeler/themes/light_fresh.qss` for the unified Ant light theme.
- Focused tests for project persistence, naming, CSV import registration, UI
  interactions, layout, and theme selectors.

The implementation must not change:

- CSV headers: `source,start,end,output`.
- The fields stored in each segment record.
- Existing filename shape, CSV export format, or FFmpeg command behavior.
- Existing validated add/update next-clip refresh behavior. A new clip still
  begins at the saved segment end, clears behavior selection, and preserves
  lighting, polarity, and view values.
- Existing playback, import/export, dirty-state, video switching, undo/redo,
  and shortcut behavior except where the UI must render their existing
  controls.

No remote Git action, merge, rebase, or pull request is part of this work.

## Data Model

`LabelProject` gains:

```python
custom_behavior_tags: list[str] = field(default_factory=list)
```

The serialized project document gains one root key:

```json
"custom_behavior_tags": ["vehicle_idle", "delivery_dropoff"]
```

The segment record schema remains unchanged. Segment behavior values continue
to live only in the existing `behaviors` list.

### Validation And Backward Compatibility

- New projects serialize `custom_behavior_tags`, including an empty list.
- Legacy `.labelproj` documents with the four historical root keys load with
  `custom_behavior_tags=[]`.
- New documents must contain the new root key and a list of strings.
- Each custom tag must satisfy the existing lowercase English token rule:
  `[a-z0-9_]+`.
- UI additions and serialization preserve insertion order and deduplicate the
  list. Built-in behavior constants are not duplicated into the custom
  library. A loaded document containing duplicate or built-in custom entries
  is invalid rather than silently rewritten.
- Invalid project documents still fail validation rather than silently
  rewriting corrupt data.

## Filename And CSV Behavior

`naming.py` validates behavior labels by token syntax rather than membership
in `BEHAVIOR_LABELS`. Built-in labels remain unchanged constants; the
relaxation only allows valid user-defined tags to pass through the existing
filename builder and parser.

- `build_filename()` preserves its current argument shape and its current
  filename format.
- `parse_filename()` parses syntactically valid unknown behavior tags.
- CSV files retain their exact existing columns and rows.
- When CSV import yields an unknown valid behavior, `MainWindow` adds it to
  the active project's `custom_behavior_tags` list before rendering imported
  data.
- Selecting an already local historical segment never restores a deleted tag
  to the tag library.

## Custom Tag UI And Historical Data Protection

### Available Tags

The behavior panel renders, in order:

1. All built-in English behavior labels.
2. The current project's custom behavior tags.

The panel adds a compact custom-tag input and an add button. Empty values are
rejected with the existing error-dialog pathway. New values are normalized,
deduplicated, persisted in the project tag library, and immediately rendered.

A custom behavior checkbox uses the same selection semantics as a built-in
checkbox, with a small top-right `x` control. Built-in labels never show that
control and cannot be removed.

### Deleting A Custom Tag

Before removal, the application scans records for every video in the current
project. When at least one record references the tag, it presents a Chinese
warning that removal hides the reusable button but preserves all saved
annotation data. On confirmation:

- Only the matching entry is removed from
  `project.custom_behavior_tags`.
- The tag string remains in all historical `ClipRecord.behaviors` values.
- Existing CSV contents and output filenames remain unchanged.
- The project becomes dirty and the behavior panel is refreshed.

### Deleted Historical Tags

When a selected record contains a behavior tag that is neither built-in nor
present in the current custom library, the behavior area adds a temporary
read-only historical capsule:

- Style: muted gray, non-clickable, and visually distinct from a selectable
  tag.
- Tooltip: `[Historical Tag] This tag has been removed from tag library, data
  remains inside this segment, cannot reuse via button`.
- Lifecycle: only present while editing the selected record; it disappears
  for a segment without it.
- Update safety: a hidden editor state includes the historical values in
  `selected_behaviors()` so updating another field does not erase those tags.
- Re-add behavior: adding the exact tag name back to the custom library
  replaces the historical capsule with an ordinary interactive selected tag.

## Partial Refresh And Expanders

The existing behavior group remains responsive and collapsible. Two matching
`CollapsibleGroupBox` instances wrap light condition and positive/negative
example controls. Their expanded state, along with the behavior panel state,
is never changed by selecting, updating, adding a segment, or adding a custom
tag.

Adding a custom tag updates only:

- Start time display.
- End time display.
- Behavior-tag controls and their responsive grid.

It does not reset, overwrite, or refresh lighting, polarity, view, or the
existing next-clip field preservation logic.

The behavior grid keeps full label text. It uses the existing minimum-width
measurement to choose two columns below the three-column threshold and three
columns at or above that threshold. The tag group does not add a dedicated
vertical scrollbar.

## Ant Design Desktop Layout

### Color And Shape System

`light_fresh.qss` becomes the single style source. It applies:

- Canvas `#f7f8fa`; panel interiors `#ffffff`.
- Main text `#1f2329`; secondary text `#86909c`.
- Borders and dividers `#e5e6eb`.
- Primary button `#1677ff`, hover `#4096ff`.
- Danger button `#ff7875`.
- Secondary controls `#f2f3f5` with `#4e5969` text.
- An `8px` radius for buttons, line edits, combo boxes, group boxes, and tag
  capsules.
- Low-contrast thin scrollbars and no heavy black borders.

Behavior pills use:

- Normal built-in and custom: `#e8f3ff` background, `#1677ff` text.
- Selected: `#1677ff` background, white text.
- Historical: `#f2f3f5` background, `#86909c` text.

The existing non-native QFileDialog readability selectors remain scoped to
`QAbstractScrollArea` and `QAbstractItemView`; direct `QFileDialog QListView`
or `QTreeView` selectors remain prohibited.

### Toolbar

The header uses three visual action groups:

1. `导入与 CSV`: video import, CSV import, and CSV save.
2. `导出与输出`: output-directory picker, elided output-path display, and
   batch export.
3. `设置与操作`: shortcut help and the existing export settings control.

Groups have compact captions, spacing, and light separators. The advanced
export settings panel stays collapsed by default. Date, camera, and viewpoint
inputs remain on one compact row. The output path display uses font-metric
elision and provides the full path through a tooltip.

### Annotation Workspace

- The video card and annotation panel use a 5:4 splitter ratio with a thin
  light-gray handle.
- The video card remains the visual priority and keeps all controls below the
  preview.
- The empty preview state uses a subtle placeholder icon and the Chinese hint
  `导入视频后开始标注`.
- Start time, end time, and sequence fields appear in one row.
- Add, delete, undo, redo, and clear buttons are the same height and aligned
  in one action row. They use primary, danger, or secondary styles based on
  existing semantics.
- Behavior tags, lighting, and positive/negative controls are separate,
  independent expanders.

## Testing

Add or update tests for:

1. New and legacy project documents, including missing
   `custom_behavior_tags`, malformed custom lists, deduplication, and
   serialization.
2. Custom label filename construction and parsing without changing existing
   filename assertions.
3. CSV import parsing of unknown valid behavior tags and UI registration into
   the active project library.
4. Add, duplicate rejection, deletion warning, project-wide reference scan,
   persistence, and historical-record preservation for custom tags.
5. Historical capsule tooltip, read-only state, disappearance on selection
   change, preservation during record update, and conversion after re-adding
   the tag.
6. Partial refresh behavior: custom-tag changes preserve lighting, polarity,
   view, and all expander states.
7. Three toolbar groups, output path tooltip/elision, one-row time fields,
   independent collapsibles, two/three-column tag reflow, and no text
   clipping.
8. Required Ant QSS selectors, color tokens, radius, tag states, and
   QFileDialog readability protection.

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
```
