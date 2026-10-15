"""片段业务规则：与 Qt 无关的纯逻辑。

从 MainWindow.add_or_update_clip 与审核状态机中抽出的可独立测试规则：
- 片段输入校验（源视频名/时间范围/输出文件名唯一性）
- 片段记录的审计字段回填（annotator / created_at / updated_at）
- 审核状态转移（reviewer / reviewed_at / review_comment / rejection_reason /
  review_history）
- 最近行为标签合并

约定：本模块不得导入任何 Qt 类型；输入输出均为数据对象或标量，
弹窗与控件读取由 MainWindow 负责。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from .models import REVIEW_STATUSES, ClipRecord

RECENT_BEHAVIOR_TAG_LIMIT = 6

_FAST_REVIEW_REJECTION_REASONS = {
    "needs_fix": "快速审核：需修正",
    "rejected": "快速审核：剔除",
}


def utc_now_stamp(now: datetime | None = None) -> str:
    """生成秒级 UTC ISO 时间戳（如 2026-07-29T12:00:00Z），与既有持久化格式一致。"""
    moment = now if now is not None else datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_clip_bounds(
    source_name: str, start_seconds: float, end_seconds: float
) -> str:
    """校验片段基本边界，返回去除首尾空白后的源视频名。

    不通过时抛出 ValueError，消息与既有 UI 文案一致。
    """
    source = source_name.strip()
    if not source:
        raise ValueError("添加片段前请先选择源视频。")
    if end_seconds <= start_seconds:
        raise ValueError("结束时间必须晚于开始时间。")
    return source


def assert_output_is_unique(
    records: Iterable[ClipRecord],
    output: str,
    *,
    editing_index: int | None = None,
) -> None:
    """确保输出文件名（不区分大小写）在片段列表中唯一。

    editing_index 指向的记录（正在编辑的片段自身）豁免；
    重复时抛出 ValueError。
    """
    for index, record in enumerate(records):
        if index != editing_index and record.output.lower() == output.lower():
            raise ValueError(f"输出文件名重复：{output}")


def resolve_annotator(
    previous: ClipRecord | None,
    editor_annotator: str,
    default_annotator: str,
) -> str:
    """标注人取值优先级：沿用上一版本记录 > 编辑器输入 > 默认标注人。"""
    return (
        (previous.annotator if previous is not None else "")
        or editor_annotator
        or default_annotator
    )


def finalize_clip_record(
    record: ClipRecord,
    *,
    previous: ClipRecord | None,
    editor_annotator: str,
    default_annotator: str,
    now_stamp: str,
) -> ClipRecord:
    """按新增/更新语义回填审计字段，原地修改并返回该记录。

    - annotator：沿用上一版本 > 编辑器输入 > 默认标注人
    - created_at：更新时保持首次创建时间，新增时取 now_stamp
    - updated_at：恒为 now_stamp
    """
    record.annotator = resolve_annotator(previous, editor_annotator, default_annotator)
    record.created_at = (
        (previous.created_at if previous is not None else "") or now_stamp
    )
    record.updated_at = now_stamp
    return record


def apply_review_transition(
    record: ClipRecord,
    review_status: str,
    *,
    reviewer: str,
    reviewed_at: str,
    review_comment: str = "",
    rejection_reason: str = "",
    fallback_annotator: str = "",
) -> ClipRecord:
    """将单条片段推进到目标审核状态，原地修改并返回该记录。

    - 置回 pending 时清空 reviewer / reviewed_at / review_comment；
      rejection_reason 始终按入参覆写（与既有行为一致）。
    - updated_at 恒为 reviewed_at。
    - annotator 为空时回填 fallback_annotator。
    - 每次转移向 review_history 追加一条审计记录。
    review_status 不在 REVIEW_STATUSES 内时抛出 ValueError。
    """
    if review_status not in REVIEW_STATUSES:
        raise ValueError("审核状态无效")
    is_pending = review_status == "pending"
    record.review_status = review_status
    record.reviewer = "" if is_pending else reviewer
    record.reviewed_at = "" if is_pending else reviewed_at
    record.review_comment = "" if is_pending else review_comment
    record.rejection_reason = rejection_reason
    record.updated_at = reviewed_at
    if not record.annotator:
        record.annotator = fallback_annotator
    record.review_history.append(
        {
            "status": review_status,
            "reviewer": record.reviewer,
            "reviewed_at": record.reviewed_at,
            "comment": record.review_comment,
            "rejection_reason": record.rejection_reason,
        }
    )
    return record


def fast_review_rejection_reason(review_status: str) -> str:
    """快速审核（数字键 1-4）的内置驳回原因；其余状态为空。"""
    return _FAST_REVIEW_REJECTION_REASONS.get(review_status, "")


def dialog_review_rejection_reason(review_status: str, review_comment: str) -> str:
    """审核对话框路径：needs_fix/rejected 用审核备注作为驳回原因，其余为空。"""
    return review_comment if review_status in {"needs_fix", "rejected"} else ""


def merge_recent_behavior_tags(
    existing: Sequence[str],
    behaviors: Sequence[str],
    limit: int = RECENT_BEHAVIOR_TAG_LIMIT,
) -> tuple[str, ...]:
    """把刚标注的行为标签提到最近使用队列最前，去重并截断到 limit 个。"""
    return tuple(dict.fromkeys((*behaviors, *existing)))[:limit]
