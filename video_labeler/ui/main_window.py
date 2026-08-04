from collections.abc import Callable
from dataclasses import replace
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
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..csv_io import read_clip_csv, write_clip_csv
from ..export_worker import ExportSummary, ExportWorker
from ..ffmpeg_service import format_seconds, resolve_ffmpeg
from ..history import SegmentHistory
from ..models import (
    BEHAVIOR_LABELS,
    LIGHTING_VALUES,
    POLARITIES,
    VIEW_TYPES,
    ClipRecord,
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
    load_project,
    new_project,
    save_project as write_label_project,
)


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
)
BEHAVIOR_COLUMN_PADDING = 16
CUSTOM_OPTION_TEXT = "自定义..."
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
            start_height = 0
            target_height = max(
                self._content.sizeHint().height(),
                self._content.minimumSizeHint().height(),
            )
            self._content.setMaximumHeight(start_height)
        else:
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

        self.setWindowTitle("视频片段标注工具")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)

        self._build_ui()
        self._build_project_menu()
        self._connect_signals()
        self._update_filename_preview()
        self._update_history_controls()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_project_header())

        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_splitter.setChildrenCollapsible(False)
        self.editor_splitter.addWidget(self._build_video_panel())

        self.annotation_panel = self._build_clip_editor()
        self.annotation_scroll = QScrollArea()
        self.annotation_scroll.setWidget(self.annotation_panel)
        self.annotation_scroll.setWidgetResizable(True)
        self.annotation_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.annotation_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.annotation_scroll.installEventFilter(self)
        self.editor_splitter.addWidget(self.annotation_scroll)
        self.editor_splitter.setSizes([616, 788])

        self.workspace_splitter.addWidget(self.editor_splitter)
        self.workspace_splitter.addWidget(self._build_task_table())
        self.workspace_splitter.setSizes([520, 340])
        self.workspace_splitter.setStretchFactor(0, 3)
        self.workspace_splitter.setStretchFactor(1, 2)
        root_layout.addWidget(self.workspace_splitter, stretch=1)
        root_layout.addLayout(self._build_export_status())

        self.setCentralWidget(root)

    def _build_project_header(self) -> QGroupBox:
        group = QGroupBox("项目设置")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        layout.setColumnStretch(4, 1)

        self.open_video_button = QPushButton("导入视频")
        self.import_csv_button = QPushButton("导入 CSV")
        self.save_csv_button = QPushButton("保存标注 CSV")
        self.output_folder_button = QPushButton("选择输出文件夹")
        self.export_button = QPushButton("批量导出")
        self.export_button.setObjectName("primaryButton")
        self.shortcut_help_button = QPushButton("快捷键说明")
        self.output_folder_label = QLabel("未选择输出文件夹")
        self.output_folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.output_folder_label.setObjectName("mutedLabel")

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

        layout.addWidget(self.open_video_button, 0, 0)
        layout.addWidget(self.import_csv_button, 0, 1)
        layout.addWidget(self.save_csv_button, 0, 2)
        layout.addWidget(self.output_folder_button, 0, 3)
        layout.addWidget(self.output_folder_label, 0, 4)
        layout.addWidget(self.export_button, 0, 5)
        layout.addWidget(self.shortcut_help_button, 0, 6)

        layout.addWidget(QLabel("日期"), 1, 0)
        layout.addWidget(self.date_edit, 1, 1)
        layout.addWidget(QLabel("摄像头"), 1, 2)
        layout.addWidget(self.camera_edit, 1, 3)
        layout.addWidget(QLabel("视角"), 1, 4)
        layout.addWidget(self.view_combo, 1, 5)

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
        layout.addWidget(self.advanced_export_group, 2, 0, 1, 6)
        return group

    def _build_project_menu(self) -> None:
        self.project_menu = self.menuBar().addMenu("工程")
        self.new_project_action = QAction("新建工程", self)
        self.open_project_action = QAction("打开工程", self)
        self.save_project_action = QAction("保存工程", self)
        self.restore_project_action = QAction("从备份文件恢复工程", self)
        self.project_menu.addAction(self.new_project_action)
        self.project_menu.addAction(self.open_project_action)
        self.project_menu.addAction(self.save_project_action)
        self.project_menu.addSeparator()
        self.project_menu.addAction(self.restore_project_action)

    def _build_video_panel(self) -> QGroupBox:
        group = QGroupBox("视频预览")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(240)
        self.video_widget.setObjectName("videoSurface")
        layout.addWidget(self.video_widget, stretch=1)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        position_layout = QHBoxLayout()
        self.position_label = QLabel("00:00:00.000")
        self.duration_label = QLabel("00:00:00.000")
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setTracking(False)
        position_layout.addWidget(self.position_label)
        position_layout.addWidget(self.timeline_slider, stretch=1)
        position_layout.addWidget(self.duration_label)
        layout.addLayout(position_layout)

        controls = QHBoxLayout()
        self.play_button = QPushButton("播放")
        self.seek_back_button = QPushButton("-5s")
        self.seek_forward_button = QPushButton("+5s")
        self.set_start_button = QPushButton("设置起始点")
        self.set_end_button = QPushButton("设置结束点")
        self.speed_combo = QComboBox()
        self.speed_combo.addItem("0.5x", 0.5)
        self.speed_combo.addItem("1.0x", 1.0)
        self.speed_combo.addItem("1.5x", 1.5)
        self.speed_combo.addItem("2.0x", 2.0)
        self.speed_combo.setCurrentIndex(1)

        controls.addWidget(self.play_button)
        controls.addWidget(self.seek_back_button)
        controls.addWidget(self.seek_forward_button)
        controls.addStretch(1)
        controls.addWidget(self.set_start_button)
        controls.addWidget(self.set_end_button)
        controls.addWidget(QLabel("播放速度"))
        controls.addWidget(self.speed_combo)
        layout.addLayout(controls)
        return group

    def _build_clip_editor(self) -> QGroupBox:
        group = QGroupBox("片段标注")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        source_layout = QHBoxLayout()
        self.source_label = QLabel("未选择视频")
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("mutedLabel")
        self.project_video_combo = QComboBox()
        self.project_video_combo.setMinimumContentsLength(16)
        self.project_video_combo.setEnabled(False)
        source_layout.addWidget(self.source_label, stretch=1)
        source_layout.addWidget(self.project_video_combo)
        layout.addLayout(source_layout)

        time_form = QFormLayout()
        self.start_spin = self._new_time_spin()
        self.end_spin = self._new_time_spin()
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 999999)
        self.sequence_spin.setValue(1)
        time_form.addRow("开始时间", self.start_spin)
        time_form.addRow("结束时间", self.end_spin)
        time_form.addRow("编号", self.sequence_spin)
        layout.addLayout(time_form)

        actions = QHBoxLayout()
        self.add_button = QPushButton("添加片段")
        self.remove_button = QPushButton("删除所选")
        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("重做")
        self.clear_button = QPushButton("清空编辑区")
        self.add_button.setObjectName("addClipButton")
        self.remove_button.setObjectName("dangerButton")
        self.undo_button.setObjectName("undoButton")
        self.redo_button.setObjectName("redoButton")
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addWidget(self.undo_button)
        actions.addWidget(self.redo_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)

        self.behavior_checks: dict[str, QCheckBox] = {}
        self.behaviors_group = CollapsibleGroupBox("行为标签")
        self.behaviors_group.setObjectName("collapsibleBehaviorGroup")
        self.behavior_checks_container = QWidget()
        self.behavior_checks_container.installEventFilter(self)
        self.behavior_checks_layout = QGridLayout(self.behavior_checks_container)
        self.behavior_checks_layout.setContentsMargins(0, 0, 0, 0)
        self.behavior_checks_layout.setHorizontalSpacing(10)
        self.behavior_checks_layout.setVerticalSpacing(4)
        self.behavior_columns = 2
        self._behavior_reflow_pending = False

        behaviors_layout = QVBoxLayout(self.behaviors_group)
        behaviors_layout.setContentsMargins(6, 6, 6, 6)
        behaviors_layout.addWidget(self.behavior_checks_container)
        self.behaviors_group.set_content(self.behavior_checks_container)

        for behavior in BEHAVIOR_LABELS:
            checkbox = QCheckBox(behavior)
            self.behavior_checks[behavior] = checkbox
        self._reflow_behavior_checks()
        layout.addWidget(self.behaviors_group)

        labels_form = QFormLayout()
        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(POLARITIES)
        self._configure_custom_combo(
            self.polarity_combo,
            "正负性",
            lambda value: normalize_label_token(value, "polarity"),
            "仅支持小写英文、数字和下划线。",
        )
        self.lighting_combo = QComboBox()
        self.lighting_combo.addItems(LIGHTING_VALUES)
        self._configure_custom_combo(
            self.lighting_combo,
            "光照",
            lambda value: normalize_label_token(value, "lighting"),
            "仅支持小写英文、数字和下划线。",
        )
        labels_form.addRow("正负性", self.polarity_combo)
        labels_form.addRow("光照", self.lighting_combo)
        layout.addLayout(labels_form)

        layout.addWidget(QLabel("生成的文件名"))
        self.filename_preview = QLineEdit()
        self.filename_preview.setReadOnly(True)
        self.filename_preview.setToolTip("生成的输出文件名")
        layout.addWidget(self.filename_preview)
        return group

    def _reflow_behavior_checks(self) -> None:
        self._behavior_reflow_pending = False
        available_width = self.behavior_checks_container.width()
        if available_width <= 0:
            available_width = self.behavior_checks_container.sizeHint().width()
        columns, column_widths = self._behavior_layout_for_width(available_width)
        self.behavior_columns = columns
        for checkbox in self.behavior_checks.values():
            checkbox.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
            )
        while self.behavior_checks_layout.count():
            self.behavior_checks_layout.takeAt(0)
        for column in range(3):
            self.behavior_checks_layout.setColumnMinimumWidth(column, 0)
            self.behavior_checks_layout.setColumnStretch(column, 0)
        rows = (len(self.behavior_checks) + columns - 1) // columns
        for index, checkbox in enumerate(self.behavior_checks.values()):
            row, column = divmod(index, columns)
            self.behavior_checks_layout.addWidget(checkbox, row, column)
        for column in range(columns):
            self.behavior_checks_layout.setColumnMinimumWidth(
                column, column_widths[column]
            )
            self.behavior_checks_layout.setColumnStretch(column, 1)
        self.behavior_checks_container.updateGeometry()
        self.behaviors_group.updateGeometry()
        if self.behaviors_group.isChecked():
            QTimer.singleShot(0, self._restore_behavior_content_height)

    def _behavior_layout_for_width(self, available_width: int) -> tuple[int, list[int]]:
        checks = list(self.behavior_checks.values())
        spacing = self.behavior_checks_layout.horizontalSpacing()
        two_column_widths = self._behavior_column_widths(checks, 2)
        three_column_widths = self._behavior_column_widths(checks, 3)
        three_column_width = sum(three_column_widths) + spacing * 2
        if available_width >= three_column_width:
            return 3, three_column_widths
        return 2, two_column_widths

    @staticmethod
    def _behavior_column_widths(
        checks: list[QCheckBox], columns: int
    ) -> list[int]:
        column_widths = [0] * columns
        for index, checkbox in enumerate(checks):
            column = index % columns
            column_widths[column] = max(
                column_widths[column],
                checkbox.sizeHint().width() + BEHAVIOR_COLUMN_PADDING,
            )
        return column_widths

    def _schedule_behavior_reflow(self) -> None:
        if self._behavior_reflow_pending:
            return
        self._behavior_reflow_pending = True
        QTimer.singleShot(0, self._reflow_behavior_checks)

    def _release_behavior_width_constraints(self) -> None:
        for column in range(3):
            self.behavior_checks_layout.setColumnMinimumWidth(column, 0)
        for checkbox in self.behavior_checks.values():
            checkbox.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
        self.behavior_checks_container.updateGeometry()
        self.behaviors_group.updateGeometry()

    def _restore_behavior_content_height(self) -> None:
        if (
            self.behaviors_group.isChecked()
            and self.behaviors_group._animation.state()
            != QAbstractAnimation.State.Running
        ):
            self.behavior_checks_container.setMaximumHeight(
                CollapsibleGroupBox._UNRESTRICTED_HEIGHT
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "behavior_checks_layout"):
            self._schedule_behavior_reflow()

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.Resize:
            return super().eventFilter(watched, event)
        if watched is getattr(self, "annotation_scroll", None):
            self._release_behavior_width_constraints()
            self._schedule_behavior_reflow()
        elif watched is getattr(self, "behavior_checks_container", None):
            self._schedule_behavior_reflow()
        return super().eventFilter(watched, event)

    def _build_task_table(self) -> QGroupBox:
        group = QGroupBox("片段任务")
        layout = QVBoxLayout(group)

        self.task_table = QTableWidget(0, len(TABLE_COLUMNS))
        self.task_table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.task_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.task_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.task_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(26)
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for column, width in enumerate((72, 98, 98, 82, 210, 72, 150, 430, 80, 260)):
            self.task_table.setColumnWidth(column, width)

        toolbar = QHBoxLayout()
        self.batch_edit_button = QPushButton("批量修改选中片段")
        self.batch_delete_button = QPushButton("批量删除选中")
        self.batch_delete_button.setObjectName("dangerButton")
        self.behavior_filter_combo = QComboBox()
        self.behavior_filter_combo.addItem("全部行为", None)
        for behavior in BEHAVIOR_LABELS:
            self.behavior_filter_combo.addItem(behavior, behavior)
        self.behavior_filter_combo.setCurrentData = lambda value: (
            self.behavior_filter_combo.setCurrentIndex(
                self.behavior_filter_combo.findData(value)
            )
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
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("编号升序", ("sequence", False))
        self.sort_combo.addItem("编号降序", ("sequence", True))
        self.sort_combo.addItem("时长升序", ("duration", False))
        self.sort_combo.addItem("时长降序", ("duration", True))
        self.clear_filters_button = QPushButton("清空筛选")

        toolbar.addWidget(self.batch_edit_button)
        toolbar.addWidget(self.batch_delete_button)
        toolbar.addWidget(self.behavior_filter_combo)
        toolbar.addWidget(self.polarity_filter_combo)
        toolbar.addWidget(self.status_filter_combo)
        toolbar.addWidget(self.sort_combo)
        toolbar.addWidget(self.clear_filters_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.task_table)
        return group

    def _build_export_status(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.cancel_export_button = QPushButton("取消导出")
        self.cancel_export_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel("就绪")
        self.shortcut_hint_label = QLabel(
            "快捷键：空格 播放/暂停，A/D 前后帧，S/E 设置起止点，Del 删除，"
            "Ctrl+Z/Y 撤销/重做，Ctrl+S 保存工程"
        )

        layout.addWidget(self.cancel_export_button)
        layout.addWidget(self.progress_bar, stretch=1)
        layout.addWidget(self.status_label)
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
        self.save_csv_button.clicked.connect(self.save_csv)
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action.triggered.connect(self.open_project)
        self.save_project_action.triggered.connect(self.save_project)
        self.restore_project_action.triggered.connect(
            self.restore_project_from_backup
        )
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
        self.speed_combo.currentIndexChanged.connect(self._set_playback_rate)
        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.playbackStateChanged.connect(self._update_play_button)
        self.player.errorOccurred.connect(self._media_error)
        self.advanced_export_group.toggled.connect(
            self.advanced_export_content.setVisible
        )
        self.editor_splitter.splitterMoved.connect(
            lambda _position, _index: self._schedule_behavior_reflow()
        )

        self.date_edit.textChanged.connect(self._update_filename_preview)
        self.camera_edit.textChanged.connect(self._update_filename_preview)
        self.view_combo.currentTextChanged.connect(self._update_filename_preview)
        self.polarity_combo.currentTextChanged.connect(self._update_filename_preview)
        self.lighting_combo.currentTextChanged.connect(self._update_filename_preview)
        self.sequence_spin.valueChanged.connect(self._update_filename_preview)
        for checkbox in self.behavior_checks.values():
            checkbox.toggled.connect(self._update_filename_preview)

        self.add_button.clicked.connect(self.add_or_update_clip)
        self.remove_button.clicked.connect(self.remove_selected_clip)
        self.undo_button.clicked.connect(self.undo_segments)
        self.redo_button.clicked.connect(self.redo_segments)
        self.clear_button.clicked.connect(self.clear_editor)
        self.batch_edit_button.clicked.connect(self.show_batch_edit_dialog)
        self.batch_delete_button.clicked.connect(self._delete_selected_records)
        self.behavior_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.polarity_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.status_filter_combo.currentIndexChanged.connect(
            self._apply_table_filters
        )
        self.sort_combo.currentIndexChanged.connect(self._sort_records)
        self.clear_filters_button.clicked.connect(self.clear_table_filters)
        self.task_table.itemSelectionChanged.connect(self._load_selected_clip)
        self.task_table.cellChanged.connect(self._table_cell_changed)

        self.export_button.clicked.connect(self.start_export)
        self.cancel_export_button.clicked.connect(self.cancel_export)
        self.shortcut_help_button.clicked.connect(self.show_shortcut_help)
        self._register_shortcuts()

    def _register_shortcuts(self) -> None:
        bindings = {
            "play_pause": ("Space", self.toggle_playback),
            "previous_frame": ("A", lambda: self._step_frame(-1)),
            "next_frame": ("D", lambda: self._step_frame(1)),
            "set_start": ("S", self._set_start_from_player),
            "set_end": ("E", self._set_end_from_player),
            "delete_selected": ("Del", self.remove_selected_clip),
            "undo": ("Ctrl+Z", self.undo_segments),
            "redo": ("Ctrl+Y", self.redo_segments),
            "save_project": ("Ctrl+S", self.save_project),
        }
        self.shortcuts = {}
        for name, (sequence, callback) in bindings.items():
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts[name] = shortcut

    def _create_shortcut_help_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("快捷键说明")
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(SHORTCUT_HELP_ROWS), 2, dialog)
        table.setHorizontalHeaderLabels(("快捷键", "操作"))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for row, (shortcut, action) in enumerate(SHORTCUT_HELP_ROWS):
            table.setItem(row, 0, QTableWidgetItem(shortcut))
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
        self._bind_active_video(entry)
        self._mark_project_dirty()
        self._set_status(f"已选择视频：{entry.path.name}")

    def _bind_active_video(self, entry: ProjectVideo) -> None:
        self.project.active_video_id = entry.id
        self.records = entry.segments
        self.source_path = entry.path
        self.source_name = entry.path.name
        self.source_label.setText(entry.path.name)
        self._editing_index = None
        self.add_button.setText("添加片段")
        self._sync_project_video_combo()
        self._refresh_table()
        self._update_history_controls()

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
            self.player.setSource(QUrl.fromLocalFile(str(entry.path)))
            self.player.pause()
        else:
            self.player.setSource(QUrl())
            self._set_status(f"视频源不存在：{entry.path}")

    def _project_snapshot(self) -> LabelProject:
        settings = self.project.global_settings
        settings["date"] = self.date_edit.text().strip()
        settings["camera"] = self.camera_edit.text().strip()
        settings["view"] = self.view_combo.currentText()
        settings["output_dir"] = str(self.output_dir) if self.output_dir else ""
        return self.project

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
        except (OSError, ValueError) as error:
            self._set_status(f"自动备份失败：{error}")

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
        self.project_video_combo.clear()
        self.project_video_combo.setEnabled(False)
        self.player.setSource(QUrl())
        self._refresh_table()
        self.clear_editor()

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
            self._project_path = write_label_project(
                project_path, self._project_snapshot()
            )
        except (OSError, ValueError) as error:
            self._show_error("无法保存工程", f"保存工程失败：{error}")
            return
        self._project_dirty = False
        self._set_status(f"已保存工程：{self._project_path}")

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

    def _load_project_path(self, path: Path) -> bool:
        try:
            project = load_project(path)
        except (OSError, ValueError) as error:
            self._show_error("无法打开工程", f"打开工程失败：{error}")
            return False

        self._backup_timer.stop()
        self.project = project
        self._project_path = Path(path)
        self._project_dirty = False
        self._active_video_histories = {}
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

        entry = self._active_project_video()
        if entry is None:
            self.records = []
            self.source_path = None
            self.source_name = ""
            self.source_label.setText("未选择视频")
            self._sync_project_video_combo()
            self._refresh_table()
            self.player.setSource(QUrl())
        else:
            self.switch_active_video(entry.id)
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
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.pause()

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
            self._bind_active_video(selected_video)
        elif active_video is not None:
            active_video.segments.clear()
            self._active_video_histories.pop(active_video.id, None)
            self._bind_active_video(active_video)
        else:
            self.records = []

        if self.records:
            self.source_name = self.records[0].source
            self.source_label.setText(self.source_name)
            first_parsed: ParsedFilename | None = None
            for record in imported_records:
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
            self._show_error("无法保存 CSV", f"保存 CSV 失败：{error}")
            return
        self._set_status(f"已保存 CSV：{filename}")

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
        self.output_folder_label.setText(str(self.output_dir))
        self._mark_project_dirty()
        self._set_status(f"输出文件夹：{self.output_dir}")

    def set_clip_range(self, start_seconds: float, end_seconds: float) -> None:
        self.start_spin.setValue(start_seconds)
        self.end_spin.setValue(end_seconds)

    def selected_behaviors(self) -> tuple[str, ...]:
        return tuple(
            behavior
            for behavior, checkbox in self.behavior_checks.items()
            if checkbox.isChecked()
        )

    def add_or_update_clip(self) -> None:
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
            sequence = self.sequence_spin.value()
            output = build_filename(
                metadata, behaviors, polarity, lighting, sequence
            )
            self._assert_output_is_unique(output)
        except ValueError as error:
            self._show_error("无法添加片段", f"添加片段失败：{error}")
            return

        record = ClipRecord(
            source=source,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            output=output,
            behaviors=behaviors,
            polarity=polarity,
            lighting=lighting,
            sequence=sequence,
        )
        before = list(self.records)
        if self._editing_index is None:
            self.records.append(record)
            self._set_status(f"已添加片段 {sequence:03d}")
        else:
            self.records[self._editing_index] = record
            self._set_status(f"已更新片段 {sequence:03d}")

        history = self._active_history(create=True)
        if history is not None:
            history.push(before, self.records)
        self._refresh_table()
        self._mark_project_dirty()
        self._prepare_next_clip(record.end_seconds)
        self._update_history_controls()

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
        for checkbox in self.behavior_checks.values():
            checkbox.setChecked(False)
        self.polarity_combo.setCurrentIndex(0)
        self.lighting_combo.setCurrentIndex(0)
        self.sequence_spin.setValue(
            next_sequence([record.sequence for record in self.records])
        )
        self.add_button.setText("添加片段")
        self._update_filename_preview()

    def _prepare_next_clip(self, saved_end_seconds: float) -> None:
        self._editing_index = None
        self.add_button.setText("添加片段")
        self.set_clip_range(saved_end_seconds, saved_end_seconds)
        for checkbox in self.behavior_checks.values():
            checkbox.setChecked(False)
        self.sequence_spin.setValue(
            next_sequence([record.sequence for record in self.records])
        )
        self._update_filename_preview()

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _set_start_from_player(self) -> None:
        self.start_spin.setValue(self.player.position() / 1000)

    def _set_end_from_player(self) -> None:
        self.end_spin.setValue(self.player.position() / 1000)

    def _step_frame(self, direction: int) -> None:
        self._seek_relative(33 * direction)

    def _seek_relative(self, milliseconds: int) -> None:
        duration = self.player.duration()
        position = max(0, min(duration, self.player.position() + milliseconds))
        self.player.setPosition(position)

    def _seek_to_milliseconds(self, milliseconds: int) -> None:
        if milliseconds != self.player.position():
            self.player.setPosition(milliseconds)

    def _set_playback_rate(self) -> None:
        self.player.setPlaybackRate(float(self.speed_combo.currentData()))

    def _update_position(self, milliseconds: int) -> None:
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setValue(milliseconds)
        self.position_label.setText(format_seconds(milliseconds / 1000))

    def _update_duration(self, milliseconds: int) -> None:
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setRange(0, max(0, milliseconds))
        self.duration_label.setText(format_seconds(milliseconds / 1000))

    def _update_play_button(self, state: QMediaPlayer.PlaybackState) -> None:
        self.play_button.setText(
            "暂停"
            if state == QMediaPlayer.PlaybackState.PlayingState
            else "播放"
        )

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

    def _sync_filter_options(self) -> None:
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
            self.sort_combo,
        ):
            self._set_combo_visible_item_count(combo)

    def _apply_table_filters(self) -> None:
        behavior = self.behavior_filter_combo.currentData()
        polarity = self.polarity_filter_combo.currentData()
        status = self.status_filter_combo.currentData()
        selection_model = self.task_table.selectionModel()
        for row, record in enumerate(self.records):
            visible = (
                (behavior is None or behavior in record.behaviors)
                and (polarity is None or polarity == record.polarity)
                and (status is None or status == record.status)
            )
            self.task_table.setRowHidden(row, not visible)
            if not visible:
                selection_model.select(
                    self.task_table.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.Deselect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )

    def clear_table_filters(self) -> None:
        self.behavior_filter_combo.setCurrentIndex(0)
        self.polarity_filter_combo.setCurrentIndex(0)
        self.status_filter_combo.setCurrentIndex(0)
        self._apply_table_filters()

    def _sort_records(self) -> None:
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
        self._clear_active_history()

    @staticmethod
    def _apply_status_color(item: QTableWidgetItem, status: str) -> None:
        colors = {
            "ok": "#2dd4bf",
            "skip": "#fbbf24",
            "fail": "#fb7185",
            "canceled": "#94a3b8",
            "queued": "#cbd5e1",
        }
        item.setForeground(QColor(colors.get(status, "#cbd5e1")))

    def _load_selected_clip(self) -> None:
        selected = self.task_table.selectionModel().selectedRows()
        if len(selected) != 1:
            self._editing_index = None
            self.add_button.setText("添加片段")
            return
        index = selected[0].row()
        record = self.records[index]
        self._editing_index = index
        self.start_spin.setValue(record.start_seconds)
        self.end_spin.setValue(record.end_seconds)
        self.sequence_spin.setValue(max(1, record.sequence))
        for behavior, checkbox in self.behavior_checks.items():
            checkbox.setChecked(behavior in record.behaviors)
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
        self.add_button.setText("更新片段")
        self.player.setPosition(int(record.start_seconds * 1000))
        self._update_filename_preview()

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
    ) -> None:
        selected_indexes = set(indexes)
        proposed: dict[int, ClipRecord] = {}
        skipped_manual_view = False

        for index in indexes:
            record = self.records[index]
            next_behaviors = behaviors if behaviors is not None else record.behaviors
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
        self._clear_active_history()
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
        batch_behavior_checks = {
            behavior: QCheckBox(behavior) for behavior in BEHAVIOR_LABELS
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
            self._apply_batch_changes(indexes, behaviors, polarity, lighting, view)
        except ValueError as error:
            self._show_error("批量修改失败", str(error))

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
        if self._export_worker is not None and self._export_worker.isRunning():
            return
        if self.source_path is None or not self.source_path.is_file():
            self._show_error("没有视频源", "导出前请先导入源视频。")
            return
        if not self.records:
            self._show_error("没有片段任务", "导出前请至少添加一个片段。")
            return
        if self.output_dir is None:
            self._show_error("没有输出文件夹", "导出前请先选择输出文件夹。")
            return

        try:
            ffmpeg = resolve_ffmpeg(self.ffmpeg_edit.text())
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if not self.output_dir.is_dir():
                raise OSError("输出路径不是文件夹")
            outputs = [record.output.lower() for record in self.records]
            if len(outputs) != len(set(outputs)):
                raise ValueError("任务列表中包含重复的输出文件名。")
            for record in self.records:
                validate_output_filename(record.output)
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error("无法开始导出", f"开始导出失败：{error}")
            return

        self._export_worker = ExportWorker(
            records=self.records,
            input_path=self.source_path,
            output_dir=self.output_dir,
            ffmpeg=ffmpeg,
            mode=self.mode_combo.currentText(),
            overwrite=self.overwrite_check.isChecked(),
            workers=self.workers_spin.value(),
        )
        self._export_worker.clip_finished.connect(self._export_clip_finished)
        self._export_worker.progress.connect(self._export_progress)
        self._export_worker.export_completed.connect(self._export_completed)
        self.progress_bar.setRange(0, len(self.records))
        self.progress_bar.setValue(0)
        self.export_button.setEnabled(False)
        self.cancel_export_button.setEnabled(True)
        self._set_status("正在导出片段……")
        self._export_worker.start()

    def cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()
            self.cancel_export_button.setEnabled(False)
            self._set_status("已请求取消，正在完成当前 FFmpeg 任务……")

    def _export_clip_finished(self, _index: int, _result: object) -> None:
        self._refresh_table()

    def _export_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)

    def _export_completed(self, summary: ExportSummary) -> None:
        self._refresh_table()
        self.export_button.setEnabled(True)
        self.cancel_export_button.setEnabled(False)
        self._export_worker = None
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

    def closeEvent(self, event) -> None:
        if self._confirm_discard_dirty_project():
            event.accept()
        else:
            event.ignore()
