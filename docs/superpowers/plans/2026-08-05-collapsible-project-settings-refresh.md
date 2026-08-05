# Collapsible Project Settings And Partial Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project settings card collapsible and make custom behavior-tag additions refresh only the approved editor fields.

**Architecture:** Reuse `CollapsibleGroupBox` for the existing `project_header` instead of adding a new controller or data model. Keep custom tag persistence unchanged; the UI refresh path will snapshot and restore start/end, lighting, and polarity while rebuilding only the behavior controls.

**Tech Stack:** Python 3.11, PySide6, pytest, Qt QSS.

## Global Constraints

- Do not change CSV headers, segment fields, `.labelproj` schema, FFmpeg commands, or export-worker behavior.
- Keep all existing buttons and `S`/`E` player-position shortcuts functional.
- Keep the light fresh QSS theme and existing responsive video-first layout.
- Push only after all tests pass; do not merge or create a pull request.

---

### Task 1: Collapsible Project Settings Card

**Files:**
- Modify: `video_labeler/ui/main_window.py:445-580`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `CollapsibleGroupBox.set_content(content: QWidget)`.
- Produces: `MainWindow.project_header`, an expanded `CollapsibleGroupBox` with all existing toolbar and metadata controls inside its content widget.

- [ ] **Step 1: Write the failing test**

```python
def test_project_settings_card_is_expanded_and_collapsible(qt_app):
    window = MainWindow()

    assert isinstance(window.project_header, CollapsibleGroupBox)
    assert window.project_header.isChecked()
    assert window.project_header.content_widget is window.project_settings_content
    assert window.open_video_button.parentWidget() is not window.project_header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "project_settings_card_is_expanded_and_collapsible"`

Expected: FAIL because `project_header` is still a plain `QGroupBox`.

- [ ] **Step 3: Write minimal implementation**

```python
group = CollapsibleGroupBox("项目设置")
group.setObjectName("toolbarCard")
self.project_settings_content = QWidget()
content_layout = QVBoxLayout(self.project_settings_content)
# Move the existing toolbar, metadata, and export-settings widgets into
# content_layout without changing button creation or signal connections.
group_layout = QVBoxLayout(group)
group_layout.addWidget(self.project_settings_content)
group.set_content(self.project_settings_content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "project_settings_card_is_expanded_and_collapsible"`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "feat: collapse project settings card"
```

### Task 2: Custom-Tag Partial Refresh

**Files:**
- Modify: `video_labeler/ui/main_window.py:1874-1887`
- Modify: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `MainWindow.add_custom_behavior_tag()`, `set_clip_range(start: float, end: float)`, and `_rebuild_behavior_controls(selected: Collection[str])`.
- Produces: custom-tag additions that redraw start/end and behavior controls while preserving `polarity_combo` and `lighting_combo`.

- [ ] **Step 1: Write the failing test**

```python
def test_adding_custom_tag_partially_refreshes_only_editor_fields(
    qt_app, monkeypatch
):
    window = MainWindow()
    window.set_clip_range(12.5, 18.75)
    window.polarity_combo.setCurrentText("neg")
    window.lighting_combo.setCurrentText("night_full_color")
    window.custom_behavior_tag_edit.setText("delivery_dropoff")
    refreshed_ranges = []
    original_set_range = window.set_clip_range

    monkeypatch.setattr(
        window,
        "set_clip_range",
        lambda start, end: (
            refreshed_ranges.append((start, end)),
            original_set_range(start, end),
        )[1],
    )

    window.add_custom_behavior_tag()

    assert refreshed_ranges == [(12.5, 18.75)]
    assert "delivery_dropoff" in window.behavior_checks
    assert window.polarity_combo.currentText() == "neg"
    assert window.lighting_combo.currentText() == "night_full_color"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "adding_custom_tag_partially_refreshes_only_editor_fields"`

Expected: FAIL because the current method rebuilds behavior controls without explicitly refreshing the time editor.

- [ ] **Step 3: Write minimal implementation**

```python
start_seconds = self.start_spin.value()
end_seconds = self.end_spin.value()
polarity = self.polarity_combo.currentText()
lighting = self.lighting_combo.currentText()
self.project.custom_behavior_tags.append(normalized)
self._rebuild_behavior_controls(selected)
self.set_clip_range(start_seconds, end_seconds)
self.polarity_combo.setCurrentText(polarity)
self.lighting_combo.setCurrentText(lighting)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `D:\Python311\python.exe -m pytest tests/test_main_window.py -v -k "adding_custom_tag_partially_refreshes_only_editor_fields"`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add video_labeler/ui/main_window.py tests/test_main_window.py
git commit -m "fix: refresh custom tag editor fields"
```

### Task 3: Verification And Delivery

**Files:**
- Modify: no source files expected

**Interfaces:**
- Consumes: complete working tree from Tasks 1 and 2.
- Produces: tested local commits pushed to `origin/feature/video-segment-labeler-zh`.

- [ ] **Step 1: Run complete verification**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
D:\Python311\python.exe -m compileall -q app.py video_labeler
git diff --check
```

Expected: all tests pass, compilation exits zero, and diff check reports no errors.

- [ ] **Step 2: Push the branch**

```powershell
git push origin feature/video-segment-labeler-zh
```

Expected: the feature branch is updated on `origin`; do not merge or create a pull request.

- [ ] **Step 3: Clean only project-owned, regenerable cache files**

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ |
    Remove-Item -Recurse -Force
Remove-Item -LiteralPath .pytest_cache -Recurse -Force -ErrorAction SilentlyContinue
```

Expected: only Python bytecode and pytest cache generated inside this project are
removed. Do not touch the Recycle Bin, user documents, system directories, or
installed applications.
