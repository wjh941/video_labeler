# Dark Workspace UI Design

## Status

Approved visual direction: dark workstation with resizable panes.

## Problem

The current window uses pale application, group, and input backgrounds at the
same time. The visual hierarchy is weak, controls appear washed out, and the
full-height layout compresses the video, annotation editor, and task table on
smaller screens.

## Goal

Make the application easy to scan during long annotation sessions:

- Make every selectable control visible against its background.
- Keep the video, annotation controls, and task list usable in a 1366x768
  desktop window.
- Allow the user to resize the workspace and scroll dense controls without
  hiding important actions.
- Preserve existing video, CSV, filename, and export behavior.

## Layout

Use a three-part workstation:

1. A compact top toolbar for project inputs and primary file actions.
2. A vertical splitter beneath the toolbar.
3. An upper horizontal splitter inside the vertical splitter.

The upper horizontal splitter contains:

- A video review area on the left.
- A scrollable clip annotation panel on the right.

The lower vertical splitter pane contains the task table. It keeps its native
vertical and horizontal scrolling. The user can drag the splitters to favor
video review or task inspection without making the whole window taller.

The project toolbar uses one compact action row and one compact metadata row.
FFmpeg path, export mode, overwrite, and worker count move into an "Export
Options" collapsible panel so they do not compete with high-frequency
annotation controls.

## Visual System

Use a dark neutral base with restrained functional accent colors:

- Application background: charcoal `#111827`.
- Surface background: dark slate `#18212d`.
- Raised control background: `#253244`.
- Input background: `#101923`.
- Primary text: `#f1f5f9`.
- Secondary text: `#a8b3c2`.
- Border: `#334155`.
- Focus and primary action: blue `#2563eb`.
- Add clip action and successful status: teal `#0f9f8c`.
- Warning and skip status: amber `#d39b2a`.
- Error and delete action: red `#dc4c64`.

The selected table row uses a muted blue fill with high-contrast text.
Inputs, combo boxes, checkboxes, and table headers use visible borders and
clear hover and focus states. Controls keep 4-6 pixel corners and compact,
stable heights.

## Interaction and Density

- Keep Open Video, Import CSV, Save CSV, Output Folder, and Batch Export
  visible at all times.
- Keep date, camera, and view type visible in the metadata row.
- Keep clip start, end, sequence, polarity, lighting, and Add Clip visible
  near the top of the right panel.
- Put the behavior checkboxes in a labeled scroll area with a fixed preferred
  height; use two compact columns to reduce vertical scrolling.
- Show the generated filename in a single-line, selectable preview below the
  label inputs.
- Make the task table the lower workspace pane with a 26-pixel row height.
- Keep task table status colors visible but do not rely on color alone; the
  status text remains present.
- Use tooltips for less obvious controls and avoid explanatory paragraphs in
  the application itself.

## Component Changes

`video_labeler/ui/main_window.py` will:

- Replace the outer vertical layout with a compact toolbar and vertical
  `QSplitter`.
- Wrap the clip editor in a `QScrollArea`.
- Replace the single-column behavior list with a two-column grid inside that
  scroll area.
- Move advanced export controls into a checkable `QGroupBox`.
- Apply the dark palette and explicit component-level styles.
- Adjust table column widths, row height, header style, and status colors for
  the dark surface.
- Preserve the existing public UI fields used by tests and the CSV/export
  signal wiring.

## Error Handling

The visual update must not change validation behavior. File, CSV, FFmpeg, and
time-range errors continue to use the current dialog and status label. Error
dialogs and progress states must inherit the dark palette and retain readable
text.

## Verification

Automated checks:

- Existing UI behavior test still adds sequential tasks and expected output
  names.
- New UI test confirms the annotation editor is scrollable and the main
  workspace uses a vertical splitter.

Manual checks:

- Launch at 1366x768 and confirm all primary file actions, metadata inputs,
  player controls, and Add Clip are visible.
- Resize the vertical and horizontal splitters.
- Scroll the annotation editor and task list independently.
- Confirm selected checkbox, input focus, table selection, queued, successful,
  skipped, failed, and canceled states remain readable.
