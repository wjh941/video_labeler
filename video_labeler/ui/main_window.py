from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QColor, QKeySequence, QShortcut
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
    ("I", "设置起始点"),
    ("O", "设置结束点"),
    ("Enter", "添加或更新片段"),
    ("Delete", "删除选中片段"),
    ("Ctrl+S", "保存标注 CSV"),
    ("Ctrl+E", "批量导出"),
    ("Left / Right", "后退或前进 5 秒"),
    ("Shift+Left / Shift+Right", "后退或前进 30 秒"),
)


class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self._content: QWidget | None = None
        self.toggled.connect(self._set_content_visible)

    def set_content(self, content: QWidget) -> None:
        self._content = content
        content.setVisible(self.isChecked())

    def _set_content_visible(self, expanded: bool) -> None:
        if self._content is not None:
            self._content.setVisible(expanded)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[ClipRecord] = []
        self.source_path: Path | None = None
        self.source_name = ""
        self.output_dir: Path | None = None
        self._editing_index: int | None = None
        self._export_worker: ExportWorker | None = None

        self.setWindowTitle("视频片段标注工具")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)

        self._build_ui()
        self._connect_signals()
        self._update_filename_preview()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

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
        self.editor_splitter.addWidget(self.annotation_scroll)
        self.editor_splitter.setSizes([980, 380])

        self.workspace_splitter.addWidget(self.editor_splitter)
        self.workspace_splitter.addWidget(self._build_task_table())
        self.workspace_splitter.setSizes([520, 340])
        self.workspace_splitter.setStretchFactor(0, 3)
        self.workspace_splitter.setStretchFactor(1, 2)
        root_layout.addWidget(self.workspace_splitter, stretch=1)
        root_layout.addLayout(self._build_export_status())

        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow, QMessageBox { background: #111827; color: #f1f5f9; }
            QWidget { color: #f1f5f9; }
            QGroupBox {
                background: #18212d;
                border: 1px solid #334155;
                border-radius: 5px;
                margin-top: 8px;
                font-weight: 600;
                padding: 7px;
                color: #f1f5f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 9px;
                padding: 0 4px;
                color: #dce5ef;
            }
            QPushButton {
                min-height: 28px;
                padding: 4px 10px;
                background: #253244;
                border: 1px solid #475569;
                border-radius: 4px;
                color: #f1f5f9;
            }
            QPushButton:hover { background: #334155; border-color: #60a5fa; }
            QPushButton:focus { border-color: #60a5fa; }
            QPushButton:pressed { background: #1e293b; }
            QPushButton:disabled { background: #1f2937; color: #64748b; border-color: #334155; }
            QPushButton#primaryButton { background: #2563eb; border-color: #3b82f6; color: #ffffff; }
            QPushButton#primaryButton:hover { background: #1d4ed8; }
            QPushButton#addClipButton { background: #0f9f8c; border-color: #2dd4bf; color: #ffffff; }
            QPushButton#addClipButton:hover { background: #0f8a7a; }
            QPushButton#dangerButton { background: #512033; border-color: #dc4c64; color: #fecdd3; }
            QPushButton#dangerButton:hover { background: #70243b; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 25px;
                padding: 1px 6px;
                background: #101923;
                color: #f1f5f9;
                border: 1px solid #475569;
                border-radius: 4px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #60a5fa;
            }
            QComboBox QAbstractItemView {
                background: #18212d;
                color: #f1f5f9;
                border: 1px solid #475569;
                selection-background-color: #1d4f7a;
            }
            QCheckBox { color: #dce5ef; spacing: 6px; }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                background: #101923;
                border: 1px solid #64748b;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background: #2563eb;
                border-color: #60a5fa;
            }
            QScrollArea { background: #18212d; border: 1px solid #334155; border-radius: 5px; }
            QScrollBar:vertical { background: #111827; width: 11px; margin: 2px; }
            QScrollBar::handle:vertical { background: #475569; min-height: 28px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background: #64748b; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QTableWidget {
                background: #101923;
                color: #f1f5f9;
                gridline-color: #334155;
                selection-background-color: #1d4f7a;
                selection-color: #ffffff;
            }
            QTableWidget::item { padding: 2px 5px; }
            QTableWidget::item:selected { background: #1d4f7a; color: #ffffff; }
            QHeaderView::section {
                background: #253244;
                color: #dce5ef;
                border: 0;
                border-right: 1px solid #475569;
                border-bottom: 1px solid #475569;
                padding: 4px;
                font-weight: 600;
            }
            QSlider::groove:horizontal { background: #334155; height: 5px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #2563eb; border-radius: 2px; }
            QSlider::handle:horizontal { background: #dce5ef; width: 12px; margin: -4px 0; border-radius: 6px; }
            QProgressBar {
                background: #101923;
                border: 1px solid #475569;
                border-radius: 4px;
                color: #f1f5f9;
                text-align: center;
            }
            QProgressBar::chunk { background: #0f9f8c; border-radius: 3px; }
            """
        )

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
        self.output_folder_label.setStyleSheet("color: #a8b3c2;")

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

    def _build_video_panel(self) -> QGroupBox:
        group = QGroupBox("视频预览")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(240)
        self.video_widget.setStyleSheet("background: #111827;")
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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        self.source_label = QLabel("未选择视频")
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet("color: #a8b3c2;")
        layout.addWidget(self.source_label)

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
        self.clear_button = QPushButton("清空编辑区")
        self.add_button.setObjectName("addClipButton")
        self.remove_button.setObjectName("dangerButton")
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)

        self.behavior_checks: dict[str, QCheckBox] = {}
        self.behaviors_group = CollapsibleGroupBox("行为标签")
        self.behavior_checks_container = QWidget()
        self.behavior_checks_layout = QGridLayout(self.behavior_checks_container)
        self.behavior_checks_layout.setContentsMargins(0, 0, 0, 0)
        self.behavior_checks_layout.setHorizontalSpacing(10)
        self.behavior_checks_layout.setVerticalSpacing(4)
        self.behavior_columns = 2

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
        columns = 3 if self.width() >= 1280 else 2
        self.behavior_columns = columns
        while self.behavior_checks_layout.count():
            self.behavior_checks_layout.takeAt(0)
        for index, checkbox in enumerate(self.behavior_checks.values()):
            row, column = divmod(index, columns)
            self.behavior_checks_layout.addWidget(checkbox, row, column)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "behavior_checks_layout"):
            self._reflow_behavior_checks()

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
            "快捷键：空格 播放/暂停，I/O 设置起止点，Enter 添加，Delete 删除，"
            "Ctrl+S 保存，Ctrl+E 导出"
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
        self.output_folder_button.clicked.connect(self.select_output_folder)
        self.play_button.clicked.connect(self.toggle_playback)
        self.seek_back_button.clicked.connect(lambda: self._seek_relative(-5000))
        self.seek_forward_button.clicked.connect(lambda: self._seek_relative(5000))
        self.set_start_button.clicked.connect(
            lambda: self.start_spin.setValue(self.player.position() / 1000)
        )
        self.set_end_button.clicked.connect(
            lambda: self.end_spin.setValue(self.player.position() / 1000)
        )
        self.timeline_slider.valueChanged.connect(self._seek_to_milliseconds)
        self.speed_combo.currentIndexChanged.connect(self._set_playback_rate)
        self.player.positionChanged.connect(self._update_position)
        self.player.durationChanged.connect(self._update_duration)
        self.player.playbackStateChanged.connect(self._update_play_button)
        self.player.errorOccurred.connect(self._media_error)
        self.advanced_export_group.toggled.connect(
            self.advanced_export_content.setVisible
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
            "set_start": (
                "I",
                lambda: self.start_spin.setValue(self.player.position() / 1000),
            ),
            "set_end": (
                "O",
                lambda: self.end_spin.setValue(self.player.position() / 1000),
            ),
            "add_clip": ("Return", self.add_or_update_clip),
            "delete_selected": ("Del", self.remove_selected_clip),
            "save_csv": ("Ctrl+S", self.save_csv),
            "start_export": ("Ctrl+E", self.start_export),
            "seek_back_5": ("Left", lambda: self._seek_relative(-5000)),
            "seek_forward_5": ("Right", lambda: self._seek_relative(5000)),
            "seek_back_30": ("Shift+Left", lambda: self._seek_relative(-30000)),
            "seek_forward_30": ("Shift+Right", lambda: self._seek_relative(30000)),
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
        self.source_path = path
        self.source_name = path.name
        self.source_label.setText(path.name)
        self._set_status(f"已选择视频：{path.name}")

    def open_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "导入视频",
            "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov *.m4v);;所有文件 (*.*)",
        )
        if not filename:
            return
        path = Path(filename)
        self.set_source_path(path)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.pause()

    def import_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入片段 CSV", "", "CSV 文件 (*.csv)"
        )
        if not filename:
            return
        try:
            self.records = read_clip_csv(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error("无法导入 CSV", f"导入 CSV 失败：{error}")
            return

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
        self._set_status(f"已导入 {len(self.records)} 个任务")

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
            self, "选择输出文件夹", str(self.output_dir or Path.home())
        )
        if not directory:
            return
        self.output_dir = Path(directory)
        self.output_folder_label.setText(str(self.output_dir))
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
        if self._editing_index is None:
            self.records.append(record)
            self.sequence_spin.setValue(
                next_sequence([item.sequence for item in self.records])
            )
            self._set_status(f"已添加片段 {sequence:03d}")
        else:
            self.records[self._editing_index] = record
            self._set_status(f"已更新片段 {sequence:03d}")

        self._editing_index = None
        self.add_button.setText("添加片段")
        self._refresh_table()

    def remove_selected_clip(self) -> None:
        self._delete_selected_records()

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

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

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
        for index in reversed(indexes):
            del self.records[index]
        self._editing_index = None
        self.add_button.setText("添加片段")
        self._refresh_table()
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
