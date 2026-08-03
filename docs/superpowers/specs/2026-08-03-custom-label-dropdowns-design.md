# Custom Annotation Dropdowns Design

## Goal

Make the metadata dropdowns practical for long video-labeling sessions by allowing
operators to add a missing value without leaving the application. The new value
must be immediately selected, included in generated filenames, and preserved when
the generated CSV is imported again.

This design supersedes the implementation scope of the earlier `indoor` view
specification. `indoor` remains a built-in view value and is implemented together
with the custom-value behavior.

## Scope

The following dropdowns support a final custom-value action:

- View: built-in values are `panorama`, `closeup`, and `indoor`.
- Polarity: built-in values are `pos` and `neg`.
- Lighting: built-in values are `daytime`, `night_full_color`, and
  `night_black_white`.

Selecting the custom action opens a short text prompt. A valid value is inserted
before the custom action if it is not already present, then becomes the selected
value. If it already exists, it is selected instead. Canceling the prompt or
submitting an invalid value leaves the previous selection unchanged and displays
a Chinese validation message.

The custom action itself is never used in records, CSV data, or filenames.

The export mode dropdown remains restricted to `encode` and `copy`. The playback
speed dropdown remains restricted to its fixed numeric speeds. Neither receives
a custom-value action because their values directly control application behavior.

## Value Rules

All custom values are normalized by trimming surrounding whitespace and converting
to lowercase before validation and storage.

- Custom view values must match `[a-z0-9]+`.
- Custom polarity and lighting values must match `[a-z0-9_]+`.
- Empty values and values containing Chinese characters, spaces, punctuation, or
  other symbols are rejected.

The stricter view rule deliberately excludes underscores. A filename stores its
camera and view together as `camera_view`, and camera names may contain
underscores. Restricting custom view tokens makes this boundary unambiguous.

Behavior labels remain the existing fixed English multi-select preset list. They
are not made customizable in this change.

## Naming And Import Behavior

The filename format remains:

`date-camera_view-behavior1+behavior2-polarity-lighting-sequence.mp4`

Existing built-in filenames stay valid. Custom polarity and lighting tokens that
meet their rules are valid in filename generation and parsing. `parse_filename`
will split `camera_view` at its final underscore and validate the resulting view
token, which supports custom views while retaining cameras such as `cam_01`.

On loading a selected record or importing a CSV, any valid non-built-in view,
polarity, or lighting value is added to the matching dropdown before it is
selected. This preserves prior project metadata and enables editing an imported
record. Custom options do not persist globally between fresh application
launches; CSV import restores the values needed for that project.

## UI And Error Handling

The UI remains Chinese except for stored label tokens. The custom menu entry,
prompt title, prompt description, and validation feedback are Chinese. Existing
dropdown selections are never replaced with invalid values.

Validation remains centralized with filename/domain validation rather than relying
only on UI checks. This means manually entered metadata, generated names, CSV
imports, and later code paths use the same constraints.

## Verification

Tests will cover:

- `indoor` is a built-in view option.
- Valid built-in and custom view, polarity, and lighting values build and parse
  filenames.
- Invalid custom-token shapes are rejected by the shared validation rules.
- A custom value can be registered in each editable dropdown and is selected.
- Loading/importing a record with valid custom metadata restores those values in
  the dropdowns.
- The mode and speed dropdowns retain only their fixed options.

## Self-Review

The feature is limited to metadata values that are safe to store in the current
filename format. It avoids altering FFmpeg controls, CSV column layout, behavior
presets, output sequencing, or global configuration. The parsing rule and the
custom view restriction are aligned, so camera names containing underscores remain
unambiguous.
