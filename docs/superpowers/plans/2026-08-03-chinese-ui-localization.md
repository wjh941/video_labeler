# Chinese UI Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate every user-facing workflow message in the desktop window to Chinese while preserving English annotation values, CSV data contracts, and export filenames.

**Architecture:** Keep localization scoped to string literals in `MainWindow` and the UI-only `TABLE_COLUMNS` tuple. No models, CSV code, filename code, FFmpeg command construction, or behavior label values change. Add one public-behavior regression test to protect Chinese commands and unchanged English tag values.

**Tech Stack:** Python 3.11, PySide6 6.11, pytest 8.4.

## Global Constraints

- Preserve `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, and `VIEW_TYPES` values exactly.
- Preserve CSV headers `source,start,end,output` exactly.
- Preserve filename format and FFmpeg behavior exactly.
- Translate window chrome, buttons, sections, table columns, dialogs, status text, and error text into concise Chinese.
- Keep technical names `CSV`, `FFmpeg`, and `MP4` visible as written.

---

## File Structure

```text
video_labeler/
  video_labeler/
    ui/
      main_window.py       # User-visible Chinese copy
  tests/
    test_main_window.py    # UI copy and unchanged tag-value regression test
```

### Task 1: Localize Visible UI Copy

**Files:**
- Modify: `tests/test_main_window.py`
- Modify: `video_labeler/ui/main_window.py`

**Interfaces:**
- Consumes: `MainWindow`, `BEHAVIOR_LABELS`, `POLARITIES`, and `LIGHTING_VALUES`.
- Produces: Chinese workflow copy for all MainWindow controls while retaining the English behavior/value strings consumed by clip creation and filename generation.

- [ ] **Step 1: Write the failing UI-copy regression test**

Add this test and import `BEHAVIOR_LABELS`, `POLARITIES`, and `LIGHTING_VALUES` from `video_labeler.models`:

```python
def test_main_window_uses_chinese_workflow_copy_and_keeps_tag_values(qt_app):
    window = MainWindow()

    assert window.windowTitle() == "视频片段标注工具"
    assert window.open_video_button.text() == "导入视频"
    assert window.import_csv_button.text() == "导入 CSV"
    assert window.output_folder_button.text() == "选择输出文件夹"
    assert window.export_button.text() == "批量导出"
    assert window.add_button.text() == "添加片段"
    assert window.cancel_export_button.text() == "取消导出"
    assert window.task_table.horizontalHeaderItem(0).text() == "编号"
    assert window.behavior_checks[BEHAVIOR_LABELS[0]].text() == "strangers_climbs"
    assert window.polarity_combo.itemText(0) == "pos"
    assert window.lighting_combo.itemText(0) == "daytime"
```

This test catches a return to English workflow actions and prevents localization from mutating the annotation values written to filenames.

- [ ] **Step 2: Run the focused test to verify failure**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py::test_main_window_uses_chinese_workflow_copy_and_keeps_tag_values -v
```

Expected: FAIL because the current title, buttons, and table columns are in English.

- [ ] **Step 3: Replace all MainWindow-visible copy with the defined Chinese terms**

In `video_labeler/ui/main_window.py`, replace the visible strings with these values:

```python
TABLE_COLUMNS = (
    "编号", "开始", "结束", "时长", "行为标签",
    "正负例", "光照", "输出文件名", "状态", "错误信息",
)

self.setWindowTitle("视频片段标注工具")
self.open_video_button = QPushButton("导入视频")
self.import_csv_button = QPushButton("导入 CSV")
self.save_csv_button = QPushButton("保存标注 CSV")
self.output_folder_button = QPushButton("选择输出文件夹")
self.export_button = QPushButton("批量导出")
self.cancel_export_button = QPushButton("取消导出")
```

Use the following mapping for all remaining visible text:

```text
Project -> 项目设置                 Export Options -> 导出设置
No output folder selected -> 未选择输出文件夹
Date -> 日期                        Camera -> 摄像头
View -> 视角                        Mode -> 模式
Parallel -> 并行数量                Video Review -> 视频预览
Play -> 播放                        Pause -> 暂停
Set Start -> 设置起始点             Set End -> 设置结束点
Speed -> 播放速度                   Clip Annotation -> 片段标注
No video selected -> 未选择视频     Start -> 起始时间
End -> 结束时间                     Sequence -> 编号
Behaviors -> 行为标签               Polarity -> 正负例
Lighting -> 光照                    Generated filename -> 生成的文件名
Add Clip -> 添加片段                Update Clip -> 更新片段
Remove Selected -> 删除所选         Clear Editor -> 清空编辑区
Clip Tasks -> 片段任务              Ready -> 就绪
```

Translate every `QFileDialog` title and filter label, every `_show_error` title/message, and every `_set_status` message to concise Chinese. Preserve interpolated technical values such as a video filename, output folder path, FFmpeg error text, sequence number, and the literal `FFmpeg` name. For example:

```python
self._set_status(f"已选择视频：{path.name}")
self._set_status(f"已添加片段 {sequence:03d}")
self._show_error("无法导出", "请先选择输出文件夹。")
```

Do not translate `BEHAVIOR_LABELS`, `POLARITIES`, `LIGHTING_VALUES`, `VIEW_TYPES`, CSV headers, output filenames, or the FFmpeg command string.

- [ ] **Step 4: Run focused UI tests**

Run:

```powershell
D:\Python311\python.exe -m pytest tests/test_main_window.py -v
```

Expected: PASS, including filename sequencing, splitter, annotation scroll, action placement, and Chinese-copy coverage.

- [ ] **Step 5: Run full suite and compile check**

Run:

```powershell
D:\Python311\python.exe -m pytest tests -v
D:\Python311\python.exe -m compileall -q app.py video_labeler
```

Expected: all tests pass and compile check returns exit code 0.

- [ ] **Step 6: Commit the localization**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' add -- video_labeler/ui/main_window.py tests/test_main_window.py
& 'C:\Program Files\Git\cmd\git.exe' commit -m "feat: localize annotation UI to Chinese"
```

## Plan Self-Review

Spec coverage:

- Chinese window, command, section, table, dialog, status, and error copy is covered by Task 1 Step 3.
- English label and filename/data constraints are protected by Task 1 Steps 1 and 3.
- Regression verification is covered by Task 1 Steps 4 and 5.

The plan contains no placeholders. It changes only the two files that own visible UI text and its behavior-level regression check.
