from collections.abc import Callable, Collection, Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QItemSelectionModel,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Property,
    QSignalBlocker,
    QSizeF,
    Signal,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..csv_io import (
    read_clip_csv,
    read_full_clip_csv,
    write_clip_csv,
    write_full_clip_csv,
)
from ..project_validation import validate_project, export_quality_issues
from ..project_statistics import calculate_project_statistics
from ..report_io import write_project_statistics_report
from ..builtin_exporters import register_builtin_exporters
from ..plugin_api import list_exporters, load_plugin_file, load_plugin_directory, get_exporter, export_with
from ..project_v2 import load_project_v2, save_project_v2
from ..media_locator import relocate_media_paths
from ..dataset_io import write_clip_jsonl, write_clip_yolo
from ..export_worker import ExportSummary, ExportWorker
from ..ffmpeg_service import (
    cleanup_orphaned_temporary_outputs,
    find_orphaned_temporary_outputs,
    format_seconds,
    probe_media_metadata,
    resolve_ffmpeg,
    resolve_ffprobe,
)
from ..frame_cache import FrameCache
from ..history import SegmentHistory
from ..models import (
    AGE_LABELS,
    AGE_VALUES,
    BEHAVIOR_LABELS,
    FAMILIARITY_LABELS,
    FAMILIARITY_VALUES,
    LIGHTING_VALUES,
    POLARITIES,
    REVIEW_STATUS_LABELS,
    STRATUM_LABELS,
    STRATUM_VALUES,
    VIEW_TYPES,
    ClipRecord,
    EventRecord,
    ProjectMetadata,
)
from ..naming import (
    ParsedFilename,
    build_filename,
    next_sequence,
    normalize_label_token,
    normalize_view_token,
    parse_filename,
    validate_output_filename,
)
from ..project_io import (
    LabelProject,
    ProjectVideo,
    add_or_activate_video,
    create_backup,
    create_version_snapshot,
    list_version_snapshots,
    load_export_queue_state,
    load_project,
    load_tag_preset,
    new_project,
    restore_version_snapshot,
    save_export_queue_state,
    save_project as write_label_project,
    save_tag_preset,
)
from ..preannotation_io import PreAnnotation, read_preannotation_json
from ..preferences_io import (
    DEFAULT_HOTKEYS,
    default_preferences_path,
    load_hotkey_preferences,
    save_hotkey_preferences,
)
from ..segment_timeline import SegmentTimelineSlider
from ..themes import apply_dark_fresh_theme, apply_light_fresh_theme


TABLE_COLUMNS = (
    "编号",
    "开始",
    "结束",
    "时长",
    "行为标签",
    "正负性",
    "光照",
    "输出文件名",
    "状态",
    "错误信息",
    "备注",
    "分层",
)
CUSTOM_OPTION_TEXT = "自定义..."
CUSTOM_PLAYBACK_RATE_TEXT = "自定义"
PLAYBACK_RATE_PRESETS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
STATUS_LABELS = {
    "queued": "排队中",
    "ok": "成功",
    "skip": "已跳过",
    "fail": "失败",
    "canceled": "已取消",
}
SHORTCUT_HELP_ROWS = (
    ("Space", "播放或暂停"),
    ("A", "上一帧"),
    ("D", "下一帧"),
    ("S", "设置起始点"),
    ("E", "设置结束点"),
    ("Del", "删除选中片段"),
    ("Ctrl+Z", "撤销片段操作"),
    ("Ctrl+Y", "重做片段操作"),
    ("Ctrl+S", "保存标注工程 (*.labelproj)"),
)
HOTKEY_ACTION_LABELS = {
    "play_pause": "Play or pause",
    "previous_frame": "Previous frame",
    "next_frame": "Next frame",
    "set_start": "Set start",
    "set_end": "Set end",
    "delete_selected": "Delete selected segment",
    "undo": "Undo segment change",
    "redo": "Redo segment change",
    "save_project": "Save project",
}


class CollapsibleGroupBox(QGroupBox):
    animation_duration_ms = 300
    _UNRESTRICTED_HEIGHT = 16777215

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self._content: QWidget | None = None
        self._content_animation: QPropertyAnimation | None = None
        self._chevron_rotation = 90.0
        self._animation = QParallelAnimationGroup(self)
        self._chevron_animation = QPropertyAnimation(
            self, b"chevronRotation", self
        )
        self._chevron_animation.setDuration(self.animation_duration_ms)
        self._chevron_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.addAnimation(self._chevron_animation)
        self._animation.finished.connect(self._finish_content_animation)
        self.toggled.connect(self._animate_content)

    def set_content(self, content: QWidget) -> None:
        self._content = content
        content.setVisible(self.isChecked())
        content.setMaximumHeight(self._UNRESTRICTED_HEIGHT)
        self.chevronRotation = 90.0 if self.isChecked() else 0.0
        self._content_animation = QPropertyAnimation(
            content, b"maximumHeight", self
        )
        self._content_animation.setDuration(self.animation_duration_ms)
        self._content_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.insertAnimation(0, self._content_animation)

    @Property(float)
    def chevronRotation(self) -> float:
        return self._chevron_rotation

    @chevronRotation.setter
    def chevronRotation(self, value: float) -> None:
        self._chevron_rotation = value
        self.update()

    @property
    def chevron_rotation(self) -> float:
        return self._chevron_rotation

    def _animate_content(self, expanded: bool) -> None:
        if self._content is None or self._content_animation is None:
            return

        self._animation.stop()
        if expanded:
            self._content.setVisible(True)
            self._content.setMinimumHeight(0)
            start_height = 0
            target_height = max(
                self._content.sizeHint().height(),
                self._content.minimumSizeHint().height(),
            )
            self._content.setMaximumHeight(start_height)
        else:
            self._content.setMinimumHeight(0)
            start_height = max(
                self._content.height(),
                self._content.sizeHint().height(),
            )
            target_height = 0

        self._content_animation.setStartValue(start_height)
        self._content_animation.setEndValue(target_height)
        self._chevron_animation.setStartValue(self._chevron_rotation)
        self._chevron_animation.setEndValue(90.0 if expanded else 0.0)
        self._animation.start()

    def _finish_content_animation(self) -> None:
        if self._content is None:
            return
        if self.isChecked():
            self._content.setMaximumHeight(self._UNRESTRICTED_HEIGHT)
            self._content.setMinimumHeight(self._content.sizeHint().height())
            self._content.updateGeometry()
        else:
            self._content.setVisible(False)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.palette().color(QPalette.ColorRole.Highlight))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.translate(15, 11)
        painter.rotate(self._chevron_rotation)
        painter.drawLine(-3, -5, 3, 0)
        painter.drawLine(3, 0, -3, 5)


class BehaviorTagComboBox(QComboBox):
    """A compact, checkable tag picker that retains multi-tag selection."""

    selectionChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("behaviorTagCombo")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("请选择行为标签")
        self.lineEdit().installEventFilter(self)
        model = QStandardItemModel(self)
        model.dataChanged.connect(self._on_model_data_changed)
        self.setModel(model)
        self.view().setMinimumWidth(240)
        self.view().pressed.connect(self._toggle_index)

    def set_tags(
        self,
        tags: Collection[str],
        selected: Collection[str],
    ) -> None:
        selected_tags = set(selected)
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        model.clear()
        for tag in tags:
            item = QStandardItem(tag)
            item.setData(tag, Qt.ItemDataRole.UserRole)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if tag in selected_tags
                else Qt.CheckState.Unchecked
            )
            model.appendRow(item)
        self.setMaxVisibleItems(max(1, model.rowCount()))
        self.setCurrentIndex(-1)
        self._update_summary()

    def checked_tags(self) -> tuple[str, ...]:
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        return tuple(
            str(item.data(Qt.ItemDataRole.UserRole))
            for row in range(model.rowCount())
            if (item := model.item(row)).checkState()
            == Qt.CheckState.Checked
        )

    def set_tag_checked(self, tag: str, checked: bool) -> None:
        index = self.findData(tag)
        if index < 0:
            return
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        item = model.item(index)
        target_state = (
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        if item.checkState() == target_state:
            return
        item.setCheckState(target_state)

    def _toggle_index(self, index) -> None:
        if not index.isValid():
            return
        model = self.model()
        assert isinstance(model, QStandardItemModel)
        item = model.item(index.row())
        self.set_tag_checked(
            str(item.data(Qt.ItemDataRole.UserRole)),
            item.checkState() != Qt.CheckState.Checked,
        )
        QTimer.singleShot(0, self.showPopup)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.lineEdit()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            self.showPopup()
            return True
        return super().eventFilter(watched, event)

    def _on_model_data_changed(self, _top_left, _bottom_right, roles) -> None:
        if roles and Qt.ItemDataRole.CheckStateRole not in roles:
            return
        self._update_summary()
        self.selectionChanged.emit()

    def _update_summary(self) -> None:
        selected_tags = self.checked_tags()
        if not selected_tags:
            self.setEditText("请选择行为标签")
            return
        preview = "、".join(selected_tags[:3])
        suffix = f" 等 {len(selected_tags)} 项" if len(selected_tags) > 3 else ""
        self.setEditText(f"已选 {len(selected_tags)} 项：{preview}{suffix}")


class ProjectExportQueueDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("全工程导出队列")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.cancel_button = QPushButton("取消全部")
        self.cancel_button.setEnabled(False)
        controls.addWidget(self.progress_bar, stretch=1)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ("编号", "视频源", "输出文件", "状态", "错误")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

    def set_items(self, items: Sequence[tuple[Path, ClipRecord]]) -> None:
        self.table.setRowCount(len(items))
        for index, (source_path, record) in enumerate(items):
            self.table.setItem(index, 0, QTableWidgetItem(str(index + 1)))
            self.table.setItem(index, 1, QTableWidgetItem(source_path.name))
            self.table.setItem(index, 2, QTableWidgetItem(record.output))
            self.update_item(index, record)
        self.set_progress(0, len(items))

    def update_item(self, index: int, record: ClipRecord) -> None:
        self.table.setItem(
            index,
            3,
            QTableWidgetItem(STATUS_LABELS.get(record.status, record.status)),
        )
        self.table.setItem(index, 4, QTableWidgetItem(record.error))

    def set_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[ClipRecord] = []
        self.project: LabelProject = new_project()
        self._project_path: Path | None = None
        self._project_dirty = False
        self._active_video_histories: dict[str, SegmentHistory] = {}
        self._backup_timer = QTimer(self)
        self._backup_timer.setSingleShot(True)
        self._backup_timer.setInterval(30_000)
        self._backup_timer.timeout.connect(self._write_automatic_backup)
        self.source_path: Path | None = None
        self.source_name = ""
        self.output_dir: Path | None = None
        self._editing_index: int | None = None
        self._export_worker: ExportWorker | None = None
        self._export_records: list[ClipRecord] = []
        self._export_record_states: list[tuple[str, str]] = []
        self._project_export_queue: list[tuple[Path, ClipRecord]] = []
        self._is_project_export = False
        register_builtin_exporters()
        self.frame_cache = FrameCache(max_bytes=64 * 1024 * 1024)
        self._hotkey_preferences_path = default_preferences_path()
        self.hotkey_bindings = load_hotkey_preferences(
            self._hotkey_preferences_path
        )
        self._last_playback_rate = 1.0
        self._button_hover_effects: dict[
            QPushButton, QGraphicsDropShadowEffect
        ] = {}
        self._button_hover_animations: dict[
            QPushButton, QPropertyAnimation
        ] = {}
        self._button_press_animations: dict[QPushButton, QPropertyAnimation] = {}
        self._utility_shortcuts: list[QShortcut] = []
        self.historical_behavior_tags: tuple[str, ...] = ()
        self._last_annotation_labels: tuple[tuple[str, ...], str, str] = ((), "", "")
        self._review_mode = False
        self._remember_last_labels = False
        self.historical_tag_labels: dict[str, QLabel] = {}

        self.setWindowTitle("视频片段标注工具")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)

        self._build_ui()
        self.project_queue_dialog = ProjectExportQueueDialog(self)
        self.project_queue_dialog.cancel_button.clicked.connect(self.cancel_export)
        self._build_project_menu()
        self._connect_signals()
        self._update_filename_preview()
        self._update_history_controls()
        self._update_welcome_hint()

    def _build_ui(self) -> None:
        self.workspace_content = QWidget()
        self.workspace_content.setObjectName("workspaceContent")
        self.workspace_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.page_layout = QVBoxLayout(self.workspace_content)
        self.page_layout.setContentsMargins(14, 12, 14, 12)
        self.page_layout.setSpacing(10)

        self.project_header = self._build_project_header()
        self.page_layout.addWidget(self.project_header)

        self.workspace_row = QWidget()
        self.workspace_row.setObjectName("workspaceRow")
        workspace_layout = QHBoxLayout(self.workspace_row)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(12)

        self.video_panel = self._build_video_panel()
        self.video_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.annotation_workspace = QWidget()
        self.annotation_workspace.setObjectName("annotationWorkspace")
        self.annotation_workspace.setMinimumWidth(420)
        self.annotation_workspace.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.annotation_workspace_layout = QVBoxLayout(
            self.annotation_workspace
        )
        self.annotation_workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.annotation_workspace_layout.setSpacing(10)

        self.annotation_panel = self._build_clip_editor()
        self.annotation_panel.setObjectName("annotationCard")
        self.task_panel = self._build_task_table()
        self.task_panel.setObjectName("taskCard")
        self.task_panel._animation.finished.connect(
            self._restore_task_table_content_minimum
        )
        self.annotation_workspace_layout.addWidget(self.annotation_panel)

        # Keep the reference layout's most useful principle: video remains
        # permanently visible while the annotation side has more working width.
        workspace_layout.addWidget(self.video_panel, 11)
        workspace_layout.addWidget(self.annotation_workspace, 13)

        self.task_table_dialog = QDialog(self)
        self.task_table_dialog.setWindowTitle("片段任务")
        self.task_table_dialog.setObjectName("taskTableDialog")
        self.task_table_dialog.setModal(False)
        self.task_table_dialog.setMinimumSize(900, 500)
        self.task_table_dialog.setLayout(QVBoxLayout())
        self.task_table_dialog.finished.connect(self._restore_task_panel)

        self.page_layout.addWidget(self.workspace_row)
        self.page_layout.addWidget(self.task_panel)
        self.operation_log_group = self._build_log_panel()
        self.page_layout.addWidget(self.operation_log_group)
        self.page_layout.addLayout(self._build_export_status())

        for card in (
            self.project_header,
            self.video_panel,
            self.annotation_panel,
            self.task_panel,
            self.operation_log_group,
        ):
            self._apply_card_shadow(card)
        self._install_presentation_button_effects()

        self.main_content_scroll = QScrollArea()
        self.main_content_scroll.setObjectName("mainContentScroll")
        self.main_content_scroll.setWidgetResizable(True)
        self.main_content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_content_scroll.setWidget(self.workspace_content)
        self.setCentralWidget(self.main_content_scroll)

    def _apply_card_shadow(self, widget: QWidget) -> None:
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(24)
        effect.setOffset(0, 4)
        effect.setColor(QColor(37, 48, 66, 32))
        widget.setGraphicsEffect(effect)

    def _install_presentation_button_effects(self) -> None:
        """Add subtle elevation feedback without changing button behavior."""
        for button in (
            self.open_video_button,
            self.import_csv_button,
            self.save_csv_button,
            self.output_folder_button,
            self.export_button,
            self.project_export_button,
            self.project_queue_button,
            self.shortcut_help_button,
            self.play_button,
            self.seek_back_button,
            self.seek_forward_button,
            self.set_start_button,
            self.set_end_button,
            self.quick_add_button,
            self.add_button,
            self.remove_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.batch_edit_button,
            self.batch_delete_button,
            self.detach_table_button,
        ):
            self._attach_button_hover_effect(button)

    def _attach_button_hover_effect(self, button: QPushButton) -> None:
        if button in self._button_hover_effects:
            return
        effect = QGraphicsDropShadowEffect(button)
        effect.setBlurRadius(0)
        effect.setOffset(0, 2)
        effect.setColor(QColor(79, 151, 232, 54))
        animation = QPropertyAnimation(effect, b"blurRadius", button)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        button.setGraphicsEffect(effect)
        button.installEventFilter(self)
        self._button_hover_effects[button] = effect
        self._button_hover_animations[button] = animation
        press = QPropertyAnimation(effect, b"blurRadius", button)
        press.setDuration(150)
        press.setEasingCurve(QEasingCurve.Type.OutBack)
        self._button_press_animations[button] = press

    def _animate_button_press(self, button: QPushButton, pressed: bool) -> None:
        """Give physical press feedback without fighting the layout manager."""
        effect = self._button_hover_effects.get(button)
        animation = self._button_press_animations.get(button)
        if effect is None or animation is None:
            return
        animation.stop()
        animation.setStartValue(effect.blurRadius())
        animation.setEndValue(19 if pressed else 10)
        animation.start()

    def _animate_button_hover(self, button: QPushButton, target_blur: float) -> None:
        effect = self._button_hover_effects[button]
        animation = self._button_hover_animations[button]
        animation.stop()
        animation.setStartValue(effect.blurRadius())
        animation.setEndValue(target_blur)
        animation.start()

    def _build_project_header(self) -> QGroupBox:
        group = CollapsibleGroupBox("项目设置")
        group.setObjectName("toolbarCard")
        self.project_settings_content = QWidget()
        layout = QVBoxLayout(self.project_settings_content)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        hero = QWidget()
        hero.setObjectName("projectHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(4, 2, 4, 4)
        hero_layout.setSpacing(12)
        hero_mark = QLabel("VL")
        hero_mark.setObjectName("heroMark")
        hero_mark.setFixedSize(42, 42)
        hero_layout.addWidget(hero_mark)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(1)
        hero_title = QLabel("Video Labeler")
        hero_title.setObjectName("heroTitle")
        hero_subtitle = QLabel("Precision annotation workspace  ·  专业视频标注工作台")
        hero_subtitle.setObjectName("heroSubtitle")
        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_subtitle)
        hero_layout.addLayout(hero_copy)
        hero_layout.addStretch(1)
        self.workspace_status_badge = QLabel("READY")
        self.workspace_status_badge.setObjectName("workspaceStatusBadge")
        hero_layout.addWidget(self.workspace_status_badge)
        layout.addWidget(hero)

        self.open_video_button = QPushButton("导入视频")
        self.import_csv_button = QPushButton("导入 CSV")
        self.save_csv_button = QPushButton("保存标注 CSV")
        self.output_folder_button = QPushButton("选择输出文件夹")
        self.export_button = QPushButton("批量导出")
        self.export_button.setObjectName("primaryButton")
        self.project_export_button = QPushButton("导出整个项目")
        self.project_queue_button = QPushButton("查看导出队列")
        self.shortcut_help_button = QPushButton("快捷键说明")
        self.output_folder_label = QLabel("未选择输出文件夹")
        self.output_folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.output_folder_label.setObjectName("mutedLabel")
        self.output_folder_label.setWordWrap(False)
        self.output_folder_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYYMMDD")
        self.camera_edit = QLineEdit()
        self.camera_edit.setPlaceholderText("cam02")
        self.view_combo = QComboBox()
        self.view_combo.addItems(VIEW_TYPES)
        self._configure_custom_combo(
            self.view_combo,
            "视角",
            normalize_view_token,
            "仅支持小写英文和数字。",
        )

        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setPlaceholderText("留空则使用 PATH 中的 FFmpeg")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(("encode", "copy"))
        self.overwrite_check = QCheckBox("覆盖已有片段")
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 64)
        self.workers_spin.setValue(0)
        self.workers_spin.setSpecialValueText("自动")

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        def create_action_group(
            object_name: str, caption: str
        ) -> tuple[QWidget, QHBoxLayout]:
            action_group = QWidget()
            action_group.setObjectName(object_name)
            action_group_layout = QVBoxLayout(action_group)
            action_group_layout.setContentsMargins(0, 0, 0, 0)
            action_group_layout.setSpacing(4)
            caption_label = QLabel(caption)
            caption_label.setObjectName("toolbarGroupCaption")
            action_group_layout.addWidget(caption_label)
            buttons_layout = QHBoxLayout()
            buttons_layout.setContentsMargins(0, 0, 0, 0)
            buttons_layout.setSpacing(6)
            action_group_layout.addLayout(buttons_layout)
            return action_group, buttons_layout

        self.import_csv_action_group, import_csv_actions_layout = (
            create_action_group("importCsvActionGroup", "导入与 CSV")
        )
        import_csv_actions_layout.addWidget(self.open_video_button)
        import_csv_actions_layout.addWidget(self.import_csv_button)
        import_csv_actions_layout.addWidget(self.save_csv_button)
        action_layout.addWidget(self.import_csv_action_group)

        separator = QFrame()
        separator.setObjectName("toolbarSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        action_layout.addWidget(separator)

        self.export_output_action_group, export_output_actions_layout = (
            create_action_group("exportOutputActionGroup", "导出与输出")
        )
        export_output_actions_layout.addWidget(self.output_folder_button)
        export_output_actions_layout.addWidget(self.output_folder_label, stretch=1)
        export_output_actions_layout.addWidget(self.export_button)
        export_output_actions_layout.addWidget(self.project_export_button)
        export_output_actions_layout.addWidget(self.project_queue_button)
        action_layout.addWidget(self.export_output_action_group, stretch=1)

        separator = QFrame()
        separator.setObjectName("toolbarSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        action_layout.addWidget(separator)

        self.settings_operation_action_group, settings_operation_actions_layout = (
            create_action_group("settingsOperationActionGroup", "设置与操作")
        )
        settings_operation_actions_layout.addWidget(self.shortcut_help_button)
        action_layout.addWidget(self.settings_operation_action_group)
        self.import_action_group = self.import_csv_action_group
        self.csv_action_group = self.import_csv_action_group
        self.export_action_group = self.export_output_action_group
        self.settings_action_group = self.settings_operation_action_group
        self.welcome_hint_label = QLabel(
            "开始使用：导入视频，设置片段范围和标签，再选择输出文件夹导出。"
        )
        self.welcome_hint_label.setObjectName("mutedLabel")
        self.welcome_hint_label.setWordWrap(True)
        layout.addWidget(self.welcome_hint_label)
        layout.addLayout(action_layout)

        metadata_layout = QHBoxLayout()
        metadata_layout.setSpacing(8)
        metadata_layout.addWidget(QLabel("日期"))
        metadata_layout.addWidget(self.date_edit)
        metadata_layout.addWidget(QLabel("摄像头"))
        metadata_layout.addWidget(self.camera_edit)
        metadata_layout.addWidget(QLabel("视角"))
        metadata_layout.addWidget(self.view_combo)
        metadata_layout.addStretch(1)
        layout.addLayout(metadata_layout)

        self.advanced_export_group = QGroupBox("导出设置")
        self.advanced_export_group.setCheckable(True)
        self.advanced_export_group.setChecked(False)
        advanced_layout = QVBoxLayout(self.advanced_export_group)
        advanced_layout.setContentsMargins(6, 6, 6, 6)
        self.advanced_export_content = QWidget()
        options_layout = QHBoxLayout(self.advanced_export_content)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.addWidget(QLabel("FFmpeg"))
        options_layout.addWidget(self.ffmpeg_edit, stretch=1)
        options_layout.addWidget(QLabel("模式"))
        options_layout.addWidget(self.mode_combo)
        options_layout.addWidget(self.overwrite_check)
        options_layout.addWidget(QLabel("并行数量"))
        options_layout.addWidget(self.workers_spin)
        advanced_layout.addWidget(self.advanced_export_content)
        self.advanced_export_content.setVisible(False)
        self.advanced_export_group.setObjectName("inlineExportOptions")
        layout.addWidget(self.advanced_export_group)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 6, 6, 6)
        group_layout.addWidget(self.project_settings_content)
        group.set_content(self.project_settings_content)
        self._set_output_folder_display()
        return group

    def _set_output_folder_display(self) -> None:
        full_text = str(self.output_dir) if self.output_dir else "未选择输出文件夹"
        self.output_folder_label.setToolTip(full_text)
        available_width = max(80, self.output_folder_label.width())
        self.output_folder_label.setText(
            self.output_folder_label.fontMetrics().elidedText(
                full_text,
                Qt.TextElideMode.ElideMiddle,
                available_width,
            )
        )

    def _build_project_menu(self) -> None:
        self.project_menu = self.menuBar().addMenu("工程")
        self.import_preannotation_action = QAction("导入预标注 JSON", self)
        self.export_dataset_action = QAction("导出数据集", self)
        self.plugin_export_action = QAction("插件数据集导出", self)
        self.export_full_csv_action = QAction("导出完整标注 CSV", self)
        self.import_full_csv_action = QAction("导入完整标注 CSV", self)
        self.validate_project_action = QAction("检查工程质量", self)
        self.statistics_action = QAction("查看工程统计", self)
        self.export_statistics_action = QAction("导出工程统计 JSON", self)
        self.load_plugin_action = QAction("加载导出插件", self)
        self.list_exporters_action = QAction("查看可用导出器", self)
        self.scan_plugins_action = QAction("扫描插件目录", self)
        self.relocate_media_action = QAction("定位缺失视频", self)
        self.new_project_action = QAction("新建工程", self)
        self.open_project_action = QAction("打开工程", self)
        self.save_project_action = QAction("保存工程", self)
        self.save_version_action = QAction("保存版本快照", self)
        self.restore_project_action = QAction("从备份文件恢复工程", self)
        self.restore_version_action = QAction("从版本快照恢复工程", self)
        self.project_menu.addAction(self.new_project_action)
        self.project_menu.addAction(self.open_project_action)
        self.project_menu.addAction(self.save_project_action)
        self.project_menu.addAction(self.import_preannotation_action)
        self.project_menu.addAction(self.export_dataset_action)
        self.project_menu.addAction(self.plugin_export_action)
        self.project_menu.addAction(self.export_full_csv_action)
        self.project_menu.addAction(self.import_full_csv_action)
        self.project_menu.addAction(self.validate_project_action)
        self.project_menu.addAction(self.statistics_action)
        self.project_menu.addAction(self.export_statistics_action)
        self.project_menu.addAction(self.load_plugin_action)
        self.project_menu.addAction(self.list_exporters_action)
        self.project_menu.addAction(self.scan_plugins_action)
        self.project_menu.addAction(self.relocate_media_action)
        self.project_menu.addSeparator()
        self.project_menu.addAction(self.save_version_action)
        self.project_menu.addAction(self.restore_version_action)
        self.project_menu.addAction(self.restore_project_action)
        self.settings_menu = self.menuBar().addMenu("设置")
        self.hotkey_settings_action = QAction("配置快捷键", self)
        self.dark_mode_action = QAction("深色模式", self)
        self.dark_mode_action.setCheckable(True)
        self.settings_menu.addAction(self.hotkey_settings_action)
        self.settings_menu.addAction(self.dark_mode_action)

    def set_dark_mode(self, enabled: bool) -> None:
        application = QApplication.instance()
        if application is None:
            return
        if enabled:
            apply_dark_fresh_theme(application)
            self.video_scene.setBackgroundBrush(QColor("#090E16"))
            self.video_placeholder_item.setBrush(QColor("#C7D2E3"))
        else:
            apply_light_fresh_theme(application)
            self.video_scene.setBackgroundBrush(QColor("#1F2937"))
            self.video_placeholder_item.setBrush(QColor("#B9C8D9"))

    def _build_video_panel(self) -> QGroupBox:
        group = QGroupBox("视频预览")
        group.setObjectName("videoCard")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.video_widget = QGraphicsView()
        self.video_widget.setMinimumHeight(280)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.video_widget.setObjectName("videoSurface")
        self.video_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_widget.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_widget.setInteractive(False)
        self.video_scene = QGraphicsScene(self.video_widget)
        self.video_scene.setBackgroundBrush(QColor("#1F2937"))
        self.video_item = QGraphicsVideoItem()
        self.video_item.setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        self.video_item.videoSink().videoFrameChanged.connect(
            self._cache_paused_video_frame
        )
        self.video_scene.addItem(self.video_item)
        self.video_placeholder_item = self.video_scene.addSimpleText(
            "导入视频后开始标注"
        )
        self.video_placeholder_item.setBrush(QColor("#B9C8D9"))
        self.video_placeholder_item.setAcceptedMouseButtons(
            Qt.MouseButton.NoButton
        )
        self.video_placeholder_item.setZValue(1)
        self.video_widget.setScene(self.video_scene)
        self.video_viewport = self.video_widget.viewport()
        self.video_viewport.installEventFilter(self)
        layout.addWidget(self.video_widget, stretch=1)

        self.video_info_panel = QWidget()
        self.video_info_panel.setObjectName("videoInfoPanel")
        video_info_layout = QHBoxLayout(self.video_info_panel)
        video_info_layout.setContentsMargins(12, 9, 12, 9)
        video_info_layout.setSpacing(8)
        self.video_info_title = QLabel("未选择视频")
        self.video_info_title.setObjectName("videoInfoTitle")
        self.video_info_meta = QLabel("导入视频后开始标注")
        self.video_info_meta.setObjectName("videoInfoMeta")
        video_info_layout.addWidget(self.video_info_title)
        video_info_layout.addStretch(1)
        video_info_layout.addWidget(self.video_info_meta)
        layout.addWidget(self.video_info_panel)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_item)
        self._update_video_placeholder(QMediaPlayer.MediaStatus.NoMedia)

        self.video_controls_panel = QWidget()
        self.video_controls_panel.setObjectName("videoControlsPanel")
        video_controls_layout = QVBoxLayout(self.video_controls_panel)
        video_controls_layout.setContentsMargins(12, 10, 12, 10)
        video_controls_layout.setSpacing(8)

        position_layout = QHBoxLayout()
        position_layout.addWidget(QLabel("播放进度"))
        self.position_label = QLabel("00:00:00.000")
        self.duration_label = QLabel("00:00:00.000")
        self.frame_info_label = QLabel("")
        self.frame_info_label.setObjectName("mutedLabel")
        self.timeline_slider = SegmentTimelineSlider()
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setTracking(False)
        self.timeline_slider.setMinimumHeight(40)
        position_layout.addWidget(self.position_label)
        position_layout.addWidget(self.timeline_slider, stretch=1)
        position_layout.addWidget(self.duration_label)
        position_layout.addWidget(self.frame_info_label)
        self.goto_edit = QLineEdit()
        self.goto_edit.setPlaceholderText("跳转 如 1:23.456")
        self.goto_edit.setMaximumWidth(150)
        self.goto_edit.setToolTip("输入时间码跳转，支持 1:23.456 / 0:01:23 / 83.5")
        self.goto_edit.returnPressed.connect(self._jump_to_timecode)
        position_layout.addWidget(self.goto_edit)
        video_controls_layout.addLayout(position_layout)

        self.play_button = QPushButton("播放")
        self.seek_back_button = QPushButton("-5s")
        self.seek_forward_button = QPushButton("+5s")
        self.set_start_button = QPushButton("设置起始点")
        self.set_end_button = QPushButton("设置结束点")
        self.quick_add_button = QPushButton("✓ 完成片段")
        self.quick_add_button.setObjectName("quickAddClipButton")
        self.quick_add_button.setToolTip("使用当前起止时间立即添加片段")
        self.quick_add_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; "
            "font-weight: bold; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        standard_icons = self.style()
        self.play_button.setIcon(
            standard_icons.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.seek_back_button.setIcon(
            standard_icons.standardIcon(QStyle.StandardPixmap.SP_MediaSeekBackward)
        )
        self.seek_forward_button.setIcon(
            standard_icons.standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward)
        )
        self.play_button.setToolTip("播放或暂停（空格）")
        self.seek_back_button.setToolTip("后退 5 秒")
        self.seek_forward_button.setToolTip("前进 5 秒")
        self.set_start_button.setToolTip("设置当前帧为起始点（S）")
        self.set_end_button.setToolTip("设置当前帧为结束点（E）")
        self.set_start_button.setStyleSheet(
            "QPushButton { background-color: #16a34a; color: white; "
            "font-weight: bold; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #15803d; }"
        )
        self.set_end_button.setStyleSheet(
            "QPushButton { background-color: #dc2626; color: white; "
            "font-weight: bold; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #b91c1c; }"
        )
        self.speed_combo = QComboBox()
        for rate in PLAYBACK_RATE_PRESETS:
            self.speed_combo.addItem(f"{rate}x", rate)
        self.speed_combo.addItem(CUSTOM_PLAYBACK_RATE_TEXT, None)
        self.speed_combo.setCurrentIndex(self.speed_combo.findData(1.0))
        self.custom_speed_spin = QDoubleSpinBox()
        self.custom_speed_spin.setRange(0.1, 4.0)
        self.custom_speed_spin.setDecimals(3)
        self.custom_speed_spin.setSingleStep(0.1)
        self.custom_speed_spin.setKeyboardTracking(False)
        self.custom_speed_spin.setSuffix("x")
        self.custom_speed_spin.setObjectName("customPlaybackRateSpin")
        self.custom_speed_spin.setValue(self._last_playback_rate)
        self.playback_rate_badge = QLabel("1.0x")
        self.playback_rate_badge.setObjectName("playbackRateBadge")

        self.clip_range_label = QLabel("起 0:00.000 · 止 0:00.000")
        self.clip_range_label.setObjectName("clipRangeLabel")
        self.clip_range_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.video_controls_panel)
        return group

    def _build_clip_editor(self) -> QGroupBox:
        group = QGroupBox("片段标注")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Compact review overview inspired by the reference right-hand cards:
        # keep the active source and progress visible while editing.
        self.annotation_overview = QFrame()
        self.annotation_overview.setObjectName("annotationOverview")
        overview_layout = QHBoxLayout(self.annotation_overview)
        overview_layout.setContentsMargins(10, 8, 10, 8)
        overview_layout.setSpacing(8)
        overview_copy = QVBoxLayout()
        overview_copy.setSpacing(1)
        self.annotation_overview_title = QLabel("当前片段")
        self.annotation_overview_title.setObjectName("annotationOverviewTitle")
        self.annotation_overview_source = QLabel("未选择记录")
        self.annotation_overview_source.setObjectName("annotationOverviewSource")
        self.annotation_overview_source.setWordWrap(True)
        overview_copy.addWidget(self.annotation_overview_title)
        overview_copy.addWidget(self.annotation_overview_source)
        self.annotation_overview_warning = QLabel("")
        self.annotation_overview_warning.setObjectName("annotationWarning")
        self.annotation_overview_warning.setWordWrap(True)
        overview_copy.addWidget(self.annotation_overview_warning)
        overview_layout.addLayout(overview_copy, stretch=1)
        self.annotation_overview_total = QLabel("0\n片段")
        self.annotation_overview_pending = QLabel("0\n待审核")
        self.annotation_overview_approved = QLabel("0\n已通过")
        for badge in (self.annotation_overview_total, self.annotation_overview_pending, self.annotation_overview_approved):
            badge.setObjectName("annotationMetric")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setMinimumWidth(58)
            overview_layout.addWidget(badge)
        layout.addWidget(self.annotation_overview)

        source_layout = QHBoxLayout()
        self.source_label = QLabel("未选择视频")
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("mutedLabel")
        self.project_video_combo = QComboBox()
        self.project_video_combo.setObjectName("projectVideoCombo")
        self.project_video_combo.setMinimumContentsLength(16)
        self.project_video_combo.setEnabled(False)
        source_layout.addWidget(self.source_label, stretch=1)
        source_layout.addWidget(self.project_video_combo)
        layout.addLayout(source_layout)

        self.start_spin = self._new_time_spin()
        self.end_spin = self._new_time_spin()
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 999999)
        self.sequence_spin.setValue(1)
        time_layout = QHBoxLayout()
        time_layout.setSpacing(8)
        for label_text, control in (
            ("开始时间", self.start_spin),
            ("结束时间", self.end_spin),
            ("编号", self.sequence_spin),
        ):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)
            cell_layout.addWidget(QLabel(label_text))
            cell_layout.addWidget(control)
            time_layout.addWidget(cell)
        layout.addLayout(time_layout)

        transport_controls = QHBoxLayout()
        transport_controls.setSpacing(6)
        transport_controls.addWidget(self.set_start_button)
        transport_controls.addWidget(self.set_end_button)
        transport_controls.addWidget(self.quick_add_button)
        transport_controls.addWidget(self.clip_range_label, stretch=1)
        layout.addLayout(transport_controls)

        playback_controls = QHBoxLayout()
        playback_controls.setSpacing(6)
        playback_controls.addWidget(self.play_button)
        playback_controls.addWidget(self.seek_back_button)
        playback_controls.addWidget(self.seek_forward_button)
        playback_controls.addStretch(1)
        layout.addLayout(playback_controls)

        playback_rate_layout = QHBoxLayout()
        playback_rate_layout.setSpacing(6)
        playback_rate_layout.addWidget(QLabel("速度"))
        playback_rate_layout.addWidget(self.playback_rate_badge)
        playback_rate_layout.addWidget(self.speed_combo)
        playback_rate_layout.addWidget(self.custom_speed_spin)
        playback_rate_layout.addStretch(1)
        layout.addLayout(playback_rate_layout)

        note_layout = QHBoxLayout()
        note_layout.setSpacing(8)
        note_layout.addWidget(QLabel("备注"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选：记录复核或导出说明")
        note_layout.addWidget(self.note_edit, stretch=1)
        layout.addLayout(note_layout)

        self.add_button = QPushButton("添加片段")
        self.remove_button = QPushButton("删除所选")
        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("重做")
        self.clear_button = QPushButton("清空编辑区")
        self.next_pending_button = QPushButton("确认并下一条")
        self.next_pending_button.setObjectName("primaryButton")
        self.review_mode_button = QPushButton("审核模式：关")
        self.review_mode_button.setCheckable(True)
        self.review_mode_button.setToolTip("开启后按 1/2/3/4 快速标记：1 通过 / 2 需修正 / 3 剔除 / 4 待审核")
        self.remember_labels_button = QPushButton("记住标签：关")
        self.remember_labels_button.setCheckable(True)
        self.remember_labels_button.setToolTip("开启后，新片段自动继承上一次行为标签")
        self.add_button.setObjectName("addClipButton")
        self.remove_button.setObjectName("dangerButton")
        self.undo_button.setObjectName("undoButton")
        self.redo_button.setObjectName("redoButton")
        for button in (
            self.add_button,
            self.remove_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.next_pending_button,
            self.review_mode_button,
            self.remember_labels_button,
        ):
            button.setMinimumHeight(28)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
        primary_actions = QHBoxLayout()
        primary_actions.addWidget(self.add_button)
        primary_actions.addWidget(self.next_pending_button)
        secondary_actions = QHBoxLayout()
        secondary_actions.setSpacing(8)
        for button in (
            self.remove_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.review_mode_button,
            self.remember_labels_button,
        ):
            secondary_actions.addWidget(button)
        layout.addLayout(primary_actions)
        layout.addLayout(secondary_actions)

        self.behavior_checks: dict[str, QCheckBox] = {}
        self.behaviors_group = CollapsibleGroupBox("行为标签")
        self.behaviors_group.setObjectName("collapsibleBehaviorGroup")
        self.behaviors_group.setChecked(True)
        self.behavior_checks_container = QWidget()
        behavior_content_layout = QVBoxLayout(self.behavior_checks_container)
        behavior_content_layout.setContentsMargins(0, 0, 0, 0)
        behavior_content_layout.setSpacing(8)
        self.behavior_tag_combo = BehaviorTagComboBox()
        behavior_content_layout.addWidget(self.behavior_tag_combo)
        self.historical_tags_container = QWidget()
        self.historical_tags_layout = QHBoxLayout(
            self.historical_tags_container
        )
        self.historical_tags_layout.setContentsMargins(0, 0, 0, 0)
        self.historical_tags_layout.setSpacing(6)
        behavior_content_layout.addWidget(self.historical_tags_container)
        self.historical_tags_container.setVisible(False)

        behaviors_layout = QVBoxLayout(self.behaviors_group)
        behaviors_layout.setContentsMargins(6, 6, 6, 6)
        behaviors_layout.addWidget(self.behavior_checks_container)
        self.behaviors_group.set_content(self.behavior_checks_container)

        self._rebuild_behavior_controls()
        layout.addWidget(self.behaviors_group)

        self.custom_tags_group = CollapsibleGroupBox("自定义字段")
        self.custom_tags_group.setChecked(False)
        custom_tags_content = QWidget()
        custom_tags_layout = QVBoxLayout(custom_tags_content)
        custom_tags_layout.setContentsMargins(0, 0, 0, 0)
        custom_tags_layout.setSpacing(8)
        add_custom_tag_layout = QHBoxLayout()
        self.custom_behavior_tag_edit = QLineEdit()
        self.custom_behavior_tag_edit.setPlaceholderText("输入英文自定义行为标签")
        self.add_custom_behavior_tag_button = QPushButton("添加")
        self.add_custom_behavior_tag_button.setObjectName("secondaryButton")
        add_custom_tag_layout.addWidget(self.custom_behavior_tag_edit, stretch=1)
        add_custom_tag_layout.addWidget(self.add_custom_behavior_tag_button)
        custom_tags_layout.addLayout(add_custom_tag_layout)
        remove_custom_tag_layout = QHBoxLayout()
        self.custom_tag_library_combo = QComboBox()
        self.custom_tag_library_combo.setObjectName("customTagLibraryCombo")
        self.remove_custom_behavior_tag_button = QPushButton("删除标签")
        self.remove_custom_behavior_tag_button.setObjectName("dangerButton")
        self.remove_custom_behavior_tag_button.setEnabled(False)
        self.custom_tag_color_button = QPushButton("设置颜色")
        self.custom_tag_color_button.setEnabled(False)
        remove_custom_tag_layout.addWidget(self.custom_tag_library_combo, stretch=1)
        remove_custom_tag_layout.addWidget(
            self.remove_custom_behavior_tag_button
        )
        remove_custom_tag_layout.addWidget(self.custom_tag_color_button)
        custom_tags_layout.addLayout(remove_custom_tag_layout)
        preset_layout = QHBoxLayout()
        self.import_tag_preset_button = QPushButton("导入标签预设")
        self.export_tag_preset_button = QPushButton("导出标签预设")
        preset_layout.addWidget(self.import_tag_preset_button)
        preset_layout.addWidget(self.export_tag_preset_button)
        custom_tags_layout.addLayout(preset_layout)
        custom_tags_group_layout = QVBoxLayout(self.custom_tags_group)
        custom_tags_group_layout.setContentsMargins(6, 6, 6, 6)
        custom_tags_group_layout.addWidget(custom_tags_content)
        self.custom_tags_group.set_content(custom_tags_content)
        layout.addWidget(self.custom_tags_group)
        self._sync_custom_tag_library()

        labels_form = QFormLayout()
        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(POLARITIES)
        self.polarity_combo.setToolTip("正向=pos，负向=neg")
        self.polarity_combo.view().setMinimumWidth(120)
        self._configure_custom_combo(
            self.polarity_combo,
            "正负性",
            lambda value: normalize_label_token(value, "polarity"),
            "仅支持小写英文、数字和下划线。",
        )
        self.lighting_combo = QComboBox()
        self.lighting_combo.addItems(LIGHTING_VALUES)
        self.lighting_combo.setToolTip(
            "白天=daytime，夜间彩色=night_full_color，夜间黑白=night_black_white"
        )
        self.lighting_combo.view().setMinimumWidth(180)
        self._configure_custom_combo(
            self.lighting_combo,
            "光照",
            lambda value: normalize_label_token(value, "lighting"),
            "仅支持小写英文、数字和下划线。",
        )
        labels_form.addRow("正负性", self.polarity_combo)
        labels_form.addRow("光照", self.lighting_combo)
        while labels_form.count():
            labels_form.takeAt(0)

        self.stratum_combo = QComboBox()
        self.stratum_combo.setToolTip(
            "简单正向=easy_pos，困难正向=hard_pos，简单负向=easy_neg，"
            "困难负向=hard_neg，待复核=pending_review"
        )
        self.stratum_combo.addItem("不设置", "")
        for value in STRATUM_VALUES:
            self.stratum_combo.addItem(STRATUM_LABELS.get(value, value), value)

        self.scene_group = CollapsibleGroupBox("场景属性")
        self.scene_group.setChecked(False)
        scene_content = QWidget()
        scene_form = QHBoxLayout(scene_content)
        scene_form.setContentsMargins(0, 0, 0, 0)
        scene_form.setSpacing(8)
        scene_form.addWidget(QLabel("正负性"))
        scene_form.addWidget(self.polarity_combo, stretch=1)
        scene_form.addWidget(QLabel("光照"))
        scene_form.addWidget(self.lighting_combo, stretch=1)
        scene_form.addWidget(QLabel("分层"))
        scene_form.addWidget(self.stratum_combo, stretch=1)
        scene_layout = QVBoxLayout(self.scene_group)
        scene_layout.setContentsMargins(6, 6, 6, 6)
        scene_layout.addWidget(scene_content)
        self.scene_group.set_content(scene_content)
        layout.addWidget(self.scene_group)

        self.events_group = CollapsibleGroupBox("样本内事件")
        self.events_group.setChecked(False)
        events_content = QWidget()
        self.events_list_layout = QVBoxLayout(events_content)
        self.events_list_layout.setContentsMargins(0, 0, 0, 0)
        self.events_list_layout.setSpacing(6)
        self._event_rows: list[tuple[QComboBox, QSpinBox, QSpinBox, QWidget]] = []
        self.add_event_button = QPushButton("+ 添加事件")
        self.add_event_button.clicked.connect(self._add_event_row)
        events_layout = QVBoxLayout(self.events_group)
        events_layout.setContentsMargins(6, 6, 6, 6)
        events_layout.addWidget(events_content)
        events_layout.addWidget(self.add_event_button)
        self.events_group.set_content(events_content)
        layout.addWidget(self.events_group)

        self.person_group = CollapsibleGroupBox("人员身份")
        self.person_group.setChecked(False)
        person_content = QWidget()
        person_form = QFormLayout(person_content)
        self.age_combo = QComboBox()
        self.age_combo.addItem("不设置", "")
        for value in AGE_VALUES:
            self.age_combo.addItem(AGE_LABELS.get(value, value), value)
        self.face_familiarity_combo = QComboBox()
        self.face_familiarity_combo.addItem("不设置", "")
        for value in FAMILIARITY_VALUES:
            self.face_familiarity_combo.addItem(
                FAMILIARITY_LABELS.get(value, value), value
            )
        self.reid_familiarity_combo = QComboBox()
        self.reid_familiarity_combo.addItem("不设置", "")
        for value in FAMILIARITY_VALUES:
            self.reid_familiarity_combo.addItem(
                FAMILIARITY_LABELS.get(value, value), value
            )
        self.person_count_spin = QSpinBox()
        self.person_count_spin.setRange(0, 99)
        self.person_count_spin.setValue(0)
        self.person_count_spin.setSpecialValueText("不设置")
        person_form.addRow("年龄", self.age_combo)
        person_form.addRow("人脸熟悉度", self.face_familiarity_combo)
        person_form.addRow("体态 ReID", self.reid_familiarity_combo)
        person_form.addRow("人数", self.person_count_spin)
        person_layout = QVBoxLayout(self.person_group)
        person_layout.setContentsMargins(6, 6, 6, 6)
        person_layout.addWidget(person_content)
        self.person_group.set_content(person_content)
        layout.addWidget(self.person_group)

        self._update_label_group_titles()

        layout.addWidget(QLabel("生成的文件名"))
        self.filename_preview = QLineEdit()
        self.filename_preview.setReadOnly(True)
        self.filename_preview.setToolTip("生成的输出文件名")
        layout.addWidget(self.filename_preview)
        return group

    def _available_behavior_tags(self) -> tuple[str, ...]:
        return (*BEHAVIOR_LABELS, *self.project.custom_behavior_tags)

    def _rebuild_behavior_controls(
        self,
        selected: Collection[str] | None = None,
    ) -> None:
        selected_tags = (
            tuple(selected) if selected is not None else self.selected_behaviors()
        )
        available_tags = self._available_behavior_tags()
        available_set = set(available_tags)
        self.historical_behavior_tags = tuple(
            dict.fromkeys(
                behavior
                for behavior in selected_tags
                if behavior not in available_set
            )
        )
        self.behavior_checks.clear()
        self.historical_tag_labels.clear()
        self.behavior_tag_combo.set_tags(available_tags, selected_tags)
        for behavior in available_tags:
            checkbox = QCheckBox(behavior)
            checkbox.setChecked(behavior in selected_tags)
            color = self.project.custom_behavior_tag_colors.get(behavior)
            if color:
                checkbox.setStyleSheet(f"QCheckBox {{ color: {color}; }}")
            checkbox.toggled.connect(
                lambda checked, tag=behavior: self.behavior_tag_combo.set_tag_checked(
                    tag, checked
                )
            )
            self.behavior_checks[behavior] = checkbox

        while self.historical_tags_layout.count():
            item = self.historical_tags_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        for behavior in self.historical_behavior_tags:
            label = QLabel(behavior)
            label.setObjectName("historicalBehaviorTag")
            label.setEnabled(False)
            label.setToolTip(
                "[Historical Tag] This tag has been removed from tag library, "
                "data remains inside this segment, cannot reuse via button"
            )
            self.historical_tag_labels[behavior] = label
            self.historical_tags_layout.addWidget(label)
        self.historical_tags_layout.addStretch(1)
        self.historical_tags_container.setVisible(
            bool(self.historical_behavior_tags)
        )
        if hasattr(self, "custom_tag_library_combo"):
            self._sync_custom_tag_library()
        if hasattr(self, "behavior_filter_combo"):
            self._sync_filter_options()

    def _sync_custom_tag_library(self) -> None:
        selected_tag = self.custom_tag_library_combo.currentData()
        with QSignalBlocker(self.custom_tag_library_combo):
            self.custom_tag_library_combo.clear()
            if self.project.custom_behavior_tags:
                for tag in self.project.custom_behavior_tags:
                    self.custom_tag_library_combo.addItem(tag, tag)
                index = self.custom_tag_library_combo.findData(selected_tag)
                self.custom_tag_library_combo.setCurrentIndex(
                    index if index >= 0 else 0
                )
            else:
                self.custom_tag_library_combo.addItem("暂无自定义标签", None)
        self.remove_custom_behavior_tag_button.setEnabled(
            bool(self.project.custom_behavior_tags)
        )
        self.custom_tag_color_button.setEnabled(
            bool(self.project.custom_behavior_tags)
        )

    def _sync_behavior_selection_from_combo(self) -> None:
        selected = set(self.behavior_tag_combo.checked_tags())
        for behavior, checkbox in self.behavior_checks.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(behavior in selected)
        self._update_filename_preview()

    def _update_label_group_titles(self) -> None:
        if hasattr(self, "scene_group"):
            self.scene_group.setTitle(
                f"场景属性：{self.polarity_combo.currentText()} · "
                f"{self.lighting_combo.currentText()}"
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "output_folder_label"):
            self._set_output_folder_display()

    def _resize_video_item(self) -> None:
        if not hasattr(self, "video_viewport"):
            return
        size = self.video_viewport.size()
        self.video_scene.setSceneRect(0, 0, size.width(), size.height())
        self.video_item.setSize(QSizeF(size))
        if hasattr(self, "video_placeholder_item"):
            bounds = self.video_placeholder_item.boundingRect()
            self.video_placeholder_item.setPos(
                (size.width() - bounds.width()) / 2,
                (size.height() - bounds.height()) / 2,
            )

    def eventFilter(self, watched, event) -> bool:
        if watched in self._button_hover_effects:
            if event.type() == QEvent.Type.Enter:
                self._animate_button_hover(watched, 13)
            elif event.type() == QEvent.Type.Leave:
                self._animate_button_hover(watched, 0)
            elif event.type() == QEvent.Type.MouseButtonPress:
                self._animate_button_press(watched, True)
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._animate_button_press(watched, False)
        if event.type() != QEvent.Type.Resize:
            return super().eventFilter(watched, event)
        if watched is getattr(self, "video_viewport", None):
            self._resize_video_item()
        return super().eventFilter(watched, event)

    def _build_task_table(self) -> CollapsibleGroupBox:
        group = CollapsibleGroupBox("片段任务")
        group.setChecked(True)
        group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content = QWidget()
        content.setMinimumHeight(280)
        self.task_panel_content = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.task_table = QTableWidget(0, len(TABLE_COLUMNS))
        self.task_table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.task_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.task_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.task_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(self._show_task_context_menu)
        self.task_table.setToolTip("双击编辑；右键打开快捷操作；Ctrl/Shift 可多选")
        self.task_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.task_table.setMinimumHeight(200)
        self.task_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(34)
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for column, width in enumerate(
            (72, 98, 98, 82, 210, 72, 150, 430, 80, 260, 220)
        ):
            self.task_table.setColumnWidth(column, width)

        self.table_filter_bar = QWidget()
        self.table_filter_bar.setObjectName("tableFilterBar")
        filter_layout = QVBoxLayout(self.table_filter_bar)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(6)
        self.batch_edit_button = QPushButton("批量修改选中片段")
        self.batch_delete_button = QPushButton("批量删除选中")
        self.batch_delete_button.setObjectName("dangerButton")
        self.approve_selected_button = QPushButton("批量通过审核")
        self.needs_fix_selected_button = QPushButton("批量标记需修正")
        self.reject_selected_button = QPushButton("批量剔除")
        self.behavior_filter_combo = QComboBox()
        self.behavior_filter_combo.addItem("全部行为", None)
        for behavior in BEHAVIOR_LABELS:
            self.behavior_filter_combo.addItem(behavior, behavior)
        self.behavior_filter_combo.setCurrentData = lambda value: (
            self.behavior_filter_combo.setCurrentIndex(
                self.behavior_filter_combo.findData(value)
            )
        )
        self.behavior_filter_combo.setMinimumContentsLength(10)
        self.behavior_filter_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._set_combo_visible_item_count(self.behavior_filter_combo)
        self.polarity_filter_combo = QComboBox()
        self.polarity_filter_combo.addItem("全部正负例", None)
        for polarity in POLARITIES:
            self.polarity_filter_combo.addItem(polarity, polarity)
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItem("全部导出状态", None)
        for status, label in STATUS_LABELS.items():
            self.status_filter_combo.addItem(label, status)
        self.review_filter_combo = QComboBox()
        self.review_filter_combo.addItem("全部审核状态", None)
        self.review_filter_combo.addItem("待审核", "pending")
        self.review_filter_combo.addItem("已通过", "approved")
        self.review_filter_combo.addItem("需修正", "needs_fix")
        self.review_filter_combo.addItem("已剔除", "rejected")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("编号升序", ("sequence", False))
        self.sort_combo.addItem("编号降序", ("sequence", True))
        self.sort_combo.addItem("时长升序", ("duration", False))
        self.sort_combo.addItem("时长降序", ("duration", True))
        self.clear_filters_button = QPushButton("清空筛选")

        self.table_filter_search_row = QWidget()
        self.table_filter_search_row.setObjectName("tableSearchRow")
        search_filter_layout = QHBoxLayout(self.table_filter_search_row)
        search_filter_layout.setContentsMargins(0, 0, 0, 0)
        search_filter_layout.setSpacing(8)
        search_filter_layout.addWidget(QLabel("搜索"))
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("搜索标签、备注或视频文件名")
        search_filter_layout.addWidget(self.search_edit, stretch=1)
        self.filter_result_label = QLabel()
        self.filter_result_label.setObjectName("mutedLabel")
        search_filter_layout.addWidget(self.filter_result_label)
        filter_layout.addWidget(self.table_filter_search_row)

        self.table_filter_primary_row = QWidget()
        primary_filter_layout = QHBoxLayout(self.table_filter_primary_row)
        primary_filter_layout.setContentsMargins(0, 0, 0, 0)
        primary_filter_layout.setSpacing(8)
        primary_filter_layout.addWidget(QLabel("筛选"))
        primary_filter_layout.addWidget(self.behavior_filter_combo, stretch=1)
        primary_filter_layout.addWidget(self.polarity_filter_combo, stretch=1)
        filter_layout.addWidget(self.table_filter_primary_row)

        self.table_filter_secondary_row = QWidget()
        secondary_filter_layout = QHBoxLayout(
            self.table_filter_secondary_row
        )
        secondary_filter_layout.setContentsMargins(0, 0, 0, 0)
        secondary_filter_layout.setSpacing(8)
        secondary_filter_layout.addWidget(self.status_filter_combo, stretch=1)
        secondary_filter_layout.addWidget(self.review_filter_combo, stretch=1)
        secondary_filter_layout.addWidget(QLabel("排序"))
        secondary_filter_layout.addWidget(self.sort_combo, stretch=1)
        secondary_filter_layout.addWidget(self.clear_filters_button)
        filter_layout.addWidget(self.table_filter_secondary_row)
        layout.addWidget(self.table_filter_bar)

        self.table_action_bar = QWidget()
        self.table_action_bar.setObjectName("tableActionBar")
        action_layout = QHBoxLayout(self.table_action_bar)
        action_layout.setContentsMargins(8, 6, 8, 6)
        action_layout.setSpacing(8)
        action_layout.addWidget(self.batch_edit_button)
        action_layout.addWidget(self.batch_delete_button)
        action_layout.addWidget(self.approve_selected_button)
        action_layout.addWidget(self.needs_fix_selected_button)
        action_layout.addWidget(self.reject_selected_button)
        action_layout.addStretch(1)
        self.detach_table_button = QPushButton("弹出表格")
        self.detach_table_button.setObjectName("secondaryButton")
        action_layout.addWidget(self.detach_table_button)
        layout.addWidget(self.task_table)
        layout.addWidget(self.table_action_bar)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 6, 6, 6)
        group_layout.addWidget(content)
        group.set_content(content)
        return group

    def _restore_task_table_content_minimum(self) -> None:
        if self.task_panel.isChecked():
            self.task_panel_content.setMinimumHeight(280)

    def _build_log_panel(self) -> CollapsibleGroupBox:
        group = CollapsibleGroupBox("操作日志")
        group.setObjectName("operationLogPanel")
        group.setChecked(False)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMinimumHeight(130)
        self.log_panel.document().setMaximumBlockCount(1000)
        layout.addWidget(self.log_panel)

        controls = QHBoxLayout()
        controls.addStretch(1)
        self.copy_log_button = QPushButton("复制日志")
        self.clear_log_button = QPushButton("清空日志")
        controls.addWidget(self.copy_log_button)
        controls.addWidget(self.clear_log_button)
        layout.addLayout(controls)

        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 6, 6, 6)
        group_layout.addWidget(content)
        group.set_content(content)
        return group

    def _show_task_table_dialog(self) -> None:
        if self.task_panel.parentWidget() is self.task_table_dialog:
            self.task_table_dialog.raise_()
            self.task_table_dialog.activateWindow()
            return

        self.page_layout.removeWidget(self.task_panel)
        self.task_panel.setParent(None)
        dialog_layout = self.task_table_dialog.layout()
        assert dialog_layout is not None
        dialog_layout.addWidget(self.task_panel)
        self.task_table_dialog.show()
        self.task_table_dialog.raise_()
        self.task_table_dialog.activateWindow()

    def _restore_task_panel(self, *_args: object) -> None:
        if self.task_panel.parentWidget() is self.workspace_content:
            return

        dialog_layout = self.task_table_dialog.layout()
        if dialog_layout is not None:
            dialog_layout.removeWidget(self.task_panel)
        self.task_panel.setParent(None)
        self.page_layout.insertWidget(
            self.page_layout.count() - 1,
            self.task_panel,
        )
        self.task_panel.show()

    def _build_export_status(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.cancel_export_button = QPushButton("取消导出")
        self.cancel_export_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel("就绪")
        self.annotation_stats_label = QLabel("片段 0 · 待审核 0")
        self.annotation_stats_label.setObjectName("annotationStats")
        self.shortcut_hint_label = QLabel(
            "快捷键：空格 播放/暂停，A/D 前后帧，S/E 设置起止点，Del 删除，"
            "Ctrl+Z/Y 撤销/重做，Ctrl+回车 确认，Ctrl+Shift+E 快速导出"
        )
        self.shortcut_hint_label.setWordWrap(True)

        layout.addWidget(self.cancel_export_button)
        layout.addWidget(self.progress_bar, stretch=1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.annotation_stats_label)
        layout.addWidget(self.shortcut_hint_label)
        return layout

    def _new_time_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 7 * 24 * 60 * 60)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        return spin

    def _configure_custom_combo(
        self,
        combo: QComboBox,
        field_name: str,
        normalize: Callable[[str], str],
        guidance: str,
    ) -> None:
        combo.addItem(CUSTOM_OPTION_TEXT)
        self._set_combo_visible_item_count(combo)
        combo.setProperty("last_valid_index", combo.currentIndex())
        combo.currentIndexChanged.connect(
            lambda index: self._request_custom_combo_value(
                combo, index, field_name, normalize, guidance
            )
        )

    def _request_custom_combo_value(
        self,
        combo: QComboBox,
        index: int,
        field_name: str,
        normalize: Callable[[str], str],
        guidance: str,
    ) -> None:
        if combo.itemText(index) != CUSTOM_OPTION_TEXT:
            combo.setProperty("last_valid_index", index)
            return

        previous_index = int(combo.property("last_valid_index"))
        value, accepted = QInputDialog.getText(
            self,
            "添加自定义选项",
            f"请输入自定义{field_name}：",
        )
        if not accepted:
            combo.setCurrentIndex(previous_index)
            return
        try:
            self._set_custom_combo_value(combo, value, normalize)
        except ValueError:
            combo.setCurrentIndex(previous_index)
            self._show_error("自定义选项无效", f"{field_name}无效：{guidance}")

    def _set_custom_combo_value(
        self,
        combo: QComboBox,
        value: str,
        normalize: Callable[[str], str],
    ) -> None:
        normalized = normalize(value)
        index = combo.findText(normalized)
        if index < 0:
            index = combo.findText(CUSTOM_OPTION_TEXT)
            combo.insertItem(index, normalized)
        combo.setCurrentIndex(index)
        combo.setProperty("last_valid_index", index)
        self._set_combo_visible_item_count(combo)

    def _set_combo_visible_item_count(self, combo: QComboBox) -> None:
        combo.setMaxVisibleItems(max(1, combo.count()))

    def _restore_parsed_metadata(self, parsed: ParsedFilename) -> None:
        self.date_edit.setText(parsed.metadata.date)
        self.camera_edit.setText(parsed.metadata.camera)
        self._set_custom_combo_value(
            self.view_combo,
            parsed.metadata.view,
            normalize_view_token,
        )
        self._set_custom_combo_value(
            self.polarity_combo,
            parsed.polarity,
            lambda value: normalize_label_token(value, "polarity"),
        )
        self._set_custom_combo_value(
            self.lighting_combo,
            parsed.lighting,
            lambda value: normalize_label_token(value, "lighting"),
        )

    def _connect_signals(self) -> None:
        self.open_video_button.clicked.connect(self.open_video)
        self.import_csv_button.clicked.connect(self.import_csv)
        self.import_preannotation_action.triggered.connect(
            self.import_preannotation_json
        )
        self.save_csv_button.clicked.connect(self.save_csv)
        self.export_dataset_action.triggered.connect(self.export_dataset)
        self.plugin_export_action.triggered.connect(self.export_plugin_dataset)
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action.triggered.connect(self.open_project)
        self.save_project_action.triggered.connect(self.save_project)
        self.save_version_action.triggered.connect(self.save_project_version)
        self.restore_project_action.triggered.connect(
            self.restore_project_from_backup
        )
        self.restore_version_action.triggered.connect(
            self.restore_project_from_version
        )
        self.relocate_media_action.triggered.connect(self.relocate_missing_media)
        self.export_full_csv_action.triggered.connect(self.save_full_csv)
        self.import_full_csv_action.triggered.connect(self.import_full_csv)
        self.validate_project_action.triggered.connect(self.show_project_validation)
        self.statistics_action.triggered.connect(self.show_project_statistics)
        self.export_statistics_action.triggered.connect(self.export_project_statistics)
        self.load_plugin_action.triggered.connect(self.load_export_plugin)
        self.list_exporters_action.triggered.connect(self.show_available_exporters)
        self.scan_plugins_action.triggered.connect(self.scan_plugin_directory)
        self.hotkey_settings_action.triggered.connect(
            self.show_hotkey_settings
        )
        self.dark_mode_action.toggled.connect(self.set_dark_mode)
        self.project_video_combo.currentIndexChanged.connect(
            lambda index: self.switch_active_video(
                self.project_video_combo.itemData(index)
            )
        )
        self.output_folder_button.clicked.connect(self.select_output_folder)
        self.play_button.clicked.connect(self.toggle_playback)
        self.seek_back_button.clicked.connect(lambda: self._seek_relative(-5000))
        self.seek_forward_button.clicked.connect(lambda: self._seek_relative(5000))
        self.set_start_button.clicked.connect(self._set_start_from_player)
        self.set_end_button.clicked.connect(self._set_end_from_player)
        self.timeline_slider.valueChanged.connect(self._seek_to_milliseconds)
        self.timeline_slider.segment_range_changed.connect(
            self._set_clip_range_from_timeline
        )
        self.speed_combo.currentIndexChanged.connect(self._on_speed_preset_changed)
        self.custom_speed_spin.editingFinished.connect(
            self._on_custom_speed_committed
        )
        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.playbackStateChanged.connect(self._update_play_button)
        self.player.mediaStatusChanged.connect(self._update_video_placeholder)
        self.player.errorOccurred.connect(self._media_error)
        self.advanced_export_group.toggled.connect(
            self.advanced_export_content.setVisible
        )

        self.date_edit.textChanged.connect(self._update_filename_preview)
        self.camera_edit.textChanged.connect(self._update_filename_preview)
        self.view_combo.currentTextChanged.connect(self._update_filename_preview)
        self.date_edit.textChanged.connect(self._mark_project_dirty)
        self.camera_edit.textChanged.connect(self._mark_project_dirty)
        self.view_combo.currentTextChanged.connect(self._mark_project_dirty)
        self.behavior_tag_combo.selectionChanged.connect(
            self._sync_behavior_selection_from_combo
        )
        self.polarity_combo.currentTextChanged.connect(self._update_filename_preview)
        self.lighting_combo.currentTextChanged.connect(self._update_filename_preview)
        self.polarity_combo.currentTextChanged.connect(self._update_label_group_titles)
        self.lighting_combo.currentTextChanged.connect(self._update_label_group_titles)
        self.sequence_spin.valueChanged.connect(self._update_filename_preview)
        self.start_spin.valueChanged.connect(self._sync_timeline_segment_range)
        self.end_spin.valueChanged.connect(self._sync_timeline_segment_range)
        self.start_spin.valueChanged.connect(self._update_clip_range_label)
        self.end_spin.valueChanged.connect(self._update_clip_range_label)
        self.add_custom_behavior_tag_button.clicked.connect(
            self.add_custom_behavior_tag
        )
        self.custom_behavior_tag_edit.returnPressed.connect(
            self.add_custom_behavior_tag
        )
        self.remove_custom_behavior_tag_button.clicked.connect(
            self._remove_selected_custom_behavior_tag
        )
        self.custom_tag_color_button.clicked.connect(
            self._choose_selected_custom_tag_color
        )
        self.import_tag_preset_button.clicked.connect(self.import_tag_preset)
        self.export_tag_preset_button.clicked.connect(self.export_tag_preset)

        self.add_button.clicked.connect(self.add_or_update_clip)
        self.quick_add_button.clicked.connect(self.add_or_update_clip)
        self.remove_button.clicked.connect(self.remove_selected_clip)
        self.undo_button.clicked.connect(self.undo_segments)
        self.redo_button.clicked.connect(self.redo_segments)
        self.clear_button.clicked.connect(self.clear_editor)
        self.next_pending_button.clicked.connect(self.confirm_and_next_pending)
        self.review_mode_button.toggled.connect(self._toggle_review_mode)
        self.remember_labels_button.toggled.connect(self._toggle_remember_labels)
        self.batch_edit_button.clicked.connect(self.show_batch_edit_dialog)
        self.batch_delete_button.clicked.connect(self._delete_selected_records)
        self.approve_selected_button.clicked.connect(lambda: self._set_selected_review_status("approved"))
        self.needs_fix_selected_button.clicked.connect(lambda: self._set_selected_review_status("needs_fix"))
        self.reject_selected_button.clicked.connect(lambda: self._set_selected_review_status("rejected"))
        self.detach_table_button.clicked.connect(self._show_task_table_dialog)
        self.behavior_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.polarity_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.status_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.review_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.search_edit.textChanged.connect(self._apply_table_filters)
        self.sort_combo.currentIndexChanged.connect(self._sort_records)
        self.clear_filters_button.clicked.connect(self.clear_table_filters)
        self.task_table.itemSelectionChanged.connect(self._load_selected_clip)
        self.task_table.cellChanged.connect(self._table_cell_changed)

        self.export_button.clicked.connect(self.start_export)
        self.project_export_button.clicked.connect(self.start_project_export)
        self.project_queue_button.clicked.connect(self.show_project_export_queue)
        self.cancel_export_button.clicked.connect(self.cancel_export)
        self.shortcut_help_button.clicked.connect(self.show_shortcut_help)
        self.copy_log_button.clicked.connect(self.copy_log)
        self.clear_log_button.clicked.connect(self.clear_log)
        self._register_shortcuts()
        self._register_utility_shortcuts()

    def _register_utility_shortcuts(self) -> None:
        """Keep high-frequency utility actions available without changing saved bindings."""
        actions: tuple[tuple[str, Callable[[], None]], ...] = (
            ("Ctrl+Enter", self.add_or_update_clip),
            ("Escape", self.clear_editor),
            ("Ctrl+Shift+E", self.start_export),
        )
        for sequence, callback in actions:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._utility_shortcuts.append(shortcut)
        select_all = QShortcut(QKeySequence("Ctrl+A"), self.task_table)
        select_all.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        select_all.activated.connect(self.task_table.selectAll)
        self._utility_shortcuts.append(select_all)

    def _register_shortcuts(self) -> None:
        callbacks: dict[str, Callable[[], None]] = {
            "play_pause": self.toggle_playback,
            "previous_frame": lambda: self._step_frame(-1),
            "next_frame": lambda: self._step_frame(1),
            "set_start": self._set_start_from_player,
            "set_end": self._set_end_from_player,
            "delete_selected": self.remove_selected_clip,
            "undo": self.undo_segments,
            "redo": self.redo_segments,
            "save_project": self.save_project,
            "complete_clip": lambda: self.add_or_update_clip(),
        }
        for shortcut in getattr(self, "shortcuts", {}).values():
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.shortcuts = {}
        for name, callback in callbacks.items():
            sequence = self.hotkey_bindings.get(name, DEFAULT_HOTKEYS[name])
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts[name] = shortcut

    def apply_hotkey_bindings(self, bindings: dict[str, str]) -> None:
        if set(bindings) != set(DEFAULT_HOTKEYS):
            raise ValueError("All hotkey actions must be configured.")
        normalized: dict[str, str] = {}
        for name in DEFAULT_HOTKEYS:
            sequence = QKeySequence(bindings[name])
            if sequence.isEmpty():
                raise ValueError("A hotkey cannot be empty.")
            normalized[name] = sequence.toString(
                QKeySequence.SequenceFormat.PortableText
            )
        if len({value.casefold() for value in normalized.values()}) != len(normalized):
            raise ValueError("Each action must use a different hotkey.")
        save_hotkey_preferences(self._hotkey_preferences_path, normalized)
        self.hotkey_bindings = normalized
        self._register_shortcuts()

    def show_hotkey_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("配置快捷键")
        layout = QFormLayout(dialog)
        editors: dict[str, QKeySequenceEdit] = {}
        for name, label in HOTKEY_ACTION_LABELS.items():
            editor = QKeySequenceEdit(QKeySequence(self.hotkey_bindings[name]))
            editors[name] = editor
            layout.addRow(label, editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.apply_hotkey_bindings(
                {
                    name: editor.keySequence().toString(
                        QKeySequence.SequenceFormat.PortableText
                    )
                    for name, editor in editors.items()
                }
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "快捷键设置", str(error))
            return
        self._set_status("快捷键设置已保存")

    def _create_shortcut_help_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("快捷键说明")
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(HOTKEY_ACTION_LABELS), 2, dialog)
        table.setHorizontalHeaderLabels(("快捷键", "操作"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for row, (name, action) in enumerate(HOTKEY_ACTION_LABELS.items()):
            table.setItem(
                row,
                0,
                QTableWidgetItem(self.hotkey_bindings[name]),
            )
            table.setItem(row, 1, QTableWidgetItem(action))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog

    def show_shortcut_help(self) -> None:
        self._create_shortcut_help_dialog().exec()

    def set_source_path(self, path: Path) -> None:
        entry = add_or_activate_video(self.project, path)
        self._probe_video_metadata(entry)
        self._bind_active_video(entry)
        self._mark_project_dirty()
        self._set_status(f"已选择视频：{entry.path.name}")

    def _probe_video_metadata(self, entry: ProjectVideo) -> None:
        if not entry.path.is_file() or entry.metadata:
            return
        try:
            ffmpeg = resolve_ffmpeg(self.ffmpeg_edit.text())
            entry.metadata = probe_media_metadata(resolve_ffprobe(ffmpeg), entry.path)
        except (OSError, RuntimeError, ValueError) as error:
            self._set_status(f"读取视频元数据失败：{self._file_error_tip(error)}")

    def _bind_active_video(self, entry: ProjectVideo) -> None:
        self.project.active_video_id = entry.id
        self.records = entry.segments
        self.source_path = entry.path
        self.source_name = entry.path.name
        self.source_label.setText(entry.path.name)
        self.video_info_title.setText(entry.path.name)
        meta = entry.metadata or {}
        if meta:
            self.video_info_meta.setText(
                f"{format_seconds(meta.get('duration', 0))} · "
                f"{meta.get('width', 0)}×{meta.get('height', 0)}"
            )
        else:
            self.video_info_meta.setText("视频已加载")
        self._editing_index = None
        self.add_button.setText("添加片段")
        self._sync_project_video_combo()
        self._refresh_table()
        self._update_history_controls()
        self._update_welcome_hint()
        if self.records:
            self.project_header.setChecked(False)

    def _active_project_video(self) -> ProjectVideo | None:
        active_id = self.project.active_video_id
        return next(
            (video for video in self.project.videos if video.id == active_id),
            None,
        )

    def _active_history(self, *, create: bool = False) -> SegmentHistory | None:
        active_video = self._active_project_video()
        if active_video is None:
            return None
        if create:
            return self._active_video_histories.setdefault(
                active_video.id, SegmentHistory()
            )
        return self._active_video_histories.get(active_video.id)

    def _clear_active_history(self) -> None:
        active_video = self._active_project_video()
        if active_video is not None:
            self._active_video_histories.pop(active_video.id, None)
        self._update_history_controls()

    def _update_history_controls(self) -> None:
        history = self._active_history()
        self.undo_button.setEnabled(history is not None and history.can_undo())
        self.redo_button.setEnabled(history is not None and history.can_redo())

    def _sync_project_video_combo(self) -> None:
        with QSignalBlocker(self.project_video_combo):
            self.project_video_combo.clear()
            for video in self.project.videos:
                self.project_video_combo.addItem(video.path.name, video.id)
            active_index = self.project_video_combo.findData(
                self.project.active_video_id
            )
            self.project_video_combo.setCurrentIndex(active_index)
            self.project_video_combo.setEnabled(bool(self.project.videos))

    def switch_active_video(self, video_id: object) -> None:
        if not isinstance(video_id, str):
            return
        entry = next(
            (video for video in self.project.videos if video.id == video_id),
            None,
        )
        if entry is None:
            return
        self._bind_active_video(entry)
        self.task_table.clearSelection()
        if entry.path.is_file():
            self._set_media_source(entry.path)
        else:
            self._set_media_source(None)
            self._set_status(f"视频源不存在：{entry.path}")

    def _set_media_source(self, path: Path | None) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        self.frame_cache.clear()
        if path is not None:
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.pause()

    def _cache_paused_video_frame(self, frame: object) -> None:
        if (
            self.source_path is None
            or self.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            return
        try:
            image = frame.toImage()
            if image.isNull():
                return
            cached_image = image.copy()
            self.frame_cache.put(
                (str(self.source_path), self.player.position()),
                cached_image,
                size_bytes=cached_image.sizeInBytes(),
            )
        except (AttributeError, RuntimeError):
            return

    def _project_snapshot(self) -> LabelProject:
        settings = self.project.global_settings
        settings["date"] = self.date_edit.text().strip()
        settings["camera"] = self.camera_edit.text().strip()
        settings["view"] = self.view_combo.currentText()
        settings["output_dir"] = str(self.output_dir) if self.output_dir else ""
        return self.project

    def _update_welcome_hint(self) -> None:
        self.welcome_hint_label.setHidden(bool(self.project.videos))

    def _mark_project_dirty(self) -> None:
        self._project_dirty = True
        self._schedule_project_backup()

    def _schedule_project_backup(self) -> None:
        if self._project_path is not None:
            self._backup_timer.start()

    def _write_automatic_backup(self) -> None:
        if self._project_path is None:
            return
        try:
            create_backup(self._project_path, self._project_snapshot())
            self._set_status("已自动备份工程")
        except (OSError, ValueError) as error:
            self._set_status(f"自动备份失败：{self._file_error_tip(error)}")

    def _confirm_discard_dirty_project(self) -> bool:
        if not self._project_dirty:
            return True
        answer = QMessageBox.question(
            self,
            "工程尚未保存",
            "当前工程有未保存的修改，确定放弃这些修改吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _clear_project_workspace(self) -> None:
        self._backup_timer.stop()
        self.project = new_project()
        self.records = []
        self.source_path = None
        self.source_name = ""
        self._editing_index = None
        self.source_label.setText("未选择视频")
        self.video_info_title.setText("未选择视频")
        self.video_info_meta.setText("导入视频后开始标注")
        self.project_video_combo.clear()
        self.project_video_combo.setEnabled(False)
        self._set_media_source(None)
        self._project_export_queue = []
        self.project_queue_dialog.set_items([])
        self._refresh_table()
        self.clear_editor()
        self._update_welcome_hint()

    def new_project(self) -> None:
        if not self._confirm_discard_dirty_project():
            return
        self._active_video_histories = {}
        self._clear_project_workspace()
        self._project_path = None
        self._project_dirty = False
        self._update_history_controls()
        self._set_status("已新建工程")

    def save_project(self) -> None:
        project_path = self._project_path
        if project_path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "保存工程",
                "未命名工程.labelproj",
                "标注工程 (*.labelproj)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not filename:
                return
            project_path = Path(filename)
        try:
            self._project_path = save_project_v2(
                project_path, self._project_snapshot()
            )
        except (OSError, ValueError) as error:
            self._show_error(
                "无法保存工程", f"保存工程失败：{self._file_error_tip(error)}"
            )
            return
        self._project_dirty = False
        self._set_status(f"已保存工程：{self._project_path}")

    def save_project_version(self) -> None:
        if self._project_path is None:
            self.save_project()
        if self._project_path is None:
            return
        try:
            snapshot = create_version_snapshot(
                self._project_path, self._project_snapshot()
            )
        except (OSError, ValueError) as error:
            self._show_error(
                "无法保存版本快照",
                f"保存版本快照失败：{self._file_error_tip(error)}",
            )
            return
        self._set_status(f"已保存版本快照：{snapshot.name}")

    def open_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "打开工程",
            "",
            "标注工程 (*.labelproj)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename or not self._confirm_discard_dirty_project():
            return
        if not self._load_project_path(Path(filename)):
            return

    def restore_project_from_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "从备份文件恢复工程",
            "",
            "标注工程 (*.labelproj)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename or not self._confirm_discard_dirty_project():
            return
        backup_path = Path(filename)
        if not self._load_project_path(backup_path):
            return
        if backup_path.parent.name == ".backups":
            project_name, separator, _timestamp = backup_path.stem.rpartition("_")
            if separator and project_name:
                self._project_path = backup_path.parent.parent / (
                    f"{project_name}.labelproj"
                )
        self._project_dirty = True
        self._set_status(f"已从备份恢复工程：{backup_path.name}")

    def restore_project_from_version(self) -> None:
        if self._project_path is None:
            self._show_error("无法恢复版本快照", "请先保存或打开工程。")
            return
        snapshots = list_version_snapshots(self._project_path)
        if not snapshots:
            self._show_error("无法恢复版本快照", "当前工程没有可恢复的手动版本快照。")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "从版本快照恢复工程",
            str(snapshots[0].parent),
            "标注工程 (*.labelproj)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename or not self._confirm_discard_dirty_project():
            return
        try:
            restore_version_snapshot(self._project_path, Path(filename))
        except (OSError, ValueError) as error:
            self._show_error(
                "无法恢复版本快照",
                f"恢复版本快照失败：{self._file_error_tip(error)}",
            )
            return
        if self._load_project_path(self._project_path):
            self._set_status(f"已从版本快照恢复工程：{Path(filename).name}")

    def _load_project_path(self, path: Path) -> bool:
        try:
            project = load_project_v2(path)
        except (OSError, ValueError) as error:
            self._show_error(
                "无法打开工程", f"打开工程失败：{self._file_error_tip(error)}"
            )
            return False

        self._backup_timer.stop()
        self.project = project
        self._project_path = Path(path)
        self._project_dirty = False
        self._active_video_histories = {}
        self.historical_behavior_tags = ()
        self._rebuild_behavior_controls(())
        settings = project.global_settings
        self.date_edit.setText(settings.get("date", self.date_edit.text()))
        self.camera_edit.setText(settings.get("camera", self.camera_edit.text()))
        if settings.get("view"):
            self._set_custom_combo_value(
                self.view_combo,
                settings["view"],
                normalize_view_token,
            )
        output_dir = settings.get("output_dir", "")
        self.output_dir = Path(output_dir) if output_dir else None
        self.output_folder_label.setText(
            str(self.output_dir) if self.output_dir else "未选择输出文件夹"
        )
        self._set_output_folder_display()
        self._cleanup_orphaned_export_parts(prompt=True)

        entry = self._active_project_video()
        if entry is None:
            self.records = []
            self.source_path = None
            self.source_name = ""
            self.source_label.setText("未选择视频")
            self.video_info_title.setText("未选择视频")
            self.video_info_meta.setText("导入视频后开始标注")
            self._sync_project_video_combo()
            self._refresh_table()
            self._set_media_source(None)
        else:
            self.switch_active_video(entry.id)
        self._restore_project_export_queue()
        self._project_dirty = False
        self._backup_timer.stop()
        self._update_welcome_hint()
        self._set_status(f"已打开工程：{path.name}")
        return True

    @staticmethod
    def _normalized_import_source(
        source: str | Path, csv_path: Path
    ) -> tuple[Path, str]:
        source_path = Path(source).expanduser()
        if not source_path.is_absolute():
            source_path = csv_path.parent / source_path
        normalized_path = source_path.resolve(strict=False)
        return normalized_path, str(normalized_path).casefold()

    def relocate_missing_media(self) -> None:
        missing = [video.path for video in self.project.videos if not video.path.is_file()]
        if not missing:
            QMessageBox.information(self, "定位缺失视频", "当前工程没有缺失的视频源。")
            return
        directory = QFileDialog.getExistingDirectory(
            self, "选择素材搜索目录", "",
            options=QFileDialog.Option.ShowDirsOnly,
        )
        if not directory:
            return
        replacements = relocate_media_paths(missing, Path(directory))
        if not replacements:
            self._show_error("未找到视频", "没有找到唯一匹配的缺失视频文件。")
            return
        for video in self.project.videos:
            replacement = replacements.get(video.path)
            if replacement is not None:
                video.path = replacement
        active = self._active_project_video()
        if active is not None:
            self._bind_active_video(active)
            if active.path.is_file():
                self._set_media_source(active.path)
        self._mark_project_dirty()
        self._set_status(f"已重新定位 {len(replacements)} 个视频源")

    def open_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "导入视频",
            "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov *.m4v);;所有文件 (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        path = Path(filename)
        self.set_source_path(path)
        self._set_media_source(path)

    def import_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "导入片段 CSV",
            "",
            "CSV 文件 (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            imported_records = read_clip_csv(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error("无法导入 CSV", f"导入 CSV 失败：{error}")
            return
        self._register_imported_behavior_tags(imported_records)

        csv_path = Path(filename)
        active_video = self._active_project_video()
        source_groups: dict[str, tuple[Path, list[ClipRecord]]] = {}
        for record in imported_records:
            source_path, source_key = self._normalized_import_source(
                record.source, csv_path
            )
            if source_key not in source_groups:
                source_groups[source_key] = (source_path, [])
            source_groups[source_key][1].append(record)

        project_videos = {
            self._normalized_import_source(video.path, csv_path)[1]: video
            for video in self.project.videos
        }
        imported_videos: dict[str, ProjectVideo] = {}
        for source_key, (source_path, records) in source_groups.items():
            video = project_videos.get(source_key)
            if video is None:
                video = add_or_activate_video(
                    self.project,
                    source_path,
                )
            video.segments[:] = records
            project_videos[source_key] = video
            imported_videos[source_key] = video
            self._active_video_histories.pop(video.id, None)

        if imported_videos:
            active_key = (
                self._normalized_import_source(active_video.path, csv_path)[1]
                if active_video is not None
                else None
            )
            selected_video = imported_videos.get(active_key)
            if selected_video is None:
                selected_video = next(iter(imported_videos.values()))
            self.switch_active_video(selected_video.id)
        elif active_video is not None:
            active_video.segments.clear()
            self._active_video_histories.pop(active_video.id, None)
            self.switch_active_video(active_video.id)
        else:
            self.records = []

        if self.records:
            self.source_name = self.records[0].source
            self.source_label.setText(self.source_name)
            first_parsed: ParsedFilename | None = None
            for record in self.records:
                parsed = parse_filename(record.output)
                if parsed is None:
                    continue
                if first_parsed is None:
                    first_parsed = parsed
                self._set_custom_combo_value(
                    self.view_combo,
                    parsed.metadata.view,
                    normalize_view_token,
                )
                self._set_custom_combo_value(
                    self.polarity_combo,
                    parsed.polarity,
                    lambda value: normalize_label_token(value, "polarity"),
                )
                self._set_custom_combo_value(
                    self.lighting_combo,
                    parsed.lighting,
                    lambda value: normalize_label_token(value, "lighting"),
                )
            if first_parsed is not None:
                self._restore_parsed_metadata(first_parsed)
            self.sequence_spin.setValue(
                next_sequence([record.sequence for record in self.records])
            )
        self._editing_index = None
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()
        self._set_status(f"已导入 {len(imported_records)} 个任务")

    def import_preannotation_json(self) -> None:
        if not self.source_name:
            self._show_error("无法导入预标注", "请先选择要人工复核的源视频。")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "导入预标注 JSON",
            "",
            "JSON 文件 (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            annotations = read_preannotation_json(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error("无法导入预标注", str(error))
            return
        self._show_preannotation_preview(annotations)

    def _show_preannotation_preview(
        self, annotations: Sequence[PreAnnotation]
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("预标注复核")
        dialog.setMinimumWidth(680)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(annotations), 5, dialog)
        table.setHorizontalHeaderLabels(("导入", "开始", "结束", "标签", "正负例"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, annotation in enumerate(annotations):
            selected = QTableWidgetItem()
            selected.setFlags(
                selected.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            selected.setCheckState(Qt.CheckState.Checked)
            table.setItem(row, 0, selected)
            table.setItem(row, 1, QTableWidgetItem(f"{annotation.start_seconds:.3f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{annotation.end_seconds:.3f}"))
            table.setItem(row, 3, QTableWidgetItem(", ".join(annotation.behaviors)))
            table.setItem(row, 4, QTableWidgetItem(annotation.polarity))
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("导入已勾选片段")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_annotations = [
            annotation
            for row, annotation in enumerate(annotations)
            if table.item(row, 0).checkState() == Qt.CheckState.Checked
        ]
        self._apply_preannotations(selected_annotations)

    def _apply_preannotations(
        self, annotations: Sequence[PreAnnotation]
    ) -> None:
        if not annotations:
            return
        try:
            source = self.source_name.strip()
            if not source:
                raise ValueError("请先选择源视频。")
            metadata = ProjectMetadata(
                date=self.date_edit.text().strip(),
                camera=self.camera_edit.text().strip(),
                view=self.view_combo.currentText(),
            )
            existing_outputs = {record.output for record in self.records}
            sequence = next_sequence(record.sequence for record in self.records)
            imported: list[ClipRecord] = []
            for annotation in annotations:
                behaviors = tuple(
                    dict.fromkeys(
                        normalize_label_token(tag, "行为标签")
                        for tag in annotation.behaviors
                    )
                )
                polarity = normalize_label_token(
                    annotation.polarity or self.polarity_combo.currentText(),
                    "正负例",
                )
                lighting = normalize_label_token(
                    annotation.lighting or self.lighting_combo.currentText(),
                    "光照",
                )
                output = build_filename(
                    metadata, behaviors, polarity, lighting, sequence
                )
                if output in existing_outputs:
                    raise ValueError(f"导出文件名重复：{output}")
                imported.append(
                    ClipRecord(
                        source=source,
                        start_seconds=annotation.start_seconds,
                        end_seconds=annotation.end_seconds,
                        output=output,
                        behaviors=behaviors,
                        polarity=polarity,
                        lighting=lighting,
                        sequence=sequence,
                    )
                )
                existing_outputs.add(output)
                sequence += 1
        except ValueError as error:
            self._show_error("无法导入预标注", str(error))
            return

        before = list(self.records)
        self._register_imported_behavior_tags(imported)
        self.records.extend(imported)
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self.sequence_spin.setValue(sequence)
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()
        self._set_status(f"已导入 {len(imported)} 个待复核预标注片段")

    def save_full_csv(self) -> None:
        if not self.records:
            self._show_error("没有片段任务", "导出完整 CSV 前请至少添加一个片段。")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出完整标注 CSV", "clips-full.csv", "CSV 文件 (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            write_full_clip_csv(Path(filename), self.records)
        except (OSError, ValueError) as error:
            self._show_error("无法导出完整 CSV", f"导出失败：{self._file_error_tip(error)}")
            return
        self._set_status(f"已导出完整标注 CSV：{filename}")

    def import_full_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入完整标注 CSV", "", "CSV 文件 (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            imported_records = read_full_clip_csv(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error("无法导入完整 CSV", f"导入失败：{error}")
            return
        if not imported_records:
            self._show_error("无法导入完整 CSV", "CSV 中没有可导入的片段。")
            return
        self._register_imported_behavior_tags(imported_records)
        active_video = self._active_project_video()
        if active_video is None:
            source = Path(imported_records[0].source)
            active_video = add_or_activate_video(self.project, source)
        self.records = list(imported_records)
        active_video.segments[:] = self.records
        self.source_name = self.records[0].source
        self.source_label.setText(self.source_name)
        self._active_video_histories.pop(active_video.id, None)
        self._editing_index = None
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()
        self._set_status(f"已导入 {len(self.records)} 个完整标注片段")

    def show_project_statistics(self) -> None:
        stats = calculate_project_statistics(self.project)
        status_text = "、".join(
            f"{STATUS_LABELS.get(key, key)} {value}" for key, value in stats.status_counts.items()
        ) or "无"
        behavior_text = "、".join(
            f"{key} {value}" for key, value in stats.behavior_counts.items()
        ) or "无"
        QMessageBox.information(
            self,
            "工程统计",
            (f"视频数量：{stats.video_count}\n片段数量：{stats.segment_count}\n"
             f"标注时长：{format_seconds(stats.total_duration)}\n"
             f"正样本：{stats.positive_count}，负样本：{stats.negative_count}，未设置：{stats.unlabeled_count}\n"
             f"导出状态：{status_text}\n行为标签：{behavior_text}"),
        )

    def export_project_statistics(self) -> None:
        default_name = "project-statistics.json"
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出工程统计", default_name, "JSON 文件 (*.json)"
        )
        if not filename:
            return
        try:
            target = write_project_statistics_report(Path(filename), self.project)
        except OSError as error:
            self._show_error("无法导出工程统计", f"导出失败：{self._file_error_tip(error)}")
            return
        self._set_status(f"已导出工程统计：{target.name}")

    def show_available_exporters(self) -> None:
        exporters = list_exporters()
        text = "\n".join(f"{name}  v{version}" for name, version in exporters)
        QMessageBox.information(self, "可用导出器", text or "暂无可用导出器")

    def scan_plugin_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "扫描插件目录")
        if not directory:
            return
        try:
            loaded = load_plugin_directory(Path(directory))
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            self._show_error("插件扫描失败", str(error))
            return
        self._set_status("已扫描插件目录：" + (", ".join(loaded) or "无新增导出器"))

    def load_export_plugin(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载导出插件", "", "Python 插件 (*.py)"
        )
        if not filename:
            return
        try:
            loaded = load_plugin_file(Path(filename))
        except (ImportError, OSError, ValueError, RuntimeError) as error:
            self._show_error("插件加载失败", str(error))
            return
        self._set_status("已加载导出插件：" + (", ".join(loaded) or "无新增导出器"))

    def show_project_validation(self) -> None:
        issues = validate_project(self.project)
        if not issues:
            QMessageBox.information(self, "工程质量检查", "未发现问题。")
            self._set_status("工程质量检查通过")
            return
        lines = []
        for issue in issues:
            location = f"视频 {issue.video_id}，片段 {issue.segment_index + 1}" if issue.segment_index is not None else f"视频 {issue.video_id}"
            lines.append(f"[{issue.severity}] {location}：{issue.message}")
        QMessageBox.warning(self, "工程质量检查", "\n".join(lines))
        self._set_status(f"工程质量检查发现 {len(issues)} 个问题")

    def save_csv(self) -> None:
        if not self.records:
            self._show_error("没有片段任务", "保存 CSV 前请至少添加一个片段。")
            return
        default_name = (
            f"{Path(self.source_name).stem}_clips.csv"
            if self.source_name
            else "clips.csv"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "保存标注 CSV",
            default_name,
            "CSV 文件 (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            write_clip_csv(Path(filename), self.records)
        except OSError as error:
            self._show_error(
                "无法保存 CSV", f"保存 CSV 失败：{self._file_error_tip(error)}"
            )
            return
        self._set_status(f"已保存 CSV：{filename}")

    def export_dataset(self) -> None:
        if not self.records:
            self._show_error("没有片段任务", "导出数据集前请至少添加一个片段。")
            return
        format_name, accepted = QInputDialog.getItem(
            self,
            "导出数据集",
            "格式",
            ("JSONL", "YOLO 标签"),
            0,
            False,
        )
        if not accepted:
            return
        if format_name == "JSONL":
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "导出 JSONL 数据集",
                "clips.jsonl",
                "JSONL 文件 (*.jsonl)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not filename:
                return
            try:
                write_clip_jsonl(Path(filename), self.records)
            except OSError as error:
                self._show_error(
                    "无法导出 JSONL", self._file_error_tip(error)
                )
                return
            self._set_status(f"已导出 JSONL 数据集：{filename}")
            return

        directory = QFileDialog.getExistingDirectory(
            self,
            "选择 YOLO 标签目录",
            str(self.output_dir or Path.home()),
            options=(
                QFileDialog.Option.ShowDirsOnly
                | QFileDialog.Option.DontUseNativeDialog
            ),
        )
        if not directory:
            return
        try:
            write_clip_yolo(Path(directory), self.records)
        except OSError as error:
            self._show_error("无法导出 YOLO 标签", self._file_error_tip(error))
            return
        self._set_status(f"已导出 YOLO 标签：{directory}")

    def export_plugin_dataset(self) -> None:
        if not self.records:
            self._show_error("没有片段任务", "插件导出前请至少添加一个片段。")
            return
        exporters = list_exporters()
        if not exporters:
            self._show_error("没有可用导出器", "请先加载或注册一个导出器。")
            return
        labels = [f"{name} v{version}" for name, version in exporters]
        choice, accepted = QInputDialog.getItem(self, "插件数据集导出", "导出器", labels, 0, False)
        if not accepted:
            return
        name = exporters[labels.index(choice)][0]
        directory = QFileDialog.getExistingDirectory(self, "选择插件导出目录", str(self.output_dir or Path.home()))
        if not directory:
            return
        try:
            prepared = self._prepare_export_records(self.records, [self.source_path] * len(self.records) if self.source_path else [Path(record.source) for record in self.records])
            if prepared is None:
                return
            export_records, _ = prepared
            export_with(get_exporter(name), export_records, Path(directory))
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            self._show_error("插件导出失败", self._file_error_tip(error))
            return
        self._set_status(f"插件导出完成：{name} → {directory}")

    def select_output_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出文件夹",
            str(self.output_dir or Path.home()),
            options=(
                QFileDialog.Option.ShowDirsOnly
                | QFileDialog.Option.DontUseNativeDialog
            ),
        )
        if not directory:
            return
        self.output_dir = Path(directory)
        self._set_output_folder_display()
        self._cleanup_orphaned_export_parts(prompt=True)
        self._mark_project_dirty()
        self._set_status(f"输出文件夹：{self.output_dir}")

    def set_clip_range(self, start_seconds: float, end_seconds: float) -> None:
        self.start_spin.setValue(start_seconds)
        self.end_spin.setValue(end_seconds)
        self._sync_timeline_segment_range()

    def _sync_timeline_segment_range(self, *_args: object) -> None:
        if not hasattr(self, "timeline_slider"):
            return
        self.timeline_slider.set_segment_ranges([
            (round(record.start_seconds * 1000), round(record.end_seconds * 1000))
            for record in self.records
            if record.source == self.source_name
        ])
        self.timeline_slider.set_segment_range(
            round(self.start_spin.value() * 1000),
            round(self.end_spin.value() * 1000),
        )

    def _set_clip_range_from_timeline(
        self, start_milliseconds: int, end_milliseconds: int
    ) -> None:
        self.start_spin.setValue(start_milliseconds / 1000)
        self.end_spin.setValue(end_milliseconds / 1000)

    def selected_behaviors(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self.behavior_tag_combo.checked_tags(),
                    *self.historical_behavior_tags,
                )
            )
        )

    def add_custom_behavior_tag(self) -> None:
        value = self.custom_behavior_tag_edit.text()
        try:
            normalized = normalize_label_token(value, "行为标签")
        except ValueError as error:
            self._show_error("自定义标签无效", str(error))
            return
        if normalized in BEHAVIOR_LABELS:
            self._show_error("自定义标签无效", "内置行为标签无需重复添加。")
            return
        if normalized in self.project.custom_behavior_tags:
            self._show_error("自定义标签无效", "该自定义行为标签已存在。")
            return

        selected = self.selected_behaviors()
        start_seconds = self.start_spin.value()
        end_seconds = self.end_spin.value()
        self.project.custom_behavior_tags.append(normalized)
        self.custom_behavior_tag_edit.clear()
        self._rebuild_behavior_controls(selected)
        self.set_clip_range(start_seconds, end_seconds)
        self._mark_project_dirty()

    def set_custom_behavior_tag_color(self, tag: str, color: str) -> None:
        if tag not in self.project.custom_behavior_tags:
            raise ValueError("只能为自定义标签设置颜色")
        selected_color = QColor(color)
        if not selected_color.isValid():
            raise ValueError("标签颜色无效")
        self.project.custom_behavior_tag_colors[tag] = selected_color.name().upper()
        self._rebuild_behavior_controls(self.selected_behaviors())
        self._mark_project_dirty()

    def _choose_selected_custom_tag_color(self) -> None:
        tag = self.custom_tag_library_combo.currentData()
        if not isinstance(tag, str):
            return
        current = QColor(
            self.project.custom_behavior_tag_colors.get(tag, "#3F9CFF")
        )
        color = QColorDialog.getColor(current, self, "设置标签颜色")
        if not color.isValid():
            return
        self.set_custom_behavior_tag_color(tag, color.name().upper())

    def export_tag_preset(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "导出标签预设",
            "标签预设.tagpreset.json",
            "标签预设 (*.tagpreset.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            path = save_tag_preset(
                Path(filename),
                self.project.custom_behavior_tags,
                self.project.custom_behavior_tag_colors,
            )
        except (OSError, ValueError) as error:
            self._show_error(
                "无法导出标签预设",
                f"导出标签预设失败：{self._file_error_tip(error)}",
            )
            return
        self._set_status(f"已导出标签预设：{path.name}")

    def import_tag_preset(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "导入标签预设",
            "",
            "标签预设 (*.tagpreset.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            tags, colors = load_tag_preset(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error(
                "无法导入标签预设",
                f"导入标签预设失败：{self._file_error_tip(error)}",
            )
            return
        selected = self.selected_behaviors()
        self.project.custom_behavior_tags = list(
            dict.fromkeys((*self.project.custom_behavior_tags, *tags))
        )
        self.project.custom_behavior_tag_colors.update(colors)
        self._rebuild_behavior_controls(selected)
        self._mark_project_dirty()
        self._set_status(f"已导入标签预设：{Path(filename).name}")

    def _register_imported_behavior_tags(
        self,
        records: Sequence[ClipRecord],
    ) -> bool:
        known = set(self._available_behavior_tags())
        additions = []
        for record in records:
            for behavior in record.behaviors:
                if behavior not in known:
                    additions.append(behavior)
                    known.add(behavior)
        if not additions:
            return False

        selected = self.selected_behaviors()
        self.project.custom_behavior_tags.extend(additions)
        self._rebuild_behavior_controls(selected)
        return True

    def _remove_custom_behavior_tag(self, tag: str) -> None:
        if tag not in self.project.custom_behavior_tags:
            return

        is_referenced = any(
            tag in record.behaviors
            for video in self.project.videos
            for record in video.segments
        )
        if is_referenced:
            answer = QMessageBox.question(
                self,
                "删除自定义标签",
                (
                    f"“{tag}” 已被历史片段使用。删除后仅移除可选标签按钮，"
                    "历史片段中的标签数据会保留。是否继续？"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if self._editing_index is not None and 0 <= self._editing_index < len(
            self.records
        ):
            selected = self.records[self._editing_index].behaviors
        else:
            selected = tuple(
                behavior
                for behavior in self.selected_behaviors()
                if behavior != tag
            )
        self.project.custom_behavior_tags.remove(tag)
        self.project.custom_behavior_tag_colors.pop(tag, None)
        self._rebuild_behavior_controls(selected)
        self._mark_project_dirty()

    def _remove_selected_custom_behavior_tag(self) -> None:
        tag = self.custom_tag_library_combo.currentData()
        if isinstance(tag, str):
            self._remove_custom_behavior_tag(tag)

    def add_or_update_clip(self) -> bool:
        try:
            source = self.source_name.strip()
            if not source:
                raise ValueError("添加片段前请先选择源视频。")
            start_seconds = self.start_spin.value()
            end_seconds = self.end_spin.value()
            if end_seconds <= start_seconds:
                raise ValueError("结束时间必须晚于开始时间。")

            metadata = ProjectMetadata(
                date=self.date_edit.text().strip(),
                camera=self.camera_edit.text().strip(),
                view=self.view_combo.currentText(),
            )
            behaviors = self.selected_behaviors()
            polarity = self.polarity_combo.currentText()
            lighting = self.lighting_combo.currentText()
            stratum = self.stratum_combo.currentData() or ""
            sequence = self.sequence_spin.value()
            output = build_filename(
                metadata, behaviors, polarity, lighting, sequence
            )
            self._assert_output_is_unique(output)
        except ValueError as error:
            self._show_error("无法添加片段", f"添加片段失败：{error}")
            return False

        record = ClipRecord(
            source=source,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            output=output,
            behaviors=behaviors,
            polarity=polarity,
            lighting=lighting,
            data_stratum=stratum,
            sequence=sequence,
            note=self.note_edit.text().strip(),
            events=self._collect_events(),
            age=self.age_combo.currentData() or "",
            face_familiarity=self.face_familiarity_combo.currentData() or "",
            reid_familiarity=self.reid_familiarity_combo.currentData() or "",
            person_count=self.person_count_spin.value(),
        )
        before = list(self.records)
        is_new_record = self._editing_index is None
        if is_new_record:
            self.records.append(record)
            self._set_status(f"已添加片段 {sequence:03d}")
        else:
            self.records[self._editing_index] = record
            self._set_status(f"已更新片段 {sequence:03d}")

        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._refresh_table()
        if is_new_record and not before:
            self.project_header.setChecked(False)
        self._mark_project_dirty()
        self._last_annotation_labels = (behaviors, polarity, lighting)
        self._prepare_next_clip(record.end_seconds)
        if is_new_record:
            self.task_table.scrollToBottom()
        self._update_history_controls()
        return True

    def remove_selected_clip(self) -> None:
        self._delete_selected_records()

    def undo_segments(self) -> None:
        history = self._active_history()
        if history is None or not history.can_undo():
            return
        self.records[:] = history.undo(self.records)
        self._editing_index = None
        self.task_table.clearSelection()
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()

    def redo_segments(self) -> None:
        history = self._active_history()
        if history is None or not history.can_redo():
            return
        self.records[:] = history.redo(self.records)
        self._editing_index = None
        self.task_table.clearSelection()
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()

    def clear_editor(self) -> None:
        self._editing_index = None
        self.start_spin.setValue(0)
        self.end_spin.setValue(0)
        self.historical_behavior_tags = ()
        self._rebuild_behavior_controls(())
        self.polarity_combo.setCurrentIndex(0)
        self.lighting_combo.setCurrentIndex(0)
        self.stratum_combo.setCurrentIndex(0)
        self.note_edit.clear()
        self._clear_event_rows()
        self.age_combo.setCurrentIndex(0)
        self.face_familiarity_combo.setCurrentIndex(0)
        self.reid_familiarity_combo.setCurrentIndex(0)
        self.person_count_spin.setValue(0)
        self.sequence_spin.setValue(
            next_sequence([record.sequence for record in self.records])
        )
        self.add_button.setText("添加片段")
        self._update_filename_preview()

    def _add_event_row(
        self,
        event_type: str = "",
        start_ms: int = 0,
        end_ms: int = 0,
    ) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        type_combo = QComboBox()
        type_combo.setEditable(True)
        type_combo.addItems(self._available_behavior_tags())
        type_combo.setCurrentIndex(-1)
        type_combo.lineEdit().setPlaceholderText("事件类型")
        if event_type:
            index = type_combo.findText(event_type)
            if index < 0:
                type_combo.addItem(event_type)
                index = type_combo.count() - 1
            type_combo.setCurrentIndex(index)
        start_spin = QSpinBox()
        start_spin.setRange(0, 99_999_999)
        start_spin.setSingleStep(100)
        start_spin.setValue(start_ms)
        start_spin.setSuffix(" ms")
        start_spin.setToolTip("相对样本起点的开始毫秒")
        end_spin = QSpinBox()
        end_spin.setRange(0, 99_999_999)
        end_spin.setSingleStep(100)
        end_spin.setValue(end_ms)
        end_spin.setSuffix(" ms")
        end_spin.setToolTip("相对样本起点的结束毫秒")
        remove_button = QPushButton("×")
        remove_button.setFixedWidth(28)
        remove_button.setToolTip("删除此事件")
        remove_button.clicked.connect(lambda: self._remove_event_row(row))
        row_layout.addWidget(type_combo, stretch=2)
        row_layout.addWidget(start_spin, stretch=1)
        row_layout.addWidget(end_spin, stretch=1)
        row_layout.addWidget(remove_button)
        self.events_list_layout.addWidget(row)
        self._event_rows.append((type_combo, start_spin, end_spin, row))

    def _remove_event_row(self, row_widget: QWidget) -> None:
        for entry in list(self._event_rows):
            if entry[3] is row_widget:
                self.events_list_layout.removeWidget(row_widget)
                row_widget.deleteLater()
                self._event_rows.remove(entry)
                break

    def _clear_event_rows(self) -> None:
        while self.events_list_layout.count():
            item = self.events_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._event_rows.clear()

    def _collect_events(self) -> list[EventRecord]:
        events: list[EventRecord] = []
        for type_combo, start_spin, end_spin, _row in self._event_rows:
            event_type = type_combo.currentText().strip()
            if not event_type:
                continue
            events.append(
                EventRecord(
                    event_type=event_type,
                    start_time_ms=start_spin.value(),
                    end_time_ms=end_spin.value(),
                )
            )
        return events

    def _populate_events(self, events: Collection[EventRecord]) -> None:
        self._clear_event_rows()
        for event in events:
            self._add_event_row(
                event_type=event.event_type,
                start_ms=event.start_time_ms,
                end_ms=event.end_time_ms,
            )

    def _restore_person_attributes(self, record: ClipRecord) -> None:
        self.age_combo.setCurrentIndex(
            self.age_combo.findData(record.age) if record.age else 0
        )
        self.face_familiarity_combo.setCurrentIndex(
            self.face_familiarity_combo.findData(record.face_familiarity)
            if record.face_familiarity
            else 0
        )
        self.reid_familiarity_combo.setCurrentIndex(
            self.reid_familiarity_combo.findData(record.reid_familiarity)
            if record.reid_familiarity
            else 0
        )
        self.person_count_spin.setValue(record.person_count or 0)

    def _prepare_next_clip(self, saved_end_seconds: float) -> None:
        self._editing_index = None
        self.add_button.setText("添加片段")
        self.set_clip_range(saved_end_seconds, saved_end_seconds)
        self.historical_behavior_tags = ()
        remembered_behaviors = (
            self._last_annotation_labels[0] if self._remember_last_labels else ()
        )
        self._rebuild_behavior_controls(remembered_behaviors)
        self.note_edit.clear()
        self._clear_event_rows()
        self.age_combo.setCurrentIndex(0)
        self.face_familiarity_combo.setCurrentIndex(0)
        self.reid_familiarity_combo.setCurrentIndex(0)
        self.person_count_spin.setValue(0)
        self.sequence_spin.setValue(
            next_sequence([record.sequence for record in self.records])
        )
        self._update_filename_preview()

    def confirm_and_next_pending(self) -> None:
        """Save the current clip, then jump to the next pending review task."""
        if not self.add_or_update_clip():
            return
        self._jump_to_next_pending(0)

    def _jump_to_next_pending(self, start: int = 0) -> bool:
        if not self.records:
            self._set_status("没有待审核片段")
            return False
        total = len(self.records)
        for offset in range(total):
            index = (start + offset) % total
            if (
                self.records[index].review_status == "pending"
                and not self.task_table.isRowHidden(index)
            ):
                self.task_table.selectRow(index)
                item = self.task_table.item(index, 0)
                if item is not None:
                    self.task_table.scrollToItem(item)
                self._set_status(f"跳转到待审核片段 #{index + 1}")
                return True
        self._set_status("没有更多待审核片段")
        return False

    def _jump_to_pending(self, direction: int) -> None:
        """J/K 上/下一条待审核片段导航。"""
        if not self.records:
            self._set_status("没有待审核片段")
            return
        total = len(self.records)
        current = self.task_table.currentRow()
        if current < 0:
            current = 0
        for step in range(1, total + 1):
            index = (current + direction * step) % total
            if (
                self.records[index].review_status == "pending"
                and not self.task_table.isRowHidden(index)
            ):
                self.task_table.selectRow(index)
                item = self.task_table.item(index, 0)
                if item is not None:
                    self.task_table.scrollToItem(item)
                self._set_status(f"跳转到待审核片段 #{index + 1}")
                return
        self._set_status("没有更多待审核片段")

    def _review_current_selected(self, review_status: str) -> None:
        """Fast no-dialog review: 1 approved / 2 needs_fix / 3 rejected / 4 pending."""
        if review_status not in REVIEW_STATUSES:
            return
        indexes = self._selected_record_indexes()
        if not indexes:
            self._set_status("没有选中片段进行审核")
            return
        before = list(self.records)
        reviewed_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        rejection_reason = {
            "needs_fix": "快速审核：需修正",
            "rejected": "快速审核：剔除",
        }.get(review_status, "")
        for index in indexes:
            record = self.records[index]
            record.review_status = review_status
            record.reviewer = "local-user" if review_status != "pending" else ""
            record.reviewed_at = reviewed_at if review_status != "pending" else ""
            record.review_comment = ""
            record.rejection_reason = rejection_reason
            record.review_history.append({
                "status": review_status,
                "reviewer": record.reviewer,
                "reviewed_at": record.reviewed_at,
                "comment": record.review_comment,
                "rejection_reason": record.rejection_reason,
            })
        self._refresh_table()
        self._mark_project_dirty()
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._update_history_controls()
        labels = REVIEW_STATUS_LABELS
        self._set_status(
            f"快速审核：{len(indexes)} 个片段标记为{labels[review_status]}"
        )
        self._jump_to_next_pending(indexes[-1] + 1)

    def _toggle_behavior_shortcut(self, tag: str) -> None:
        if tag not in self._available_behavior_tags():
            return
        selected = tag in self.selected_behaviors()
        self.behavior_tag_combo.set_tag_checked(tag, not selected)
        self._set_status(f"{'取消' if selected else '选择'}行为标签：{tag}")

    def _toggle_review_mode(self, enabled: bool) -> None:
        self._review_mode = enabled
        self.review_mode_button.setText(f"审核模式：{'开' if enabled else '关'}")
        if enabled:
            self._set_status("审核模式已开启：1 通过 / 2 需修正 / 3 剔除 / 4 待审核")
        else:
            self._set_status("审核模式已关闭：数字键 1-9 选择行为标签")

    def _toggle_remember_labels(self, enabled: bool) -> None:
        self._remember_last_labels = enabled
        self.remember_labels_button.setText(f"记住标签：{'开' if enabled else '关'}")
        self._set_status(
            "已开启记住上次标签" if enabled else "已关闭记住上次标签"
        )

    def _text_input_focused(self) -> bool:
        focus = QApplication.focusWidget()
        return isinstance(
            focus,
            (
                QLineEdit,
                QSpinBox,
                QDoubleSpinBox,
                QPlainTextEdit,
                QComboBox,
                QKeySequenceEdit,
            ),
        )

    def _dispatch_number_key(self, digit: int) -> None:
        if not 1 <= digit <= 9:
            return
        if self._review_mode:
            status = {1: "approved", 2: "needs_fix", 3: "rejected", 4: "pending"}.get(digit)
            if status is not None:
                self._review_current_selected(status)
            return
        tags = self._available_behavior_tags()
        index = digit - 1
        if index < len(tags):
            self._toggle_behavior_shortcut(tags[index])

    def keyPressEvent(self, event) -> None:
        text = event.text()
        if (
            not self._text_input_focused()
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            if text.isdigit():
                self._dispatch_number_key(int(text))
                event.accept()
                return
            if text.lower() == "j":
                self._jump_to_pending(-1)
                event.accept()
                return
            if text.lower() == "k":
                self._jump_to_pending(1)
                event.accept()
                return
        super().keyPressEvent(event)

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _set_start_from_player(self) -> None:
        self.start_spin.setValue(self.player.position() / 1000)
        self.set_end_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_end_from_player(self) -> None:
        self.end_spin.setValue(self.player.position() / 1000)
        self.quick_add_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_clip_range_label(self, *_args: object) -> None:
        if hasattr(self, "clip_range_label"):
            self.clip_range_label.setText(
                f"起 {self._short_seconds(self.start_spin.value())} · "
                f"止 {self._short_seconds(self.end_spin.value())}"
            )

    def _short_seconds(self, seconds: float) -> str:
        total_ms = round(seconds * 1000)
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, ms = divmod(rem, 1000)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}.{ms:03d}"
        return f"{minutes}:{secs:02d}.{ms:03d}"

    def _current_fps(self) -> float:
        video = self._active_project_video()
        if video is None or not video.metadata:
            return 0.0
        try:
            fps = float(video.metadata.get("fps", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
        return fps if fps > 0 else 0.0

    def _frame_position_text(self, milliseconds: int) -> str:
        fps = self._current_fps()
        if fps <= 0:
            return ""
        frame = int(round(milliseconds / 1000.0 * fps))
        return f"帧 {frame} · {fps:g}fps"

    def _step_frame(self, direction: int) -> None:
        fps = self._current_fps()
        step_ms = round(1000.0 / fps) if fps > 0 else 33
        self._seek_relative(step_ms * direction)

    def _seek_relative(self, milliseconds: int) -> None:
        duration = self.player.duration()
        position = max(0, min(duration, self.player.position() + milliseconds))
        self.player.setPosition(position)

    def _seek_to_milliseconds(self, milliseconds: int) -> None:
        if milliseconds != self.player.position():
            self.player.setPosition(milliseconds)

    def _jump_to_timecode(self) -> None:
        raw = self.goto_edit.text().strip()
        if not raw:
            return
        seconds = self._parse_timecode(raw)
        if seconds is None:
            self._set_status(f"无法识别时间码：{raw}")
            return
        duration = self.player.duration()
        position = max(0, min(duration, round(seconds * 1000)))
        self.player.setPosition(position)
        self._set_status(f"已跳转到 {format_seconds(position / 1000)}")
        self.goto_edit.clear()

    def _parse_timecode(self, raw: str) -> float | None:
        try:
            parts = raw.replace(",", ".").split(":")
            if len(parts) == 1:
                return float(parts[0])
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except ValueError:
            pass
        return None

    def _on_speed_preset_changed(self) -> None:
        rate = self.speed_combo.currentData()
        if rate is None:
            self.custom_speed_spin.setFocus()
            self.custom_speed_spin.selectAll()
            return
        self._apply_playback_rate(float(rate))

    def _on_custom_speed_committed(self) -> None:
        self._apply_playback_rate(self.custom_speed_spin.value())

    def _apply_playback_rate(self, rate: float) -> bool:
        if not 0.1 <= rate <= 4.0:
            self._sync_playback_rate_controls(self._last_playback_rate)
            self._set_status("播放速度需在 0.1x 到 4.0x 之间")
            return False

        self.player.setPlaybackRate(rate)
        self._last_playback_rate = rate
        self._sync_playback_rate_controls(rate)
        return True

    def _sync_playback_rate_controls(self, rate: float) -> None:
        with QSignalBlocker(self.speed_combo), QSignalBlocker(
            self.custom_speed_spin
        ):
            self.custom_speed_spin.setValue(rate)
            preset_index = self.speed_combo.findData(rate)
            if preset_index >= 0:
                self.speed_combo.setCurrentIndex(preset_index)
            else:
                self.speed_combo.setCurrentIndex(
                    self.speed_combo.findData(None)
                )
        self.playback_rate_badge.setText(f"{rate:g}x")

    def _update_position(self, milliseconds: int) -> None:
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setValue(milliseconds)
        self.position_label.setText(format_seconds(milliseconds / 1000))
        if hasattr(self, "frame_info_label"):
            self.frame_info_label.setText(self._frame_position_text(milliseconds))

    def _update_duration(self, milliseconds: int) -> None:
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setRange(0, max(0, milliseconds))
        self.duration_label.setText(format_seconds(milliseconds / 1000))
        self._sync_timeline_segment_range()

    def _update_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("暂停" if is_playing else "播放")
        icon = (
            QStyle.StandardPixmap.SP_MediaPause
            if is_playing
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_button.setIcon(self.style().standardIcon(icon))

    def _update_video_placeholder(
        self, status: QMediaPlayer.MediaStatus
    ) -> None:
        if status in (
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        ):
            self.video_placeholder_item.setText("正在加载视频…")
            self.video_placeholder_item.setVisible(True)
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            self.video_placeholder_item.setText("导入视频后开始标注")
            self.video_placeholder_item.setVisible(True)
        elif status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
        ):
            self.video_placeholder_item.setVisible(False)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.video_placeholder_item.setText("无法加载视频")
            self.video_placeholder_item.setVisible(True)
        self._resize_video_item()

    def _media_error(self, _error: QMediaPlayer.Error, text: str) -> None:
        if text:
            self._set_status(f"视频播放错误：{text}")

    def _update_filename_preview(self) -> None:
        try:
            metadata = ProjectMetadata(
                date=self.date_edit.text().strip(),
                camera=self.camera_edit.text().strip(),
                view=self.view_combo.currentText(),
            )
            self.filename_preview.setText(
                build_filename(
                    metadata,
                    self.selected_behaviors(),
                    self.polarity_combo.currentText(),
                    self.lighting_combo.currentText(),
                    self.sequence_spin.value(),
                )
            )
        except ValueError:
            self.filename_preview.clear()

    def _assert_output_is_unique(self, output: str) -> None:
        for index, record in enumerate(self.records):
            if index != self._editing_index and record.output.lower() == output.lower():
                raise ValueError(f"输出文件名重复：{output}")

    def _refresh_table(self) -> None:
        with QSignalBlocker(self.task_table):
            self.task_table.setRowCount(len(self.records))
            for row, record in enumerate(self.records):
                values = (
                    f"{record.sequence:03d}" if record.sequence else "",
                    format_seconds(record.start_seconds),
                    format_seconds(record.end_seconds),
                    format_seconds(record.end_seconds - record.start_seconds),
                    "+".join(record.behaviors),
                    record.polarity,
                    record.lighting,
                    record.output,
                    STATUS_LABELS.get(record.status, record.status),
                    record.error,
                    record.note,
                    STRATUM_LABELS.get(record.data_stratum, record.data_stratum) if record.data_stratum else "",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column != 7:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 8:
                        self._apply_status_color(item, record.status)
                    self.task_table.setItem(row, column, item)
        self._sync_filter_options()
        self._apply_table_filters()
        self._update_annotation_stats()
        if hasattr(self, "timeline_slider"):
            self._sync_timeline_segment_range()

    def _sync_filter_options(self) -> None:
        current_behavior = self.behavior_filter_combo.currentData()
        with QSignalBlocker(self.behavior_filter_combo):
            self.behavior_filter_combo.clear()
            self.behavior_filter_combo.addItem("全部行为", None)
            for behavior in self._available_behavior_tags():
                self.behavior_filter_combo.addItem(behavior, behavior)
            behavior_index = self.behavior_filter_combo.findData(current_behavior)
            self.behavior_filter_combo.setCurrentIndex(
                behavior_index if behavior_index >= 0 else 0
            )

        filter_options = (
            (
                self.polarity_filter_combo,
                (record.polarity for record in self.records),
                lambda value: value,
            ),
            (
                self.status_filter_combo,
                (record.status for record in self.records),
                lambda value: STATUS_LABELS.get(value, value),
            ),
        )
        for combo, values, label_for in filter_options:
            current_data = combo.currentData()
            with QSignalBlocker(combo):
                for value in values:
                    if value and combo.findData(value) < 0:
                        combo.addItem(label_for(value), value)
                current_index = combo.findData(current_data)
                if current_index >= 0:
                    combo.setCurrentIndex(current_index)

        for combo in (
            self.behavior_filter_combo,
            self.polarity_filter_combo,
            self.status_filter_combo,
            self.review_filter_combo,
            self.sort_combo,
        ):
            self._set_combo_visible_item_count(combo)

    def _apply_table_filters(self) -> None:
        behavior = self.behavior_filter_combo.currentData()
        polarity = self.polarity_filter_combo.currentData()
        status = self.status_filter_combo.currentData()
        review_status = self.review_filter_combo.currentData()
        search_text = self.search_edit.text().strip().casefold()
        selection_model = self.task_table.selectionModel()
        visible_count = 0
        for row, record in enumerate(self.records):
            visible = (
                (behavior is None or behavior in record.behaviors)
                and (polarity is None or polarity == record.polarity)
                and (status is None or status == record.status)
                and (review_status is None or review_status == record.review_status)
                and (
                    not search_text
                    or search_text
                    in " ".join(
                        (record.source, *record.behaviors, record.note)
                    ).casefold()
                )
            )
            self.task_table.setRowHidden(row, not visible)
            if visible:
                visible_count += 1
            if not visible:
                selection_model.select(
                    self.task_table.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.Deselect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
        if not self.records:
            self.filter_result_label.setText("暂无片段任务")
        elif visible_count:
            self.filter_result_label.setText(
                f"显示 {visible_count}/{len(self.records)} 个片段"
            )
        else:
            self.filter_result_label.setText(
                f"没有匹配的片段 (0/{len(self.records)})，请清空筛选。"
            )

    def clear_table_filters(self) -> None:
        self.behavior_filter_combo.setCurrentIndex(0)
        self.polarity_filter_combo.setCurrentIndex(0)
        self.status_filter_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self._apply_table_filters()

    def _sort_records(self) -> None:
        before = list(self.records)
        self.task_table.clearSelection()
        key_name, reverse = self.sort_combo.currentData()
        if key_name == "duration":
            self.records.sort(
                key=lambda record: record.end_seconds - record.start_seconds,
                reverse=reverse,
            )
        else:
            self.records.sort(key=lambda record: record.sequence, reverse=reverse)
        self._editing_index = None
        self._refresh_table()
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._update_history_controls()

    @staticmethod
    def _apply_status_color(item: QTableWidgetItem, status: str) -> None:
        colors = {
            "ok": ("#047857", "#ecfdf5"),
            "skip": ("#a16207", "#fefce8"),
            "fail": ("#be123c", "#fff1f2"),
            "canceled": ("#64748b", "#f1f5f9"),
            "queued": ("#0369a1", "#f0f9ff"),
        }
        foreground, background = colors.get(status, ("#64748b", "#f8fafc"))
        item.setForeground(QColor(foreground))
        item.setBackground(QColor(background))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _load_selected_clip(self) -> None:
        selected = self.task_table.selectionModel().selectedRows()
        if len(selected) != 1:
            self._editing_index = None
            self.add_button.setText("添加片段")
            return
        index = selected[0].row()
        record = self.records[index]
        self._editing_index = index
        if hasattr(self, "annotation_overview_source"):
            self.annotation_overview_source.setText(
                f"#{index + 1} · {format_seconds(record.start_seconds)} → {format_seconds(record.end_seconds)}"
            )
        self.start_spin.setValue(record.start_seconds)
        self.end_spin.setValue(record.end_seconds)
        self.sequence_spin.setValue(max(1, record.sequence))
        self.note_edit.setText(record.note)
        self._rebuild_behavior_controls(record.behaviors)
        parsed = parse_filename(record.output)
        if parsed is not None:
            self._restore_parsed_metadata(parsed)
        if record.polarity:
            self._set_custom_combo_value(
                self.polarity_combo,
                record.polarity,
                lambda value: normalize_label_token(value, "polarity"),
            )
        if record.lighting:
            self._set_custom_combo_value(
                self.lighting_combo,
                record.lighting,
                lambda value: normalize_label_token(value, "lighting"),
            )
        if record.data_stratum:
            stratum_index = self.stratum_combo.findData(record.data_stratum)
            if stratum_index >= 0:
                self.stratum_combo.setCurrentIndex(stratum_index)
        self._populate_events(record.events)
        self._restore_person_attributes(record)
        self.add_button.setText("更新片段")
        self.player.setPosition(int(record.start_seconds * 1000))
        self._update_filename_preview()

    def _set_selected_review_status(self, review_status: str) -> None:
        if review_status not in REVIEW_STATUSES:
            raise ValueError("审核状态无效")
        indexes = self._selected_record_indexes()
        if not indexes:
            self._show_error("未选择片段", "请先选择至少一个片段。")
            return
        before = list(self.records)
        reviewer = "local-user"
        review_comment = ""
        rejection_reason = ""
        if review_status in {"approved", "needs_fix", "rejected"}:
            comment, accepted = QInputDialog.getText(self, "审核备注", "审核意见/驳回原因：")
            if not accepted:
                return
            review_comment = comment.strip()
            rejection_reason = review_comment if review_status in {"needs_fix", "rejected"} else ""
        reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for index in indexes:
            record = self.records[index]
            record.review_status = review_status
            record.reviewer = reviewer if review_status != "pending" else ""
            record.reviewed_at = reviewed_at if review_status != "pending" else ""
            record.review_comment = review_comment if review_status != "pending" else ""
            record.rejection_reason = rejection_reason
            record.review_history.append({
                "status": review_status,
                "reviewer": record.reviewer,
                "reviewed_at": record.reviewed_at,
                "comment": record.review_comment,
                "rejection_reason": record.rejection_reason,
            })
        self._refresh_table()
        self._mark_project_dirty()
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._set_status(f"已将 {len(indexes)} 个片段标记为{REVIEW_STATUS_LABELS.get(review_status, review_status)}")

    def _selected_record_indexes(self) -> list[int]:
        return sorted(
            {
                index.row()
                for index in self.task_table.selectionModel().selectedRows()
                if not self.task_table.isRowHidden(index.row())
            }
        )

    def _apply_batch_changes(
        self,
        indexes: list[int],
        behaviors: tuple[str, ...] | None,
        polarity: str | None,
        lighting: str | None,
        view: str | None,
        *,
        behavior_mode: str = "replace",
    ) -> None:
        if behavior_mode not in {"replace", "add", "remove"}:
            raise ValueError("行为标签批量操作无效")
        before = list(self.records)
        selected_indexes = set(indexes)
        proposed: dict[int, ClipRecord] = {}
        skipped_manual_view = False

        for index in indexes:
            record = self.records[index]
            if behaviors is None:
                next_behaviors = record.behaviors
            elif behavior_mode == "replace":
                next_behaviors = behaviors
            elif behavior_mode == "add":
                next_behaviors = tuple(dict.fromkeys((*record.behaviors, *behaviors)))
            else:
                next_behaviors = tuple(
                    tag for tag in record.behaviors if tag not in behaviors
                )
            if not next_behaviors:
                raise ValueError("移除后片段至少需要保留一个行为标签")
            next_polarity = polarity if polarity is not None else record.polarity
            next_lighting = lighting if lighting is not None else record.lighting
            parsed = parse_filename(record.output)
            output = record.output

            if parsed is not None:
                metadata = ProjectMetadata(
                    date=parsed.metadata.date,
                    camera=parsed.metadata.camera,
                    view=view if view is not None else parsed.metadata.view,
                )
                output = build_filename(
                    metadata,
                    next_behaviors,
                    next_polarity,
                    next_lighting,
                    parsed.sequence,
                )
            elif view is not None:
                skipped_manual_view = True

            proposed[index] = replace(
                record,
                output=output,
                behaviors=next_behaviors,
                polarity=next_polarity,
                lighting=next_lighting,
            )

        existing_outputs = {
            record.output.lower()
            for index, record in enumerate(self.records)
            if index not in selected_indexes
        }
        proposed_outputs: set[str] = set()
        for record in proposed.values():
            output = record.output.lower()
            if output in existing_outputs or output in proposed_outputs:
                raise ValueError(f"批量修改后输出文件名重复：{record.output}")
            proposed_outputs.add(output)

        for index, record in proposed.items():
            self.records[index] = record
        self._editing_index = None
        self._refresh_table()
        self._mark_project_dirty()
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._update_history_controls()
        if skipped_manual_view:
            self._set_status("批量修改完成；手动命名片段未更新视角")
        else:
            self._set_status(f"已批量修改 {len(indexes)} 个片段")

    def show_batch_edit_dialog(self) -> None:
        indexes = self._selected_record_indexes()
        if not indexes:
            self._show_error("未选择片段", "请先选择至少一个片段。")
            return

        def _copy_data_combo(source_combo: QComboBox) -> QComboBox:
            combo = QComboBox()
            for index in range(source_combo.count()):
                if source_combo.itemText(index) != CUSTOM_OPTION_TEXT:
                    combo.addItem(
                        source_combo.itemText(index), source_combo.itemData(index)
                    )
            self._set_combo_visible_item_count(combo)
            return combo

        dialog = QDialog(self)
        dialog.setWindowTitle("批量修改选中片段")
        layout = QVBoxLayout(dialog)
        apply_behaviors = QCheckBox("应用此字段：行为标签")
        behavior_mode_combo = QComboBox()
        behavior_mode_combo.addItem("替换为所选标签", "replace")
        behavior_mode_combo.addItem("添加所选标签", "add")
        behavior_mode_combo.addItem("移除所选标签", "remove")
        batch_behavior_checks = {
            behavior: QCheckBox(behavior)
            for behavior in self._available_behavior_tags()
        }
        apply_polarity = QCheckBox("应用此字段：正负例")
        polarity_combo = _copy_data_combo(self.polarity_combo)
        apply_lighting = QCheckBox("应用此字段：光照")
        lighting_combo = _copy_data_combo(self.lighting_combo)
        apply_view = QCheckBox("应用此字段：视角")
        view_combo = _copy_data_combo(self.view_combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(apply_behaviors)
        layout.addWidget(behavior_mode_combo)
        for checkbox in batch_behavior_checks.values():
            layout.addWidget(checkbox)
        layout.addWidget(apply_polarity)
        layout.addWidget(polarity_combo)
        layout.addWidget(apply_lighting)
        layout.addWidget(lighting_combo)
        layout.addWidget(apply_view)
        layout.addWidget(view_combo)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        behaviors = (
            tuple(
                behavior
                for behavior, checkbox in batch_behavior_checks.items()
                if checkbox.isChecked()
            )
            if apply_behaviors.isChecked()
            else None
        )
        if behaviors == ():
            self._show_error("批量修改失败", "应用行为标签时至少选择一个行为。")
            return

        polarity = (
            polarity_combo.currentText() if apply_polarity.isChecked() else None
        )
        lighting = (
            lighting_combo.currentText() if apply_lighting.isChecked() else None
        )
        view = view_combo.currentText() if apply_view.isChecked() else None
        try:
            self._apply_batch_changes(
                indexes,
                behaviors,
                polarity,
                lighting,
                view,
                behavior_mode=behavior_mode_combo.currentData(),
            )
        except ValueError as error:
            self._show_error("批量修改失败", str(error))

    def _update_annotation_stats(self) -> None:
        """Expose compact progress feedback without changing annotation data."""
        records = [record for record in self.records if record.source == self.source_name]
        total = len(records)
        approved = sum(record.review_status == "approved" for record in records)
        pending = sum(record.review_status == "pending" for record in records)
        needs_fix = sum(record.review_status == "needs_fix" for record in records)
        rejected = sum(record.review_status == "rejected" for record in records)
        self.annotation_stats_label.setText(
            f"片段 {total} · 待审核 {pending} · 通过 {approved} · 需修正 {needs_fix} · 剔除 {rejected}"
        )
        if hasattr(self, "annotation_overview_total"):
            self.annotation_overview_total.setText(f"{total}\n片段")
            self.annotation_overview_pending.setText(f"{pending}\n待审核")
            self.annotation_overview_approved.setText(f"{approved}\n已通过")
            active = self.task_table.currentRow()
            if 0 <= active < len(self.records):
                record = self.records[active]
                self.annotation_overview_source.setText(
                    f"#{active + 1} · {format_seconds(record.start_seconds)} → {format_seconds(record.end_seconds)}"
                )
            else:
                self.annotation_overview_source.setText("未选择记录")
            warnings = self._current_video_quality_warnings()
            if warnings:
                self.annotation_overview_warning.setText(
                    "⚠ " + "；".join(warnings[:2])
                )
                self.annotation_overview_warning.setToolTip("\n".join(warnings))
            else:
                self.annotation_overview_warning.setText("✓ 无异常")
                self.annotation_overview_warning.setToolTip("")

    def _current_video_quality_warnings(self) -> list[str]:
        """轻量实时质量检测，仅读取数据，不修改任何标注结构。"""
        warnings: list[str] = []
        duration = 0.0
        video = self._active_project_video()
        if video is not None and video.metadata:
            raw_duration = video.metadata.get("duration")
            if isinstance(raw_duration, (int, float)):
                duration = float(raw_duration)
        for index, record in enumerate(self.records):
            label = f"片段 {index + 1}"
            if not record.behaviors:
                warnings.append(f"{label} 未设置行为标签")
            if duration > 0 and record.end_seconds > duration:
                warnings.append(f"{label} 结束时间超过视频时长")
            for previous_index, previous in enumerate(self.records[:index]):
                if (
                    record.start_seconds < previous.end_seconds
                    and previous.start_seconds < record.end_seconds
                ):
                    warnings.append(
                        f"{label} 与片段 {previous_index + 1} 时间重叠"
                    )
                    break
        return warnings

    def _show_task_context_menu(self, position) -> None:
        item = self.task_table.itemAt(position)
        if item is not None and item.row() not in self._selected_record_indexes():
            self.task_table.selectRow(item.row())
        indexes = self._selected_record_indexes()
        if not indexes:
            return
        menu = QMenu(self.task_table)
        edit_action = menu.addAction("编辑选中片段")
        clone_action = menu.addAction("克隆首个选中片段")
        menu.addSeparator()
        delete_action = menu.addAction(f"删除选中 ({len(indexes)})")
        chosen = menu.exec(self.task_table.viewport().mapToGlobal(position))
        if chosen is edit_action:
            self.task_table.selectRow(indexes[0])
            self._load_selected_clip()
            self.start_spin.setFocus()
        elif chosen is clone_action:
            self._clone_selected_record(indexes[0])
        elif chosen is delete_action:
            self._delete_selected_records()

    def _clone_selected_record(self, index: int) -> None:
        if not 0 <= index < len(self.records):
            return
        original = self.records[index]
        sequence = next_sequence([record.sequence for record in self.records])
        parsed = parse_filename(original.output)
        output = original.output
        if parsed is not None:
            output = build_filename(
                parsed.metadata, original.behaviors, original.polarity,
                original.lighting, sequence
            )
        else:
            suffix = Path(original.output).suffix or ".mp4"
            output = f"{Path(original.output).stem}-copy-{sequence:03d}{suffix}"
        clone = replace(
            original, sequence=sequence, output=output, status="queued", error=""
        )
        before = list(self.records)
        self.records.append(clone)
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._refresh_table()
        self._mark_project_dirty()
        self.task_table.selectRow(len(self.records) - 1)
        self._set_status(f"已克隆片段 {index + 1}，编号 {sequence:03d}")

    def _delete_selected_records(self) -> None:
        indexes = self._selected_record_indexes()
        if not indexes:
            self._show_error("未选择片段", "请先选择至少一个片段。")
            return
        answer = QMessageBox.question(
            self,
            "确认批量删除",
            f"确定删除选中的 {len(indexes)} 个片段吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        before = list(self.records)
        self.task_table.clearSelection()
        for index in reversed(indexes):
            del self.records[index]
        self._editing_index = None
        self.add_button.setText("添加片段")
        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._refresh_table()
        self._mark_project_dirty()
        self._update_history_controls()
        self._set_status(f"已删除 {len(indexes)} 个片段")

    def _table_cell_changed(self, row: int, column: int) -> None:
        if column != 7 or row >= len(self.records):
            return
        item = self.task_table.item(row, column)
        if item is None:
            return
        output = item.text().strip()
        try:
            validate_output_filename(output)
        except ValueError as error:
            self._show_error("文件名无效", f"输出文件名无效：{output}；{error}")
            self._refresh_table()
            return
        try:
            editing_index = self._editing_index
            self._editing_index = row
            self._assert_output_is_unique(output)
            self._editing_index = editing_index
        except ValueError as error:
            self._editing_index = editing_index
            self._show_error("文件名重复", str(error))
            self._refresh_table()
            return
        self.records[row].output = output
        self._mark_project_dirty()
        self._clear_active_history()
        self._set_status(f"已更新片段 {row + 1} 的输出文件名")

    def start_export(self) -> None:
        if self.source_path is None or not self.source_path.is_file():
            self._show_error("没有视频源", "导出前请先导入源视频。")
            return
        prepared = self._prepare_export_records(self.records, [self.source_path] * len(self.records))
        if prepared is not None:
            self._start_export(*prepared)

    def start_project_export(self) -> None:
        records: list[ClipRecord] = []
        input_paths: list[Path] = []
        missing_sources = []
        for video in self.project.videos:
            if not video.segments:
                continue
            if not video.path.is_file():
                missing_sources.append(str(video.path))
                continue
            records.extend(video.segments)
            input_paths.extend([video.path] * len(video.segments))

        if missing_sources:
            self._show_error(
                "视频源不存在",
                "以下视频源不存在：" + "；".join(missing_sources),
            )
            return
        prepared = self._prepare_export_records(records, input_paths)
        if prepared is not None:
            filtered_records, filtered_paths = prepared
            self._start_export(filtered_records, filtered_paths, project_queue=True)

    def _prepare_export_records(self, records, input_paths):
        policy, accepted = QInputDialog.getItem(
            self, "导出审核范围", "选择导出范围",
            ("全部片段", "仅导出审核通过", "取消导出"), 0, False
        )
        if not accepted or policy == "取消导出":
            self._set_status("已取消导出")
            return None
        if policy == "仅导出审核通过":
            selected = [(record, path) for record, path in zip(records, input_paths) if record.review_status == "approved"]
            if not selected:
                self._show_error("没有已审核片段", "当前没有审核通过的片段可导出。")
                return None
            records, input_paths = zip(*selected)
            records, input_paths = list(records), list(input_paths)
        warnings = export_quality_issues(self.project, require_approved=(policy == "仅导出审核通过"))
        blocking = [issue for issue in warnings if issue.severity == "error"]
        if blocking:
            text = "\n".join(issue.message for issue in blocking[:10])
            answer = QMessageBox.warning(self, "导出质量检查", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self._set_status("质量检查未通过，已取消导出")
                return None
        return records, input_paths

    @staticmethod
    def _format_export_size(byte_count: int | None) -> str:
        if byte_count is None:
            return "无法估算"
        size = float(byte_count)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return f"{int(byte_count)} B"

    @staticmethod
    def _estimate_export_bytes(
        records: Sequence[ClipRecord], input_paths: Sequence[Path]
    ) -> int | None:
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

    def _confirm_export_preview(
        self, records: Sequence[ClipRecord], input_paths: Sequence[Path]
    ) -> bool:
        total_duration = sum(
            record.end_seconds - record.start_seconds for record in records
        )
        estimate = self._estimate_export_bytes(records, input_paths)
        estimate_text = self._format_export_size(estimate)
        answer = QMessageBox.question(
            self,
            "导出预览",
            (
                f"将导出 {len(records)} 个片段，合计时长 "
                f"{format_seconds(total_duration)}。\n"
                f"预计磁盘占用：{estimate_text}\n"
                "估算按源视频平均码率计算，实际大小会随编码模式变化。\n\n"
                "是否开始导出？"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _start_export(
        self,
        records: Sequence[ClipRecord],
        input_paths: Sequence[Path],
        *,
        project_queue: bool = False,
    ) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            return
        if not records:
            self._show_error("没有片段任务", "导出前请至少添加一个片段。")
            return
        if self.output_dir is None:
            self._show_error("没有输出文件夹", "导出前请先选择输出文件夹。")
            return

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if not self.output_dir.is_dir():
                raise OSError("输出路径不是文件夹")
            outputs = [record.output.lower() for record in records]
            if len(outputs) != len(set(outputs)):
                raise ValueError("任务列表中包含重复的输出文件名。")
            for record in records:
                validate_output_filename(record.output)
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error(
                "无法开始导出", f"开始导出失败：{self._file_error_tip(error)}"
            )
            return

        if not self._confirm_export_preview(records, input_paths):
            self._set_status("已取消导出")
            return

        try:
            ffmpeg = resolve_ffmpeg(self.ffmpeg_edit.text())
            ffprobe = resolve_ffprobe(ffmpeg)
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error(
                "无法开始导出", f"开始导出失败：{self._file_error_tip(error)}"
            )
            return

        self._export_worker = ExportWorker(
            records=records,
            input_path=input_paths[0],
            input_paths=input_paths,
            output_dir=self.output_dir,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            mode=self.mode_combo.currentText(),
            overwrite=self.overwrite_check.isChecked(),
            workers=self.workers_spin.value(),
        )
        self._export_records = list(records)
        self._export_record_states = [
            (record.status, record.error) for record in self._export_records
        ]
        self._is_project_export = project_queue
        if project_queue:
            self._project_export_queue = list(zip(input_paths, records))
            self.project_queue_dialog.set_items(self._project_export_queue)
            self.project_queue_dialog.cancel_button.setEnabled(True)
            self._persist_project_export_queue()
            self.show_project_export_queue()
        self._export_worker.clip_finished.connect(self._export_clip_finished)
        self._export_worker.progress.connect(self._export_progress)
        self._export_worker.export_completed.connect(self._export_completed)
        self.progress_bar.setRange(0, len(records))
        self.progress_bar.setValue(0)
        self.export_button.setEnabled(False)
        self.project_export_button.setEnabled(False)
        self.cancel_export_button.setEnabled(True)
        self._set_status("正在导出片段……")
        self._export_worker.start()

    def cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()
            self.cancel_export_button.setEnabled(False)
            self.project_queue_dialog.cancel_button.setEnabled(False)
            self._set_status("已请求取消，正在完成当前 FFmpeg 任务……")

    def _export_clip_finished(self, _index: int, _result: object) -> None:
        self._refresh_table()
        if not 0 <= _index < len(self._export_records):
            return
        record = self._export_records[_index]
        detail = f"：{record.error}" if record.error else ""
        self._append_log(
            f"导出 {record.output}：{STATUS_LABELS.get(record.status, record.status)}{detail}"
        )
        if self._is_project_export:
            self.project_queue_dialog.update_item(_index, record)
            self._persist_project_export_queue()
        record_state = (record.status, record.error)
        if (
            self._project_path is not None
            and record_state != self._export_record_states[_index]
        ):
            self._mark_project_dirty()
        self._export_record_states[_index] = record_state

    def _export_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)
        if self._is_project_export:
            self.project_queue_dialog.set_progress(completed, total)

    def _export_completed(self, summary: ExportSummary) -> None:
        self._refresh_table()
        self.export_button.setEnabled(True)
        self.project_export_button.setEnabled(True)
        self.cancel_export_button.setEnabled(False)
        self.project_queue_dialog.cancel_button.setEnabled(False)
        if self._is_project_export:
            self._persist_project_export_queue()
        self._export_worker = None
        self._export_records = []
        self._export_record_states = []
        self._is_project_export = False
        self._set_status(
            "导出完成："
            f"成功={summary.success} 跳过={summary.skipped} "
            f"失败={summary.failed} 已取消={summary.canceled}"
        )

    def _show_error(self, title: str, text: str) -> None:
        self._set_status(text)
        QMessageBox.warning(self, title, text)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self._append_log(text)

    def _append_log(self, text: str) -> None:
        if text and hasattr(self, "log_panel"):
            self.log_panel.appendPlainText(text)

    def clear_log(self) -> None:
        self.log_panel.clear()

    def copy_log(self) -> None:
        self.log_panel.selectAll()
        self.log_panel.copy()

    @staticmethod
    def _file_error_tip(error: Exception) -> str:
        if isinstance(error, PermissionError):
            return "访问被拒绝。请检查文件夹写入权限，并关闭占用文件后重试。"
        return str(error)

    def show_project_export_queue(self) -> None:
        self.project_queue_dialog.show()
        self.project_queue_dialog.raise_()
        self.project_queue_dialog.activateWindow()

    def _persist_project_export_queue(self) -> None:
        if self._project_path is None:
            return
        try:
            save_export_queue_state(
                self._project_path,
                self.output_dir,
                self._project_export_queue,
            )
        except (OSError, ValueError) as error:
            self._set_status(
                f"保存导出队列失败：{self._file_error_tip(error)}"
            )

    def _restore_project_export_queue(self) -> None:
        if self._project_path is None:
            return
        try:
            output_dir, items = load_export_queue_state(self._project_path)
        except (OSError, ValueError) as error:
            self._set_status(
                f"恢复导出队列失败：{self._file_error_tip(error)}"
            )
            return
        self._project_export_queue = items
        if self.output_dir is None and output_dir is not None:
            self.output_dir = output_dir
            self._set_output_folder_display()
        self.project_queue_dialog.set_items(items)

    def _cleanup_orphaned_export_parts(self, *, prompt: bool) -> None:
        if self.output_dir is None:
            return
        try:
            orphaned = find_orphaned_temporary_outputs(self.output_dir)
        except OSError as error:
            self._set_status(
                f"检查导出临时文件失败：{self._file_error_tip(error)}"
            )
            return
        if not orphaned:
            return
        if prompt and QMessageBox.question(
            self,
            "发现导出临时文件",
            f"发现 {len(orphaned)} 个上次导出残留的临时文件，是否清理？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            cleanup_orphaned_temporary_outputs(self.output_dir)
        except OSError as error:
            self._set_status(
                f"清理导出临时文件失败：{self._file_error_tip(error)}"
            )

    def closeEvent(self, event) -> None:
        if self._confirm_discard_dirty_project():
            event.accept()
        else:
            event.ignore()
