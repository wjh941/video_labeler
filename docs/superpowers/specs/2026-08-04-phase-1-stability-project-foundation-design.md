# Phase 1: Stability and Project Foundation Design

**Date:** 2026-08-04  
**Base branch:** `feature/video-segment-labeler-zh`

## Scope

Phase 1 fixes the current Qt rendering and behavior-tag layout problems, then
adds durable multi-video project state, undo/redo, and the finalized shortcut
set. It does not implement the visualization, reporting, batch-script, or
packaging work planned for later phases.

No automated push, merge, or pull-request operation is allowed. All changes
and commits remain local until manual acceptance.

## Non-Negotiable Compatibility Rules

- `self.records` remains the list of `ClipRecord` objects for the active
  video. Existing CSV export and single-video FFmpeg export continue to use
  that list and their current interfaces.
- Existing CSV fields, CSV file content, filename rules, English label
  constants, and FFmpeg cutting behavior are unchanged.
- The accepted post-save editor behavior is unchanged:
  - the next clip start and end both equal the saved clip end;
  - every behavior checkbox is cleared;
  - lighting, polarity, and view retain their selected values.
- Selecting an existing table row still loads all of that row's values into
  the editor.
- Phase 2 timeline/waveform, Phase 3 reporting/batch export, and Phase 4
  PyInstaller work are out of scope.

## UI Stability

### File Dialog

All file dialogs continue to use Qt's non-native implementation. The global
light theme keeps the dialog shell, buttons, and inputs styled, but does not
apply a broad background rule to `QListView` or `QTreeView` inside
`QFileDialog`. Targeted file-dialog rules explicitly use a white base and dark
text for the file list and directory tree so those surfaces render correctly.

### Application Startup

Before creating `QApplication`, `app.py` configures Windows high-DPI handling
and Qt software OpenGL fallback. Environment configuration is set before Qt
widget initialization; Qt application attributes and high-DPI rounding policy
are set before constructing the application. The selected configuration must
remain compatible with `QMediaPlayer` and `QVideoWidget`.

### Behavior Labels

`CollapsibleGroupBox` keeps its existing public calling interface and 300 ms
animation. The behavior checkboxes remain in the collapsible content widget,
but are reflowed into as many whole columns as the available panel width
supports, with a minimum useful checkbox width. The layout never uses a
vertical scroll area, and the collapsible content height is recalculated after
each reflow to prevent clipping.

The add and delete buttons retain their existing signals and behavior while
using semantic object names covered by `light_fresh.qss`.

## Project Persistence

### Data Model

A project persistence module owns JSON serialization and validation. Its
project document contains:

```json
{
  "version": 1,
  "active_video_id": "stable identifier",
  "global_settings": {
    "date": "",
    "camera": "",
    "scene": "",
    "view": "",
    "output_folder": ""
  },
  "videos": [
    {
      "id": "stable identifier",
      "path": "C:/absolute/path/to/video.mp4",
      "segments": []
    }
  ]
}
```

Each segment is serialized from and restored to `ClipRecord`. Stored paths are
absolute. A video entry keeps an independent mutable segment list. Project
JSON is UTF-8 and is written through a temporary sibling file followed by an
atomic replace.

`MainWindow` maintains a project object and an active-video reference. When a
video becomes active, it assigns `self.source_path`, `self.source_name`, and
`self.records` from that entry. Existing annotation, table, CSV, and
single-video FFmpeg methods therefore operate only on the active video's
segments without a new export interface.

The existing `导入视频` action adds a previously unseen absolute video path to
the project and activates it. Choosing a video already in the project simply
activates that entry. A compact active-video selector makes every loaded video
switchable. Batch import and removing videos are intentionally deferred to
Phase 3.

### Project Commands

The project menu provides:

- New Project
- Open Project
- Save Project
- Restore Project From Backup

`Ctrl+S` saves the `.labelproj` document. For an unsaved project, it opens a
save dialog. The existing `保存标注 CSV` button remains the only dataset CSV
export action and has no shortcut.

New Project, Open Project, Restore Project From Backup, and application close
prompt for confirmation when the current project has unsaved changes. Opening
or restoring validates the document before replacing the current project
state. Missing video paths are retained in the project and reported to the
user without discarding their saved annotations. A missing active source leaves
the player empty while retaining its annotations for a future valid path.

### Automatic Backups

Every annotation mutation (create, update, delete, and label edits) schedules
a single-shot 30-second debounce timer. A later mutation resets the timer.

If the project has a saved path when the timer expires:

1. Serialize the current project snapshot.
2. Write it to a `.backups` directory next to the project file.
3. Name it `<project-stem>_<YYYYMMDD-HHMMSS>.labelproj`.
4. Keep the ten newest backup files and delete older backups.

Unsaved projects do not create backups. Manual project save does not cancel,
replace, or count as an automatic backup. Restore opens a backup through a
file picker and replaces the current project only after successful validation.
On Windows, the backup directory is marked hidden after creation when the
platform accepts that attribute. If backup creation, cleanup, or writing fails,
the application reports the issue in the status area without blocking
annotation, project save, or playback.

## Undo and Redo

Undo/redo applies only to segment create, update, and delete operations for
the active video. Each operation stores immutable before and after snapshots
of that video's segment collection and the selected/editor state needed to
refresh the UI coherently.

An internal history stack tracks commands and a cursor. Adding a new command
after an undo discards only the redo branch. Undo and redo:

1. Restore the appropriate active-video segment snapshot.
2. Assign the restored list to `self.records`.
3. Refresh the table and current editor state.
4. Schedule automatic backup when the project has a saved path.
5. Update the enabled state of Undo and Redo controls.

No history action changes the confirmed post-save reset behavior used when a
new clip is prepared.

## Shortcuts

The window-level shortcut mapping is:

| Shortcut | Action |
| --- | --- |
| `Space` | Play/pause |
| `A` | Previous frame |
| `D` | Next frame |
| `S` | Set clip start to current video position |
| `E` | Set clip end to current video position |
| `Delete` | Delete selected segment |
| `Ctrl+Z` | Undo segment operation |
| `Ctrl+Y` | Redo segment operation |
| `Ctrl+S` | Save `.labelproj` project |

Previous `I`, `O`, `Enter`, `Ctrl+E`, and arrow-seek shortcut bindings are
removed from the global shortcut table for this phase to avoid conflicts with
the finalized mapping. The shortcut help dialog and status-bar hint list only
the mappings above.

Frame stepping uses the active media's position with a conservative 33 ms
step. It clamps to the media duration and does nothing when no playable video
is loaded.

## UI Integration

All new menus, buttons, dialogs, and disabled states use semantic object names
and the existing globally applied `light_fresh.qss` theme. No new inline style
strings are permitted in `main_window.py`.

Undo/redo controls are visible in the main toolbar. They are disabled when
their corresponding history action is unavailable.

## Tests

New and updated tests cover:

- file-dialog list/tree styling and non-native dialog configuration;
- application startup rendering and high-DPI configuration helpers;
- responsive behavior-checkbox reflow without a vertical scrollbar;
- project JSON round-trip, version validation, and missing-path tolerance;
- active-video switching and segment isolation while retaining `self.records`;
- project save/open and backup retention, debounce, and restore behavior;
- create/update/delete undo and redo, including redo invalidation;
- every finalized shortcut binding and shortcut-help text;
- preservation of accepted post-save field reset behavior;
- regression coverage for existing CSV export and single-video FFmpeg export.

The full pytest suite must pass before requesting manual acceptance.
