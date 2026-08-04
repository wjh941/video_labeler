# Next Clip State Reset Design

## Goal

Make the post-save editor state deterministic for both adding a new clip and
updating an existing clip. After a successful save, the editor becomes a fresh
next-clip draft whose time range starts at the saved clip's end time, whose
behavior labels are empty, and whose polarity, lighting, and view values remain
selected.

## Scope And Boundaries

This is the first priority sub-project. It precedes the approved light-theme
redesign and style extraction work, which are explicitly out of scope until the
interaction behavior is accepted.

This sub-project modifies only:

- `video_labeler/ui/main_window.py`
- `tests/test_main_window.py`

It does not modify video playback, import or export behavior, CSV persistence,
FFmpeg commands, filename construction, shared data models, or the English
values in `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, and `VIEW_TYPES`.

## State Transition

`MainWindow.add_or_update_clip()` already creates a fully formed `ClipRecord`
before either appending it or replacing the selected record. Once that record
has been saved in `self.records`, both paths must use the same post-save
transition:

1. Leave the just-saved record intact and refresh the task table normally.
2. Clear `self._editing_index` and restore the add button text.
3. Set both `start_spin` and `end_spin` to the saved record's
   `end_seconds`.
4. Uncheck every behavior checkbox.
5. Preserve the currently selected polarity, lighting, and view values without
   calling their reset or restore logic.
6. Set `sequence_spin` to the next available sequence after either an append
   or an update. The saved record retains its own sequence; the editor now
   represents the next new record and must not reuse an existing sequence.
7. Refresh the filename preview after the draft state has been prepared.

A small private helper, such as `_prepare_next_clip(saved_end_seconds: float)`,
will own steps 2 through 5. It is called only after a successful add or update,
so validation errors and canceled actions leave the editor unchanged.

The helper is intentionally separate from `clear_editor()`. Manual clearing
continues to mean a full reset, including polarity and lighting defaults and
the standard next sequence. Reusing it with flags would couple two distinct
user actions and make future behavior changes error-prone.

## Selected-Row Loading

Selecting exactly one row in the task table remains an edit action.
`_load_selected_clip()` must fully overwrite the editor from the selected
record:

- start and end times
- sequence
- behavior checkboxes
- polarity
- lighting
- view, when recoverable from the standard output filename

It then marks the row as the active edit target, changes the add button to the
Chinese update action, seeks the player to the record start time, and refreshes
the filename preview. Multi-row selection or no selection exits edit mode as it
does today.

This loading behavior is deliberately different from the post-save transition:
row selection restores all fields, while saving prepares a new draft and keeps
only polarity, lighting, and view.

## Error Handling And Compatibility

The transition runs only after `ClipRecord` validation, filename generation,
and duplicate-name checks complete successfully. Therefore an invalid time
range, missing source video, or duplicate output name cannot clear behavior
labels or alter the time controls.

No stored record is rewritten as part of preparing the next draft. Existing
records retain their saved label tuple, metadata, output names, export status,
and timing. The playback, CSV, export, and filename services continue to
receive the same records and values as before.

## Verification

Update the previous behavior-preservation test so it asserts that adding a
record:

- advances the sequence to `002`;
- sets both time controls to the saved end time;
- clears all selected behavior checkboxes;
- retains the selected `indoor` view, `neg` polarity, and
  `night_full_color` lighting values.

Add a focused update-path test that selects an existing record, changes its
end time, saves through the update action, and verifies that the next draft:

- starts and ends at the updated end time;
- has no selected behavior checkboxes;
- retains its current polarity, lighting, and view;
- advances the sequence control to the next available value;
- leaves edit mode and restores the add button.

Strengthen the selected-row loading coverage to verify that selecting a
standard named record restores all five field groups: timing, behavior,
polarity, lighting, and view.

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
D:\Python311\python.exe -m pytest tests -v
```

## Self-Review

The specification defines separate semantics for manual clearing, post-save
new-draft preparation, and table-row loading. It explicitly covers both add
and update paths, leaves metadata retention unambiguous, and keeps the change
limited to existing UI and UI-test files. The deferred visual redesign is not
included in this implementation cycle.
