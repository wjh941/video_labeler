# Refined Desktop App Visual Design

## Goal

Refine the existing video-first annotation workspace into a more natural,
brand-accented desktop application. The result must feel like one coherent
tool rather than a stack of white group boxes while retaining the current
video-first layout, card ownership, table detach behavior, and all validated
business workflows.

## Scope And Constraints

Only visual presentation, display-only helper state, and visual regression
tests may change. The implementation must not alter:

- `self.records`, active-video bindings, project dirty state, or undo/redo.
- clip refresh rules, annotation editor values, batch operations, filters, or
  table selection signals.
- CSV import/export, project persistence, filename generation, FFmpeg commands,
  export worker behavior, or keyboard shortcuts.
- the video-first layout hierarchy, `QGraphicsView` output, bottom embedded
  task table default, or manual task-table dialog behavior.

No inline QSS may be added to `main_window.py`. Visual values live in
`video_labeler/themes/light_fresh.qss`. This change remains local unless the
user explicitly requests a later push.

## Selected Visual Direction

The selected direction is a restrained, brand-accented video workbench:

- App canvas: `#F3F6FA`, a cool fog-gray rather than a flat white page.
- Primary blue: `#4F97E8` for focus, progress, selected rows, and primary
  actions.
- Secondary blue-green: `#20A39E`, limited to passive supporting status and
  never used as the dominant page color.
- Text: `#253042` for headings and `#5B687A` for normal labels.
- Card backgrounds: near-white `#FCFDFE` with thin `#E5EAF1` borders.

The visual hierarchy is intentionally strongest around the video card:

1. Video card: 14px radius, strongest soft shadow, dark independent player
   surface, a quiet scene overlay before or during media loading, and a
   two-row control panel outside the video picture.
2. Annotation card: 14px radius, medium shadow, generous form spacing, and
   clear content grouping.
3. Task card: 14px radius, medium shadow, dense but comfortable table surface.
4. Toolbar card: 14px radius, light shadow, compact grouped controls.

## Toolbar

The current header remains one card but is reorganized into four compact,
labeled action groups:

- `导入`: import video.
- `CSV`: import CSV and save annotation CSV.
- `导出`: choose output folder and batch export.
- `设置`: shortcut help and existing advanced export settings.

Groups use small all-caps-style Chinese captions, light dividers, and
consistent internal gaps. The batch-export action uses the only subtle
blue-on-blue linear highlight in the interface. Secondary buttons use
near-white backgrounds and a soft blue hover wash.

Long output-folder paths use wrapping rather than text elision.

## Video Player

The existing `QGraphicsView` remains the only player output surface. A
`QGraphicsSimpleTextItem` display overlay is added to the existing scene:

- `导入视频后开始标注` when there is no media.
- `正在加载视频…` while media is loading or buffering.
- hidden once media is loaded, buffered, or playing.

The overlay is positioned at the visible scene center whenever the existing
video item is resized. It never intercepts clicks or changes video playback.

The control section stays below the preview and is divided into:

- transport and clip-boundary controls;
- a compact playback-rate component with a current-rate badge, a preset combo,
  and a custom numeric spin box.

The preset list is exactly `0.25x`, `0.5x`, `0.75x`, `1.0x`, `1.5x`, `2.0x`,
`3.0x`, `4.0x`, and `自定义`. The custom spin box remains `0.1x` through
`4.0x`; Enter and focus loss apply it, and invalid input restores the last
valid rate. This behavior continues to use the existing single
`_apply_playback_rate()` pathway.

Native Qt standard media icons accompany the existing Chinese control text so
tests and accessibility labels remain stable.

## Annotation And Behavior Tags

The annotation form retains every existing widget and binding. Visual changes
only:

- align label and field spacing through current layouts;
- give the collapsible behavior group a soft neutral surface;
- render behavior checkboxes as pill controls with no visible square
  indicator;
- use a pale blue selected pill state with blue text and a quiet focus ring;
- preserve the existing two/three-column responsive grid and full label text.

## Task Table

The task table remains in `task_panel` and uses its existing table object and
signals. The visual structure becomes:

- a compact filter row above the table;
- the table with 34-pixel rows, alternate near-white rows, clearer headers,
  and a soft blue selected-row background;
- a bottom action bar for batch edit, batch delete, and `弹出表格`.

The table dialog uses the same card theme and keeps the same reparenting logic.

## Interaction Feedback

Qt stylesheets provide the static hover/focus/checked palettes. Presentation
helpers attach a 180ms `QPropertyAnimation` to the shadow blur of primary,
transport, clip-boundary, and table-action buttons. Enter raises the shadow
slightly; leave returns it to zero. These helpers must not consume button
events or change existing signal connections.

## Testing

Tests must cover:

1. Semantic object names for each visual group and the required refined-theme
   QSS selectors.
2. The exact revised playback preset list, rate badge synchronization, custom
   input behavior, and invalid-value restoration.
3. The video scene overlay text and its visibility for empty, loading, and
   loaded media states.
4. Card, control, behavior-tag, and table geometry at `1120×720` and
   `1440×900`: text-bearing controls must have width at least their size hint,
   remain inside the containing viewport, and never overlap the video preview.
5. Existing behavior tag grid tests, table detach/restore tests, annotation
   refresh tests, CSV tests, project tests, export tests, and theme tests.

Run the complete verification command:

```powershell
D:\Python311\python.exe -m pytest tests -v
```
