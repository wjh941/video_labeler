# Impeccable Usability Review: Main Window and Timeline

> DEGRADED: single-context (the request limited this run to one sub-agent; Assessment A used one independent agent and Assessment B was completed sequentially by the parent).

## Scope and Method

- Reviewed: `video_labeler/ui/main_window.py` and `video_labeler/segment_timeline.py`.
- Visual reference: `video_labeler/themes/light_fresh.qss` and `video_labeler/themes/__init__.py`.
- Assessment A: independent design/usability review.
- Assessment B: `detect.mjs --json` returned `[]` for the two Python/Qt targets. This is a markup-oriented detector result, not evidence that the native UI has no usability issues.
- Browser visualization and overlay injection were unavailable because this session exposes no browser automation interface. No live server was started.
- No `.impeccable/critique/ignore.md` file exists.
- No product source files were modified during this review.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 3/4 | Export progress, queue state, and logs are clear; filtering gives neither a result count nor an explicit zero-results state. |
| 2 | Match between system and real world | 3/4 | Segment, playback, and export terminology fit the task; advanced export concepts appear before a new user needs them. |
| 3 | User control and freedom | 3/4 | Undo/redo, cancellation, queue visibility, and confirmations are present; timeline edits lack an immediate recovery cue. |
| 4 | Consistency and standards | 3/4 | Qt controls and shared QSS are consistent; the teal timeline interval does not share the blue action language. |
| 5 | Error prevention | 3/4 | Time, filename, duplicate-output, and delete safeguards are strong; the timeline can create a zero-width range before later validation. |
| 6 | Recognition rather than recall | 2/4 | Buttons are labeled, but timeline endpoints do not indicate that they can be dragged. |
| 7 | Flexibility and efficiency | 3/4 | Hotkey rebinding, Shift range selection, batch operations, filters, and table detachment support repeated work. |
| 8 | Aesthetic and minimalist design | 2/4 | Header commands, editor controls, table tools, log, and export controls compete on one scrollable surface. |
| 9 | Error recognition and recovery | 3/4 | Errors are human-readable and preserved in row/log state. |
| 10 | Help and documentation | 2/4 | Welcome and shortcut help exist, but contextual guidance disappears after import. |
| **Total** | | **27/40** | **Acceptable: a capable tool that needs hierarchy and discoverability refinement.** |

## Design Specificity Verdict

The screen is recognizably a video-segment labeling tool: playback, precise time controls, an interval range, a segment queue, and export recovery form a coherent workbench. Its container treatment is still broadly interchangeable with a desktop admin interface. Rounded cards and blue controls do not establish an annotation-specific hierarchy, while the most distinctive control, the draggable timeline range, is visually under-expressed.

The deterministic scan found no rules in the two Qt Python files. It did not contradict the manual findings, but it also cannot assess native widget hierarchy, discoverability, or keyboard accessibility.

## What Works

1. Export communicates risk and progress well: preview, cancellation, project queue, per-item states, and retained errors reduce uncertainty during long jobs. See [main_window.py](../video_labeler/ui/main_window.py:203).
2. High-risk changes have sound guardrails: delete confirmation, undo/redo, range validation, duplicate filename checks, and human-readable error paths are present. See [main_window.py](../video_labeler/ui/main_window.py:3356).
3. Repeated-use foundations are good: configurable hotkeys, Shift selection, batch actions, filters, and a detachable table provide real operating efficiency. See [main_window.py](../video_labeler/ui/main_window.py:1275).

## Priority Findings

### P1: Timeline range dragging is not discoverable

The timeline renders a thin teal interval, while its start/end hit zones are invisible. There are no distinct handles, cursor feedback, boundary labels, or first-use instruction. See [segment_timeline.py](../video_labeler/segment_timeline.py:47) and [segment_timeline.py](../video_labeler/segment_timeline.py:61).

Why it matters: the fastest direct-manipulation adjustment is easy to miss, so users will use spin boxes and treat the timeline as playback-only.

Recommended change: render explicit start/end handles, use resize cursors on hover, and show a concise first-use hint such as "Drag either edge to adjust the segment." Keep spin boxes for exact values.

### P1: Search and filters can make the segment table blank without explanation

Filtering only hides non-matching rows. It provides no "showing N of M" count, zero-result message, or direct reset action within the result area. See [main_window.py](../video_labeler/ui/main_window.py:2955) and [main_window.py](../video_labeler/ui/main_window.py:1334).

Why it matters: an empty table is ambiguous during review. Users cannot tell whether records were removed, the active video has no segments, or the filter worked.

Recommended change: display a compact result count. When no rows match, show an inline zero-results message with a clear-filter command.

### P2: Labeling flow loses hierarchy under command density

Import, CSV save, output choice, two export entry points, queue access, metadata, advanced FFmpeg settings, table tools, and export status remain visible around the primary task. See [main_window.py](../video_labeler/ui/main_window.py:610) and [main_window.py](../video_labeler/ui/main_window.py:1287).

Why it matters: before creating a first segment, a new user must parse many unrelated choices instead of following the intended sequence: find moment, mark range, label, add segment.

Recommended change: keep video import and active-video export available; move project export, queue, CSV save, and advanced settings into a later workflow section or compact overflow. Default the table to review-critical columns and disclose output/error/note detail on demand.

### P2: The custom timeline lacks accessible semantics and keyboard adjustment

The interval widget implements mouse press, move, and release behavior but exposes no accessible name/description or keyboard operation for choosing and nudging a boundary. See [segment_timeline.py](../video_labeler/segment_timeline.py:61).

Why it matters: keyboard-first and screen-reader users cannot discover or operate the direct-manipulation interaction. The spin boxes are a fallback, not equivalent feedback.

Recommended change: add programmatic accessible text, focus behavior, and keyboard commands to select and nudge start/end boundaries.

### P3: Dark mode is not retained between sessions

The runtime action switches the stylesheet, but this preference is not saved like configured hotkeys. See [main_window.py](../video_labeler/ui/main_window.py:775) and [main_window.py](../video_labeler/ui/main_window.py:1671).

Why it matters: users who select dark mode for long labeling sessions must repeat the preference after every restart.

Recommended change: store the selected theme in user preferences and apply it before the main window is shown.

## Persona Red Flags

### Alex, power user

- The timeline's missing handles and hover feedback make the fastest adjustment technique easy to overlook.
- Eleven table columns force horizontal scanning in continuous review; output and error details compete with segment metadata.
- Mitigations already exist: hotkey customization, range selection, batch edit/delete, undo/redo, and export queue state.

### Jordan, first-timer

- The welcome hint disappears immediately after video import, when the next-step reminder is most valuable.
- Import, CSV, two export paths, queue, and FFmpeg settings appear before the user has learned the marking workflow.
- A blank filtered table provides no clear recovery path.

### Sam, accessibility-focused user

- The segment-range interaction is mouse-driven and lacks declared accessible semantics.
- Filter controls have visual labels but no explicit Qt label-buddy or accessible-name evidence in the reviewed targets.
- Human-readable dialogs and the in-app log are positive recovery aids.

## Minor Observations

- The table advertises double-click/edit-key editing, while all columns except output filename are read-only; users can encounter a no-op edit attempt.
- The hard-coded teal interval color is independent of the primary blue interaction system.
- The operation log is useful but collapsed; a one-line recent-activity summary near export status could make feedback easier to notice.

## Questions to Consider

- How can "mark the next reliable segment" become the unmistakable center of the screen?
- Should CSV, queue, project export, and FFmpeg settings stay visible before the first segment exists?
- Which three table columns are indispensable during continuous review, and which should become details on selection?

## Run Notes

- Target slug: `video-labeler-ui-main-window-py`.
- Assessment independence: one independent Assessment A agent, then sequential parent detector assessment, due to the one-agent limit.
- CLI detector: completed with `[]`.
- Browser visibility and overlay injection: unavailable; no browser tool was exposed.
- Live-server and temporary-file cleanup: not applicable; neither was created.
- Questions skipped: the request explicitly required a Markdown report only and to stop after its generation.
