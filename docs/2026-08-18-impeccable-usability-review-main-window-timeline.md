⚠️ DEGRADED: constrained sequential (the user limited this review to at most one sub-agent; Assessment A used one independent sub-agent, then Assessment B ran in the parent context after it completed).

# Impeccable Usability Review

**Scope:** `video_labeler/ui/main_window.py`, `video_labeler/segment_timeline.py`<br>
**Mode:** Operate, native PySide6 desktop application<br>
**Target slug:** `i-main-window-py-video-labeler-segment-timeline-py`

## Design Health Score

| # | Heuristic | Score | Key issue |
| --- | --- | --- | --- |
| 1 | Visibility of system status | 3/4 | Player placeholders, export progress, queue, status label, and log are visible; per-item activity is well retained. |
| 2 | Match system / real world | 3/4 | Chinese task language and media controls map well to annotation work, but `encode`, `copy`, and FFmpeg options need more explanation. |
| 3 | User control and freedom | 2/4 | Undo, redo, cancellation, and discard confirmation exist, but batch editing clears the active undo history. |
| 4 | Consistency and standards | 3/4 | Components and terminology are consistent; the teal timeline range does not belong to the blue interaction color system. |
| 5 | Error prevention | 3/4 | Time range, duplicate-output, deletion, export, backup, and project-save guardrails are strong. |
| 6 | Recognition rather than recall | 2/4 | Text controls help, but the timeline's draggable edges have no visible handle or instruction after video import. |
| 7 | Flexibility and efficiency | 3/4 | Configurable shortcuts, frame stepping, filtering, multi-select, and batch edit support repeated work; adding the prepared clip still needs a pointer trip. |
| 8 | Aesthetic and minimalist design | 2/4 | The workbench is useful but the expanded project header and nested cards keep too many unrelated choices visible. |
| 9 | Error recovery | 3/4 | Dialogs, status, logs, queue persistence, and export reports preserve recovery information; missing-media recovery is indirect. |
| 10 | Help and documentation | 2/4 | A welcome hint and shortcut reference exist, but the core marking and review sequence lacks contextual teaching. |
| **Total** |  | **26/40** | **Acceptable: meaningful workflow improvements are still needed.** |

## Design Specificity Verdict

The layout is clearly a video-segment labeling tool: it combines a video canvas, precise timestamps, a task table, project-wide export, and a timeline interval. The visual language itself is still category-interchangeable. Repeated white cards, blue actions, borders, and shadows could serve a generic desktop admin tool; the teal timeline interval is the only distinctive element, and it is visually disconnected from the rest of the interaction system.

The deterministic detector found no rule violations in either target: `[]`. It therefore neither adds findings nor contradicts the design assessment.

## Overall Impression

This is a capable, reliable workstation with strong export-state visibility and a solid foundation for power users. Its main weakness is focus: after importing a video, the user sees project setup, media controls, interval editing, labels, table management, and export affordances at once. The highest-value improvement is to make the next annotation the unmistakable primary task.

## What's Working

- The video canvas, exact time controls, frame stepping, and Set Start/Set End actions provide more than one way to mark a precise interval. See `video_labeler/ui/main_window.py:850`.
- Configurable shortcuts, multi-row table selection, filtering, batch edit, and whole-project export establish a credible expert workflow. See `video_labeler/ui/main_window.py:1251` and `video_labeler/ui/main_window.py:1638`.
- Export is treated as a real operation, with preflight checks, visible progress, cancellation, a project queue, per-item logging, and retained failures. See `video_labeler/ui/main_window.py:3248` and `video_labeler/ui/main_window.py:3321`.

## Priority Issues

### [P1] The active workspace presents too many unrelated decisions

**Why it matters:** The expanded project header, metadata, export controls, video controls, interval editor, label selector, task table, filters, batch actions, log, and export status compete at the same time. A first-time annotator has to infer the sequence rather than being led through it.

**Evidence:** `video_labeler/ui/main_window.py:607`, `video_labeler/ui/main_window.py:920`, `video_labeler/ui/main_window.py:1237`.

**Fix:** After a source video is selected, collapse project and export setup into a compact status strip. Give the central workflow a stronger sequence: mark interval, choose labels, add segment. Keep batch and export affordances on demand.

**Suggested command:** `$impeccable layout`

### [P1] Batch edit removes the undo safety net

**Why it matters:** Batch edit affects multiple labels and output names, but `_apply_batch_edit` clears history after committing. The highest-impact mass change is therefore harder to reverse than a single-record change.

**Evidence:** `video_labeler/ui/main_window.py:2929`, `video_labeler/ui/main_window.py:3069`.

**Fix:** Push the complete before/after record lists as one undoable history entry. Sorting or batch editing should not erase existing recovery affordances.

**Suggested command:** `$impeccable harden`

### [P2] Timeline interval boundaries are not discoverable or accessible

**Why it matters:** The range is a 6px teal bar with an implicit 10px edge hit zone. It has no start/end handles, labels, hover signal, keyboard adjustment, or explicit accessible description. Users who do not discover the interaction must fall back to spin boxes; keyboard-only and screen-reader users have no equivalent direct manipulation path.

**Evidence:** `video_labeler/segment_timeline.py:47`, `video_labeler/segment_timeline.py:61`, `video_labeler/segment_timeline.py:77`.

**Fix:** Render visible start/end handles and timestamp labels, add hover/focus feedback, expose a keyboard adjustment path, and assign an accessible name/description that explains the interaction.

**Suggested command:** `$impeccable adapt`

### [P2] The visual system is too card-heavy and has competing selection colors

**Why it matters:** Repeated borders and drop shadows make routine production work feel less dense and less scannable. Blue establishes the system action color, while the range bar is teal without a stated semantic role.

**Evidence:** `video_labeler/ui/main_window.py:550`, `video_labeler/segment_timeline.py:54`, `video_labeler/themes/light_fresh.qss:111`.

**Fix:** Reserve elevation for modals and important state changes; simplify routine panels into a denser workbench. Use the established blue interaction color for the timeline, or document a distinct semantic teal role consistently.

**Suggested command:** `$impeccable quieter`

### [P2] Contextual assistance stops at the first successful import

**Why it matters:** The welcome hint establishes the first step, but disappears after importing the video. That is when users need to understand range adjustment, behavior classification, pre-annotation review, and the distinction between current-video and whole-project export.

**Evidence:** `video_labeler/ui/main_window.py:715`, `video_labeler/ui/main_window.py:1850`, `video_labeler/ui/main_window.py:2206`.

**Fix:** Keep a compact, contextual next-step hint in the empty annotation/table state, and attach short explanations to the timeline and advanced export controls.

**Suggested command:** `$impeccable onboard`

## Persona Red Flags

### Alex, Power User

Alex can set boundaries using `S` and `E`, but cannot commit the prepared segment through a shortcut; the repeated loop ends with a mouse trip to Add Segment. Batch edit then clears the undo history, making rapid correction risky. See `video_labeler/ui/main_window.py:1638`, `video_labeler/ui/main_window.py:959`, and `video_labeler/ui/main_window.py:3069`.

### Jordan, First-Timer

Jordan loses the introductory instruction immediately after video import, exactly when the workflow becomes more complex. The behavior control summarizes chosen tags as a count rather than revealing the active taxonomy, so a novice must infer what is currently selected. See `video_labeler/ui/main_window.py:715`, `video_labeler/ui/main_window.py:1850`, and `video_labeler/ui/main_window.py:364`.

### Sam, Accessibility-Dependent User

The custom timeline boundary operation is pointer-only and has no explicit accessibility metadata. The reviewed targets contain no `setAccessibleName` or `setAccessibleDescription`; muted instructional text uses `#86909c`, which also warrants contrast verification in the actual target environment. See `video_labeler/segment_timeline.py:61` and `video_labeler/themes/light_fresh.qss:17`.

## Minor Observations

- After a video is imported, the empty task table has no task-specific empty state or next action. See `video_labeler/ui/main_window.py:1237`.
- Ten fixed table columns exceed the minimum window width; detaching the table is a workaround, not an adaptive default. See `video_labeler/ui/main_window.py:1278` and `video_labeler/ui/main_window.py:1347`.
- Collapsible label group titles that surface the selected polarity and lighting are a useful recognition cue. See `video_labeler/ui/main_window.py:1199`.

## Questions to Consider

- What would the interface look like if the center of the screen optimized only for marking the next reliable segment?
- Can export become a final review state rather than a permanent competing action cluster?
- Which actions should remain visible after an operator has successfully labeled their first ten clips?

## Run Notes

- Target slug: `i-main-window-py-video-labeler-segment-timeline-py`.
- Ignore list: none found at `.impeccable/critique/ignore.md`.
- Assessment independence: Assessment A ran in one isolated sub-agent; Assessment B began only after it completed.
- CLI detector: completed once with both targets; zero findings (`[]`).
- Browser visibility and overlay injection: skipped because no browser automation tool is available in this native-PySide6 session.
- Live-server and temporary-file cleanup: not applicable; neither was created.
- Questions skipped: the user requested a file-only report and instructed execution to stop after the report was generated.
