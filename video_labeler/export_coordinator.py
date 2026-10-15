"""导出准备与协调：与 Qt 无关的纯逻辑。

从 MainWindow 的导出流程中抽出的可独立测试规则：
- 导出范围选择结果的解释（全部片段 / 仅导出审核通过 / 取消导出）
- 片段与源视频路径的配对、按审核状态过滤
- 导出质量检查（export_quality_issues）的编排、阻断筛选与文案
- 项目级导出的源收集（含缺失源收集）
- 导出前目标校验（输出目录/重复输出名/非法文件名）
- 导出预览文案与磁盘占用估算

约定：本模块不得导入任何 Qt 类型；QInputDialog/QMessageBox 等交互
由 MainWindow 完成，本模块只做决策与数据组装。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg_service import format_seconds
from .models import ClipRecord
from .naming import validate_output_filename
from .project_io import LabelProject, ProjectVideo
from .project_validation import ValidationIssue, export_quality_issues

EXPORT_SCOPE_ALL = "全部片段"
EXPORT_SCOPE_APPROVED = "仅导出审核通过"
EXPORT_SCOPE_CANCEL = "取消导出"
EXPORT_SCOPE_CHOICES = (EXPORT_SCOPE_ALL, EXPORT_SCOPE_APPROVED, EXPORT_SCOPE_CANCEL)

BLOCKING_ISSUE_PREVIEW_LIMIT = 10


@dataclass(frozen=True)
class ExportScopeDecision:
    """范围选择对话框返回值的解释结果。"""

    canceled: bool
    approved_only: bool


def interpret_export_scope(policy: object, accepted: bool) -> ExportScopeDecision:
    """解释范围选择对话框的返回值；未确认或选择取消时 canceled=True。"""
    if not accepted or policy == EXPORT_SCOPE_CANCEL:
        return ExportScopeDecision(canceled=True, approved_only=False)
    return ExportScopeDecision(
        canceled=False,
        approved_only=(policy == EXPORT_SCOPE_APPROVED),
    )


def select_records_for_scope(
    records: Sequence[ClipRecord],
    input_paths: Sequence[Path],
    *,
    approved_only: bool,
) -> tuple[Sequence[ClipRecord], Sequence[Path]] | None:
    """按导出范围过滤片段并保持 records 与 input_paths 的配对。

    仅导出审核通过且没有已通过片段时返回 None；
    全部片段时原样返回（不复制）。
    """
    if not approved_only:
        return records, input_paths
    selected = [
        (record, path)
        for record, path in zip(records, input_paths)
        if record.review_status == "approved"
    ]
    if not selected:
        return None
    filtered_records, filtered_paths = zip(*selected)
    return list(filtered_records), list(filtered_paths)


def blocking_export_issues(
    project: LabelProject, *, approved_only: bool
) -> list[ValidationIssue]:
    """返回阻断导出的质量问题（仅 error 级；warning 不阻断）。"""
    warnings = export_quality_issues(project, require_approved=approved_only)
    return [issue for issue in warnings if issue.severity == "error"]


def format_blocking_issues(
    issues: Sequence[ValidationIssue], limit: int = BLOCKING_ISSUE_PREVIEW_LIMIT
) -> str:
    """把阻断问题拼成确认框文案，最多展示 limit 条。"""
    return "\n".join(issue.message for issue in issues[:limit])


def collect_project_export_sources(
    videos: Iterable[ProjectVideo],
) -> tuple[list[ClipRecord], list[Path], list[str]]:
    """收集项目内全部片段与对应源路径。

    返回 (records, input_paths, missing_sources)；
    跳过没有片段的视频，源文件缺失的视频记入 missing_sources。
    """
    records: list[ClipRecord] = []
    input_paths: list[Path] = []
    missing_sources: list[str] = []
    for video in videos:
        if not video.segments:
            continue
        if not video.path.is_file():
            missing_sources.append(str(video.path))
            continue
        records.extend(video.segments)
        input_paths.extend([video.path] * len(video.segments))
    return records, input_paths, missing_sources


def ensure_export_targets_ready(
    output_dir: Path, records: Sequence[ClipRecord]
) -> None:
    """校验导出目标可用：创建输出目录并校验输出文件名。

    不通过时抛出 OSError / ValueError，消息与既有 UI 文案一致。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise OSError("输出路径不是文件夹")
    outputs = [record.output.lower() for record in records]
    if len(outputs) != len(set(outputs)):
        raise ValueError("任务列表中包含重复的输出文件名。")
    for record in records:
        validate_output_filename(record.output)


def format_export_size(byte_count: int | None) -> str:
    """把字节数格式化为人类可读大小；无法估算时有专门文案。"""
    if byte_count is None:
        return "无法估算"
    size = float(byte_count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(byte_count)} B"


def estimate_export_bytes(
    records: Sequence[ClipRecord], input_paths: Sequence[Path]
) -> int | None:
    """按源视频平均码率估算导出磁盘占用；无法估算时返回 None。"""
    grouped: dict[Path, list[ClipRecord]] = {}
    for record, source_path in zip(records, input_paths):
        grouped.setdefault(Path(source_path), []).append(record)

    estimated_bytes = 0.0
    has_estimate = False
    for source_path, source_records in grouped.items():
        try:
            source_bytes = source_path.stat().st_size
        except OSError:
            continue
        observed_duration = max(
            record.end_seconds for record in source_records
        )
        selected_duration = sum(
            record.end_seconds - record.start_seconds
            for record in source_records
        )
        if observed_duration <= 0 or selected_duration <= 0:
            continue
        estimated_bytes += source_bytes * selected_duration / observed_duration
        has_estimate = True
    return round(estimated_bytes) if has_estimate else None


def format_export_preview_message(
    records: Sequence[ClipRecord], input_paths: Sequence[Path]
) -> str:
    """组装导出确认框的完整文案（片段数/时长/预计占用）。"""
    total_duration = sum(
        record.end_seconds - record.start_seconds for record in records
    )
    estimate_text = format_export_size(estimate_export_bytes(records, input_paths))
    return (
        f"将导出 {len(records)} 个片段，合计时长 "
        f"{format_seconds(total_duration)}。\n"
        f"预计磁盘占用：{estimate_text}\n"
        "估算按源视频平均码率计算，实际大小会随编码模式变化。\n\n"
        "是否开始导出？"
    )
