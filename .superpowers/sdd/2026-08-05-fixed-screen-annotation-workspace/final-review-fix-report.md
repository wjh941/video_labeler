# Final Review Fix Report

## Red Test

Command:

```text
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "collapsing_task_table_releases_right_pane_height_after_loading_source or lighting_and_polarity_titles_summarize_selected_values" -q
```

Expected failure observed before the production fix: the collapsed task panel
remained 320 pixels high and extended outside the 459-pixel annotation
workspace; the lighting title remained `光照条件` rather than showing its
selected value.

Output:

```text
FF                                                                       [100%]
================================== FAILURES ===================================
_ test_collapsing_task_table_releases_right_pane_height_after_loading_source __

E       assert False
E        +  where False = <built-in method contains of PySide6.QtCore.QRect object at 0x...>(PySide6.QtCore.QRect(0, 235, 518, 320))
E        +    where <built-in method contains of PySide6.QtCore.QRect object at 0x...> = PySide6.QtCore.QRect(0, 0, 518, 459).contains

_________ test_lighting_and_polarity_titles_summarize_selected_values _________

E       AssertionError: assert '光照条件' == '光照条件：night_full_color'
E         - 光照条件：night_full_color
E         + 光照条件

=========================== short test summary info ===========================
FAILED tests/test_main_window.py::test_collapsing_task_table_releases_right_pane_height_after_loading_source
FAILED tests/test_main_window.py::test_lighting_and_polarity_titles_summarize_selected_values
2 failed, 96 deselected in 0.44s
```

## Files Changed

- `video_labeler/ui/main_window.py`
- `tests/test_main_window.py`

## Implementation

- Removed the static outer 320-pixel task-panel minimum.
- Kept a 280-pixel content minimum whenever the task table is expanded, and
  restore it after its existing expand animation completes.
- Updated lighting and polarity group titles with concise Chinese summaries of
  their current selected values.
- Added regressions for collapsed source-loaded layout and selected-value
  summaries. The animation helper now waits for the group under test.

## Verification

Focused command:

```text
D:\Python311\python.exe -m pytest tests/test_main_window.py -k "collapsing_task_table_releases_right_pane_height_after_loading_source or lighting_and_polarity_titles_summarize_selected_values or task_table_receives_remaining_right_pane_height" -q
```

Output:

```text
...                                                                      [100%]
3 passed, 95 deselected in 0.70s
```

Complete main-window suite:

```text
D:\Python311\python.exe -m pytest tests/test_main_window.py -q
```

Output:

```text
........................................................................ [ 73%]
..........................                                               [100%]
98 passed in 6.15s
```

`git diff --check` completed with no output.

## Commit

`fe5e4a9129aa586c0a07b62aa44e9a290d7ef648` (`fix: compact collapsed annotation task panel`)

## Concerns

- The worktree has a pre-existing untracked `.superpowers/brainstorm/`
  directory. It was not modified or staged.
- The `pytest` console entry point did not add the worktree to `sys.path`; all
  recorded test runs use `D:\Python311\python.exe -m pytest`.
