"""clip_rules 纯业务规则的直接单测（不依赖 Qt）。

覆盖从 MainWindow 既有行为中提炼出的规则：
- 片段输入校验与输出文件名唯一性
- 新增/更新片段的审计字段回填
- 审核状态转移（含置回 pending 与非法状态）
- 快速审核/对话框审核的驳回原因映射
- 最近行为标签合并
"""

from datetime import datetime, timezone

import pytest

from video_labeler.clip_rules import (
    apply_review_transition,
    assert_output_is_unique,
    dialog_review_rejection_reason,
    fast_review_rejection_reason,
    finalize_clip_record,
    merge_recent_behavior_tags,
    resolve_annotator,
    utc_now_stamp,
    validate_clip_bounds,
)
from video_labeler.models import ClipRecord


def _record(**overrides) -> ClipRecord:
    fields = dict(
        source="source.mp4",
        start_seconds=1.0,
        end_seconds=2.0,
        output="clip.mp4",
    )
    fields.update(overrides)
    return ClipRecord(**fields)


def test_validate_clip_bounds_rejects_missing_source_and_bad_range():
    with pytest.raises(ValueError, match="添加片段前请先选择源视频"):
        validate_clip_bounds("   ", 1.0, 2.0)
    with pytest.raises(ValueError, match="结束时间必须晚于开始时间"):
        validate_clip_bounds("a.mp4", 2.0, 2.0)
    with pytest.raises(ValueError, match="结束时间必须晚于开始时间"):
        validate_clip_bounds("a.mp4", 3.0, 1.0)
    assert validate_clip_bounds("  a.mp4  ", 1.0, 2.0) == "a.mp4"


def test_assert_output_is_unique_is_case_insensitive_and_exempts_editing_index():
    records = [_record(output="a.mp4"), _record(output="B.MP4")]
    assert_output_is_unique(records, "c.mp4")  # 无冲突，不抛
    assert_output_is_unique(records, "b.mp4", editing_index=1)  # 编辑中的记录豁免
    with pytest.raises(ValueError, match="输出文件名重复：A.MP4"):
        assert_output_is_unique(records, "A.MP4")


def test_finalize_clip_record_new_vs_update_audit_fields():
    now = utc_now_stamp(datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc))
    assert now == "2026-07-29T12:00:00Z"

    fresh = _record()
    finalize_clip_record(
        fresh,
        previous=None,
        editor_annotator="zhang",
        default_annotator="sys",
        now_stamp=now,
    )
    assert fresh.annotator == "zhang"
    assert fresh.created_at == now
    assert fresh.updated_at == now

    # 更新路径：annotator/created_at 沿用上一版本，updated_at 刷新
    previous = _record(annotator="wang", created_at="2020-01-01T00:00:00Z")
    updated = _record()
    finalize_clip_record(
        updated,
        previous=previous,
        editor_annotator="zhang",
        default_annotator="sys",
        now_stamp=now,
    )
    assert updated.annotator == "wang"
    assert updated.created_at == "2020-01-01T00:00:00Z"
    assert updated.updated_at == now

    # 编辑器输入为空时回落到默认标注人（MainWindow 传入前已 strip）
    blank = _record()
    finalize_clip_record(
        blank,
        previous=None,
        editor_annotator="",
        default_annotator="sys",
        now_stamp=now,
    )
    assert blank.annotator == "sys"
    assert resolve_annotator(None, "", "sys") == "sys"


def test_apply_review_transition_approval_sets_fields_and_appends_history():
    record = _record()
    apply_review_transition(
        record,
        "approved",
        reviewer="local-user",
        reviewed_at="2026-07-29T12:00:00Z",
        review_comment="ok",
        fallback_annotator="zhang",
    )
    assert record.review_status == "approved"
    assert record.reviewer == "local-user"
    assert record.reviewed_at == "2026-07-29T12:00:00Z"
    assert record.review_comment == "ok"
    assert record.updated_at == record.reviewed_at
    assert record.annotator == "zhang"  # 空标注人回填
    assert record.review_history[-1] == {
        "status": "approved",
        "reviewer": "local-user",
        "reviewed_at": "2026-07-29T12:00:00Z",
        "comment": "ok",
        "rejection_reason": "",
    }


def test_apply_review_transition_back_to_pending_clears_reviewer_fields():
    record = _record(
        review_status="approved",
        reviewer="local-user",
        reviewed_at="2026-07-29T12:00:00Z",
        review_comment="ok",
        annotator="zhang",
    )
    apply_review_transition(
        record,
        "pending",
        reviewer="local-user",
        reviewed_at="2026-07-30T00:00:00Z",
        rejection_reason="重新标注后待复核",
    )
    assert record.review_status == "pending"
    assert record.reviewer == ""
    assert record.reviewed_at == ""
    assert record.review_comment == ""
    # rejection_reason 按入参覆写（与既有行为一致）
    assert record.rejection_reason == "重新标注后待复核"
    assert record.updated_at == "2026-07-30T00:00:00Z"
    assert record.annotator == "zhang"  # 已有标注人不被覆盖
    assert record.review_history[-1]["status"] == "pending"


def test_apply_review_transition_rejects_unknown_status_without_mutation():
    record = _record(review_status="pending")
    with pytest.raises(ValueError, match="审核状态无效"):
        apply_review_transition(
            record,
            "unknown",
            reviewer="local-user",
            reviewed_at="2026-07-29T12:00:00Z",
        )
    assert record.review_status == "pending"
    assert record.review_history == []


def test_fast_and_dialog_rejection_reason_mapping():
    assert fast_review_rejection_reason("needs_fix") == "快速审核：需修正"
    assert fast_review_rejection_reason("rejected") == "快速审核：剔除"
    assert fast_review_rejection_reason("approved") == ""
    assert fast_review_rejection_reason("pending") == ""
    assert dialog_review_rejection_reason("rejected", "光线不足") == "光线不足"
    assert dialog_review_rejection_reason("needs_fix", " 目标太小 ") == " 目标太小 "
    assert dialog_review_rejection_reason("approved", "ok") == ""


def test_merge_recent_behavior_tags_dedupes_keeps_order_and_limit():
    merged = merge_recent_behavior_tags(("fall", "dog_out"), ("cat_come", "fall"))
    assert merged == ("cat_come", "fall", "dog_out")
    # 超出上限时截断，保留最新使用的一批
    assert merge_recent_behavior_tags(tuple("abcdef"), tuple("ghijkl")) == (
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
    )
    assert merge_recent_behavior_tags(("fall",), ()) == ("fall",)
    assert merge_recent_behavior_tags((), ()) == ()
