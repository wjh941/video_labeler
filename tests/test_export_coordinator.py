"""export_coordinator 纯逻辑的直接单测（不依赖 Qt）。

覆盖从 MainWindow 导出流程中提炼出的规则：
- 导出范围解释（全部/仅审核通过/取消）
- 按审核状态过滤并保持 records 与路径配对
- 质量问题阻断筛选与文案
- 项目级导出源收集
- 导出目标校验与大小估算
"""

from pathlib import Path

import pytest

from video_labeler.export_coordinator import (
    blocking_export_issues,
    collect_project_export_sources,
    ensure_export_targets_ready,
    estimate_export_bytes,
    format_blocking_issues,
    format_export_preview_message,
    format_export_size,
    interpret_export_scope,
    select_records_for_scope,
)
from video_labeler.models import ClipRecord
from video_labeler.project_io import (
    ProjectVideo,
    add_or_activate_video,
    new_project,
)
from video_labeler.project_validation import ValidationIssue


def _record(output="clip.mp4", review_status="pending", **overrides) -> ClipRecord:
    fields = dict(
        source="source.mp4",
        start_seconds=1.0,
        end_seconds=3.0,
        output=output,
        review_status=review_status,
    )
    fields.update(overrides)
    return ClipRecord(**fields)


def test_interpret_export_scope_covers_all_dialog_outcomes():
    all_clips = interpret_export_scope("全部片段", True)
    assert (all_clips.canceled, all_clips.approved_only) == (False, False)
    decision = interpret_export_scope("仅导出审核通过", True)
    assert (decision.canceled, decision.approved_only) == (False, True)
    canceled = interpret_export_scope("取消导出", True)
    assert (canceled.canceled, canceled.approved_only) == (True, False)
    dismissed = interpret_export_scope("全部片段", False)
    assert (dismissed.canceled, dismissed.approved_only) == (True, False)


def test_select_records_for_scope_filters_approved_and_keeps_pairing():
    records = [
        _record(output="a.mp4", review_status="approved"),
        _record(output="b.mp4", review_status="pending"),
        _record(output="c.mp4", review_status="approved"),
    ]
    paths = [Path("/src/one.mp4"), Path("/src/two.mp4"), Path("/src/three.mp4")]

    kept, kept_paths = select_records_for_scope(
        records, paths, approved_only=True
    )
    assert [r.output for r in kept] == ["a.mp4", "c.mp4"]
    assert kept_paths == [Path("/src/one.mp4"), Path("/src/three.mp4")]

    # 无审核通过片段 → None（由调用方报"没有已审核片段"）
    assert select_records_for_scope(
        [_record(output="b.mp4", review_status="pending")],
        [Path("/src/two.mp4")],
        approved_only=True,
    ) is None

    # 全部片段 → 原样返回
    assert select_records_for_scope(records, paths, approved_only=False) == (
        records,
        paths,
    )


def test_blocking_export_issues_reports_only_errors_and_includes_unapproved_scope(tmp_path):
    project = new_project()
    existing = add_or_activate_video(project, tmp_path / "existing.mp4")
    existing.segments.append(_record(output="ok.mp4", review_status="approved"))
    existing.metadata["duration"] = 100.0

    # 源文件不存在 → error 级阻断
    blocking = blocking_export_issues(project, approved_only=False)
    assert [issue.code for issue in blocking] == ["missing_source"]
    assert all(issue.severity == "error" for issue in blocking)

    # warning 级（未通过审核）永远不进入阻断列表
    (tmp_path / "existing.mp4").write_bytes(b"x")
    try:
        assert blocking_export_issues(project, approved_only=False) == []
        pending_project = new_project()
        other = add_or_activate_video(pending_project, tmp_path / "existing.mp4")
        other.segments.append(_record(output="ok.mp4", review_status="pending"))
        other.metadata["duration"] = 100.0
        assert blocking_export_issues(pending_project, approved_only=True) == []
    finally:
        (tmp_path / "existing.mp4").unlink(missing_ok=True)


def test_format_blocking_issues_joins_messages_with_limit():
    issues = [
        ValidationIssue("missing_source", f"视频源不存在: {index}", severity="error")
        for index in range(15)
    ]
    text = format_blocking_issues(issues)
    assert len(text.splitlines()) == 10
    assert text.splitlines()[0] == "视频源不存在: 0"
    assert format_blocking_issues([]) == ""


def test_collect_project_export_sources_skips_empty_and_collects_missing():
    missing_video = ProjectVideo(
        id="v-missing",
        path=Path("Z:/nowhere/gone.mp4"),
        segments=[_record(output="gone.mp4", source="gone.mp4")],
    )
    empty_video = ProjectVideo(id="v-empty", path=Path("Z:/nowhere/empty.mp4"))
    present_video = ProjectVideo(
        id="v-present",
        path=Path(__file__),  # 任意真实存在的文件
        segments=[
            _record(output="a.mp4", source="src.mp4"),
            _record(output="b.mp4", source="src.mp4"),
        ],
    )
    records, paths, missing = collect_project_export_sources(
        [missing_video, empty_video, present_video]
    )
    assert [r.output for r in records] == ["a.mp4", "b.mp4"]
    assert paths == [present_video.path, present_video.path]
    assert missing == [str(missing_video.path)]


def test_ensure_export_targets_ready_creates_dir_and_rejects_bad_outputs(tmp_path):
    output_dir = tmp_path / "nested" / "exports"
    ensure_export_targets_ready(
        output_dir, [_record(output="a.mp4"), _record(output="b.mp4")]
    )
    assert output_dir.is_dir()

    with pytest.raises(ValueError, match="任务列表中包含重复的输出文件名"):
        ensure_export_targets_ready(
            output_dir, [_record(output="a.mp4"), _record(output="A.MP4")]
        )
    with pytest.raises(ValueError, match="invalid Windows characters"):
        ensure_export_targets_ready(output_dir, [_record(output="bad/name.mp4")])
    # 输出目录指向一个已存在的文件 → Windows 上 mkdir 抛 FileExistsError(OSError)
    with pytest.raises(OSError):
        file_target = tmp_path / "a_file"
        file_target.write_bytes(b"x")
        ensure_export_targets_ready(file_target, [_record(output="a.mp4")])


def test_estimate_export_bytes_and_preview_message(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"x" * 4096)  # 4096 字节，时长 4 秒
    records = [
        _record(output="a.mp4", start_seconds=0.0, end_seconds=2.0),
        _record(output="b.mp4", start_seconds=2.0, end_seconds=4.0),
    ]
    assert estimate_export_bytes(records, [source, source]) == 4096

    # 源文件不可统计 → 无法估算
    assert estimate_export_bytes(records, [tmp_path / "gone.mp4"] * 2) is None
    assert format_export_size(None) == "无法估算"
    assert format_export_size(512) == "512 B"
    assert format_export_size(2048) == "2.0 KB"

    message = format_export_preview_message(records, [source, source])
    assert "2 个片段" in message
    assert "预计磁盘占用" in message
    assert "4.0 KB" in message
    assert message.endswith("是否开始导出？")
