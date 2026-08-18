⚠️ DEGRADED: single-context (the single allowed sub-agent did not return before timeout)

# MainWindow Usability Review

**Target:** `video_labeler/ui/main_window.py`<br>
**Mode:** Operate, native PySide6 desktop application<br>
**Scope:** Current Chinese UI, including the project-wide export queue, quick-start hint, temporary-file recovery prompt, and error feedback.

## Design Health Score

| # | Heuristic | Score | Key issue |
| --- | --- | ---: | --- |
| 1 | Visibility of System Status | 3 | Export progress, queue rows, status text, and cancellation are visible; readiness before export is still distributed across several controls. |
| 2 | Match System / Real World | 3 | Chinese workflow labels are clear, but `encode`, `copy`, FFmpeg, FFprobe, and parallelism still assume production-video knowledge. |
| 3 | User Control and Freedom | 3 | Undo/redo, deletion confirmation, export cancellation, backups, and a persistent in-session queue are present; failed queue items lack a direct retry/reveal action. |
| 4 | Consistency and Standards | 3 | Light theme, button treatments, tables, dialogs, and status vocabulary are consistent; the export controls compete for attention in one header strip. |
| 5 | Error Prevention | 3 | Filename validation, duplicate-output checks, missing-source checks, confirmations, and safe temporary publication are strong; export choices are not explained before commitment. |
| 6 | Recognition Rather Than Recall | 3 | Labeled actions, shortcut hint, filename preview, queue table, and welcome hint reduce recall; advanced export mode meaning is not visible at the decision point. |
| 7 | Flexibility and Efficiency | 3 | Playback/edit/save shortcuts, batch editing, multi-source export, and in-session queue retention support repeated work; queue recovery remains pointer-heavy. |
| 8 | Aesthetic and Minimalist Design | 2 | The work surface is orderly, but the top project header presents too many equal-weight export and file actions before the user has a video or a valid clip. |
| 9 | Error Recovery | 3 | Permission guidance, per-item queue errors, preserved records, and failed-report export give useful recovery evidence; users still must manually translate an error into the next corrective action. |
| 10 | Help and Documentation | 3 | README, shortcut dialog, and quick-start hint exist; contextual help for encoding modes and queue failures is still thin. |
| **Total** |  | **29/40** | **Good: strong operational foundation, with focused workflow and recovery improvements needed.** |

## Design Specificity Verdict

The layout is authored for video-segment labeling: the video preview, start/end controls, behavioral tags, filename preview, segment table, and project-wide export queue form a coherent task flow. The surface is nonetheless visually close to a generic Ant-style internal tool: white cards, blue primary buttons, and dense toolbar groups could be transplanted into another operations product without much change.

The strongest product-specific improvement is the queue monitor: it turns cross-source export into a visible operational state rather than a background action. The weakest moment is still the header, where importing, exporting, output destination, whole-project export, queue viewing, and settings arrive with similar visual weight.

## Deterministic and Visual Evidence

- Impeccable detector: `0` findings; `[]` returned for `video_labeler/ui/main_window.py`.
- Native offline captures: checked at `1440x900` and the stated minimum `1120x720`. Main panels and header controls rendered without detected overlap in these captures.
- Capture caveat: the offscreen Qt font stack replaced Chinese glyphs with boxes, so screenshots were used only for geometry, hierarchy, and clipping evidence, not typography or copy quality.
- Browser overlay: not applicable. The target is a native PySide6 window, not a browser surface.

## Overall Impression

This now feels like a capable desktop annotation tool rather than a simple clip cutter. The new queue, safeguards, and quick-start hint improve confidence at the important moments. The next meaningful gain is not more controls: it is making the existing export controls read as a short sequence and giving failed queue rows an immediate recovery path.

## What's Working

- **Task-specific operating surface.** The preview/editor/table arrangement and generated output naming make the annotation objective legible without a separate navigation model.
- **Export status is materially better.** Project-wide export populates queue items, refreshes each item on completion, and preserves the dialog state for the rest of the application session (`main_window.py:2687`, `2736`, `2759`, `2780`).
- **Recovery is safer and clearer.** The startup temporary-file discovery asks for consent; permission failures are translated into a concrete next step instead of exposing raw exceptions (`main_window.py:2804`, `2814`).

## Priority Issues

### [P1] Failed project-wide queue rows do not provide a direct recovery action

**Why it matters:** The queue dialog shows source, output, status, and error, but an operator with twenty failed clips must close the dialog, locate the right video, inspect the source, and restart manually. This is the highest-friction state in a long export.

**Fix:** Add row actions or a contextual menu for `Retry failed`, `Open source location`, and `Reveal output folder`. Keep the current result table as the durable in-session record, but make recovery one action rather than a multi-screen investigation.

**Suggested command:** `$impeccable harden`

### [P2] Export actions are over-concentrated in the project header

**Why it matters:** The same action group contains output-folder selection, current-video export, whole-project export, and queue viewing (`main_window.py:656-660`). Before any source is loaded, that is four decisions plus import and settings actions. The screenshot confirms that they fit at minimum width, but fitting is not the same as establishing priority.

**Fix:** Keep one primary export action appropriate to the current context. Move whole-project export and queue viewing into a compact export menu or reveal them after a project contains clips; keep the output folder visible as state rather than as a peer command.

**Suggested command:** `$impeccable distill`

### [P2] FFmpeg mode choices are still unexplained at the point of use

**Why it matters:** `encode`, `copy`, FFmpeg, FFprobe, and parallelism appear in advanced settings but the user must know their speed, compatibility, and accuracy tradeoffs. First-time users can make a valid but unsuitable export choice.

**Fix:** Add short inline descriptions beside `encode` and `copy`, with a recommended default: for example, `encode: accurate cuts, slower` and `copy: faster, cuts may start on keyframes`. Explain that Auto uses the conservative worker count.

**Suggested command:** `$impeccable clarify`

### [P2] Accessibility metadata and dynamic announcements are not explicit

**Why it matters:** Keyboard shortcuts and visible focus styles are present, but the custom video surface, dynamic export state, and queue updates do not declare accessible names/descriptions or a screen-reader announcement strategy. A keyboard-only or screen-reader user may not receive completion, failure, or cancellation feedback reliably.

**Fix:** Set accessible names/descriptions for video, timeline, queue controls, and advanced export fields. Announce queue-progress and terminal export state through an accessible status label; add keyboard-focused tests for opening and navigating the queue.

**Suggested command:** `$impeccable audit`

### [P3] The quick-start hint names the flow but does not explain the first decision

**Why it matters:** The new empty-project hint is concise and correctly hidden after video import (`main_window.py:676-681`, `1635-1636`), but it does not explain why the user must choose metadata before adding a clip or where that metadata appears in the output.

**Fix:** Keep the hint short, but make the first action a clickable `导入视频` command and add one sentence that metadata drives the generated filename.

**Suggested command:** `$impeccable onboard`

## Persona Red Flags

**Alex, power user:** Shortcuts, batch editing, and project-wide export are useful improvements. Alex still cannot keyboard-open the queue, filter it to failed items, or retry selected failures; long exports become a manual recovery exercise.

**Jordan, first-timer:** The welcome hint gives an immediate path, and visible Chinese labels reduce ambiguity. Jordan still has no in-context explanation for `encode` versus `copy`, and sees export commands before the application can establish whether a source, clip, or output folder is ready.

**Sam, accessibility-dependent:** Text buttons, focus styling, status text, and a table-backed queue are positive. The custom video surface and status changes have no explicit accessible descriptions or announcement contract, making dynamic export feedback uncertain for assistive technology.

## Minor Observations

- The modal queue monitor is useful while exporting, but no persistent indicator in the main window says that a completed queue remains available to reopen.
- The queue table preserves source names rather than full paths, which is compact but can be ambiguous when projects contain duplicate filenames in different folders.
- Queue tests cover item status and completion state; they do not yet cover a long queue, a repeated cancellation request, or keyboard navigation in the dialog.
- The light theme has consistent borders, focus color, and table states, but its generic white-card vocabulary provides limited visual differentiation between setup, annotation, and export phases.

## Questions to Consider

- Should the export destination feel like a final phase reached after the queue is ready, rather than a peer of importing and annotation?
- When an export fails, can the user recover from the queue row without having to reconstruct its context elsewhere?
- What is the smallest amount of encoding guidance that prevents a first-time user from choosing the wrong mode?

## Run Notes

- Target slug: `video-labeler-ui-main-window-py`.
- Ignore list: none found.
- Assessment independence: degraded; the one permitted sub-agent was stopped after timing out, so design assessment and evidence synthesis were completed sequentially in this context.
- CLI detector: completed once, zero findings.
- Browser visibility and overlay injection: not applicable to the native PySide6 target.
- Native evidence: offscreen captures completed at two desktop sizes; Chinese glyph fallback limited typography assessment.
- Temporary screenshot cleanup: completed.
- Report persistence: written directly to this requested Markdown artifact; no `.impeccable` snapshot was created.
