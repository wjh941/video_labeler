# Stage 1 Productivity UI Design

## Goal

Improve the efficiency of the Chinese video-labeling workflow without changing
the record model, English tag constants, CSV structure, output filename format,
or FFmpeg behavior. This stage covers global keyboard operation, batch task
editing, table filtering and sorting, and a compact responsive behavior-tag
editor.

## Scope And Boundaries

This is the first of three serial delivery stages:

1. Productivity UI: shortcuts, batch table actions, responsive collapsible tags,
   and preserving label selections after adding a clip.
2. Persistent export configuration and its FFmpeg/export-worker integration.
3. Chinese dataset statistics reporting.

Stage 1 modifies only `video_labeler/ui/main_window.py` and
`tests/test_main_window.py`.

It does not change `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`,
`VIEW_TYPES`, CSV headers or contents, output filename syntax, FFmpeg command
construction, export worker behavior, or other modules.

## Keyboard Workflow

The main window registers these window-scoped shortcuts:

- Space: play or pause.
- I: set the clip start time to the current player position.
- O: set the clip end time to the current player position.
- Enter: add or update the clip.
- Delete: remove the selected task rows through the same confirmation workflow
  used by the batch delete action.
- Ctrl+S: save the task CSV.
- Ctrl+E: start batch export.
- Left and Right: seek backward or forward five seconds.
- Shift+Left and Shift+Right: seek backward or forward thirty seconds.

The project header gains a Chinese "shortcut help" button. It opens a compact
modal Chinese table of every key and action. The existing dynamic status label
remains for runtime feedback, while a separate permanent Chinese shortcut hint
is displayed in the bottom status area.

## Task Table

The existing `QTableWidget` remains the table implementation. Its selection mode
changes to extended row selection, so Ctrl and Shift operate on multiple rows.

The task area gains Chinese controls for batch edit, batch delete, behavior
filter, polarity filter, export-status filter, clearing filters, and ordering by
sequence or duration in ascending or descending order.

Filters hide non-matching rows through the table view and never delete or mutate
records. A behavior filter matches whether the behavior appears in a record's
behavior tuple. The polarity and status filters match their stored English
values; only their user-visible labels are Chinese. Clearing filters restores
all rows.

Sorting reorders `self.records` and refreshes the table. Sorting is limited to
sequence and clip duration, with ascending and descending variants. Existing
filenames, sequence values, statuses, and task metadata are not rewritten.

Batch deletion lists the selected-row count in a Chinese confirmation dialog.
On confirmation, it removes those records in descending row order, clears the
edit state, refreshes the table, and updates the status area.

## Batch Metadata Editing

The Chinese batch-edit modal operates on all selected records. It provides
independent checkboxes that decide whether to apply each field:

- Behavior labels, using the existing English checkbox values.
- Polarity.
- Lighting.
- View.

Unchecked fields remain unchanged. If behavior editing is enabled, at least one
behavior must be selected. The three metadata selectors expose the same current
values as the main editor, excluding the non-data custom action.

For a record with a standard parseable output name, the modal derives its
existing date, camera, and sequence, applies the chosen metadata changes, then
rebuilds the output filename through the existing naming service. The operation
first verifies that the prospective output names are unique, including against
unselected rows, before changing any record.

For a record whose manually edited output name is not parseable, batch editing
updates its stored behaviors, polarity, and lighting but leaves the manually
chosen output name untouched. A view update is skipped for that record because
view is not stored separately from a standard filename. This preserves manual
filenames and avoids inventing metadata.

## Behavior Tag Layout

Replace the behavior-label `QGroupBox` with a local
`CollapsibleGroupBox` subclass in `main_window.py`. It is expanded by default,
uses a Chinese title, and hides or restores only its inner checkbox container
when toggled. The rest of the annotation editor remains unchanged.

Behavior checkboxes use a direct grid layout without a nested scroll area. The
grid automatically uses three columns at normal editor widths and two columns at
narrow widths. A resize handler recalculates positions and applies consistent
compact spacing. The outer editor scroll area remains available for genuinely
small windows, but the tag group itself has no vertical scrollbar.

Adding a clip must keep the current behavior checkboxes, polarity, lighting,
and view selection. Only sequence progression and normal time/filename preview
updates occur after the new record is appended.

## Error Handling

All new commands handle empty table selection without mutating the task list.
Batch edit displays Chinese errors for no selected rows, no selected behavior
when behavior replacement is enabled, duplicate generated filenames, and
unsupported metadata in manually named rows. Canceling either modal leaves the
table and editor untouched.

## Verification

Extend `tests/test_main_window.py` with:

- `test_main_window_shortcut_mapping`
- `test_table_batch_operation_chinese_text`
- `test_add_clip_keep_label_selected`
- `test_collapsible_behavior_group`
- `test_tag_area_no_scrollbar`

The tests verify real MainWindow behavior: shortcut registration, Chinese button
and dialog copy, extended row selection, batch-action controls, label state
preservation, collapse and expand behavior, and the absence of a nested tag
scroll area. Existing tests continue to verify filename generation, import,
custom dropdowns, and compact editor placement.

## Self-Review

The stage remains limited to the two designated UI and UI-test files. It
preserves the shared English constants and all cross-module export and CSV
contracts for later stages. Batch editing handles standard and manually named
records differently only where the data model requires it, which avoids losing
user-managed filenames.
