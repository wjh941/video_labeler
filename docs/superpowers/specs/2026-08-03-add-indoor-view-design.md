# Indoor View Option Design

## Goal

Add `indoor` as a third selectable view value alongside `panorama` and `closeup`.

## Scope

- Extend the shared `VIEW_TYPES` tuple to include `indoor`.
- Let the existing view combo box expose the new value automatically.
- Preserve `panorama` and `closeup` unchanged.
- Let the existing filename builder and CSV import/export behavior accept and retain `indoor` without special-case logic.

## Constraints

- The stored and exported value is the lowercase English token `indoor`.
- No change to behavior labels, polarity, lighting, CSV headers, or FFmpeg behavior.
- Generated filenames use the existing format, for example:
  `20260729-cam02_indoor-dog_out-pos-night_full_color-001.mp4`.

## Verification

- Add a regression test proving `indoor` is included in `VIEW_TYPES`.
- Add or extend a filename test to prove `indoor` is accepted and preserved in generated output.

## Self-Review

This is a single shared-domain-value change. It does not introduce new UI or naming logic, so the existing combo-box, CSV parsing, and filename builder remain the only consumers.
