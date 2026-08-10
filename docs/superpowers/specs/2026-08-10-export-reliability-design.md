# Export Reliability and Project Data Design

## Status

Approved for implementation.

## Goal

Make video segment data durable, traceable, and safe to export in batches
without changing the existing annotation taxonomy or generated filename format.

The implementation must:

- Preserve compatibility with the existing four-column CSV files.
- Persist complete clip labels and export state without inferring them from a
  filename.
- Make cancellation stop active FFmpeg work and leave no completed-looking
  partial output.
- Validate an exported media file before treating it as successful.
- Keep default resource use reasonable on typical desktop machines.

## Scope

This work covers project persistence, CSV compatibility, export validation,
process cancellation, and export concurrency.

It does not add multi-video project editing, configurable taxonomies,
frame-step controls, thumbnails, waveform views, or UI localization. Those
are separate user-facing workflow changes.

## Data Model

### Project Manifest

Add a versioned JSON project manifest. It stores:

- `version`
- The absolute source video path selected for the project.
- The output directory, when selected.
- Project metadata: date, camera, and view.
- A list of clip records.

Each persisted clip record stores its source value, start and end seconds,
output filename, behaviors, polarity, lighting, sequence, status, and error.

The manifest is the authoritative format for reopening an in-progress project.
It uses a version field so future migrations can be explicit.

### CSV

Continue to read the existing CSV contract:

```text
source,start,end,output
```

When writing CSV, include the existing fields plus explicit optional fields:

```text
source,start,end,output,behaviors,polarity,lighting,sequence,status,error
```

The CSV reader accepts either shape. For legacy rows, labels are inferred from
standard output filenames when possible. For extended rows, explicit values
take precedence and are validated independently. This prevents custom output
filenames from discarding label data during a round trip.

## Export Behavior

### Preflight

Before an export starts, validate:

- A source video exists and is a regular file.
- An output directory is selected and writable.
- Every clip ends after it starts.
- Output filenames are valid and unique case-insensitively.

The application remains a single-source batch exporter. Imported CSV rows with
different `source` values may be reviewed and saved, but export is refused
unless every row identifies the selected source video filename. This makes the
existing single-source limitation explicit and prevents accidental mixed-source
exports.

### Temporary Files and Validation

Each FFmpeg job writes to a unique sibling temporary file ending in
`.part.mp4`. The final output path is not replaced until:

1. FFmpeg exits with a zero status.
2. The temporary file exists and exceeds the existing minimum-size threshold.
3. `ffprobe` reports at least one video stream.
4. The reported duration is positive and within a bounded tolerance of the
   requested segment duration.

After validation, the temporary file is atomically renamed to the requested
output path. A failed or canceled job removes its temporary file. Existing
valid final files retain the current skip/overwrite behavior.

### Cancellation

Replace blocking FFmpeg execution with a managed process. The export worker
tracks active FFmpeg processes. When the user requests cancellation:

- No queued clips are submitted.
- Active FFmpeg processes are terminated.
- Their results are reported as `canceled`.
- Queued clips are reported as `canceled`.
- Temporary output files are removed.

The UI continues to show progress until every active job has returned.

### Concurrency

The automatic worker setting uses a conservative default of two concurrent
jobs. The user can still choose a worker count explicitly. This avoids
oversubscribing CPU and disk bandwidth because each FFmpeg encoder may itself
use multiple threads.

## UI Changes

Add project actions for saving and reopening the JSON manifest. Maintain the
existing annotation workflow and table layout.

Before starting export, show a clear error if imported rows refer to more than
one source video or do not match the selected source. Export status text and
the table continue to expose `queued`, `ok`, `skip`, `fail`, and `canceled`.

## Error Handling

- A missing `ffprobe` executable blocks export with an actionable message.
- Unreadable or malformed manifests report the file and validation error.
- A failed validation reports the FFmpeg or ffprobe reason in the task table
  and failed report.
- Legacy CSV remains importable even when its filename does not encode labels.

## Test Plan

Add focused automated tests for:

- Manifest write/read round trips and malformed manifest rejection.
- Extended CSV label round trips and legacy CSV compatibility.
- Rejection of mixed-source batches before FFmpeg starts.
- Temporary file command targets and atomic finalization behavior.
- ffprobe validation success, missing video stream, invalid duration, and
  missing executable behavior.
- Canceling an active managed FFmpeg process and cleanup of its temporary
  output.
- Automatic export concurrency defaulting to two.

Keep existing filename, CSV, command-construction, export-summary, and UI
tests passing.

## Acceptance Criteria

- A custom output filename does not erase labels after CSV export and import.
- A saved manifest restores the selected source, project metadata, clips, and
  their labels.
- A mixed-source CSV cannot accidentally export all rows from one selected
  source video.
- A canceled export leaves no final output for a canceled clip and no
  `.part.mp4` files.
- A zero-exit FFmpeg process is not marked successful until ffprobe confirms a
  usable video output with a plausible duration.
- `workers=0` schedules no more than two concurrent jobs.
