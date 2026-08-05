from collections.abc import Callable, Collection, Sequence
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
    QCheckBox,
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
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QStyle,
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
        selected_count = len(self.checked_tags())
        self.setEditText(
            f"已选 {selected_count} 项" if selected_count else "请选择行为标签"
        )


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
        self._last_playback_rate = 1.0
        self._button_hover_effects: dict[
            QPushButton, QGraphicsDropShadowEffect
        ] = {}
        self._button_hover_animations: dict[
            QPushButton, QPropertyAnimation
        ] = {}
        self.historical_behavior_tags: tuple[str, ...] = ()
        self.historical_tag_labels: dict[str, QLabel] = {}

        self.setWindowTitle("视频片段标注工具")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)

        self._build_ui()
        self._build_project_menu()
        self._connect_signals()
        self._update_filename_preview()
        self._update_history_controls()

    def _build_ui(self) -> None:
        self.workspace_content = QWidget()
        self.workspace_content.setObjectName("workspaceContent")
        self.workspace_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root_layout = QVBoxLayout(self.workspace_content)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        self.project_header = self._build_project_header()
        root_layout.addWidget(self.project_header)

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
        self.task_panel.setMinimumHeight(320)
        self.annotation_workspace_layout.addWidget(self.annotation_panel)
        self.annotation_workspace_layout.addWidget(self.task_panel, 1)

        workspace_layout.addWidget(self.video_panel, 13)
        workspace_layout.addWidget(self.annotation_workspace, 12)

        self.task_table_dialog = QDialog(self)
        self.task_table_dialog.setWindowTitle("片段任务")
        self.task_table_dialog.setObjectName("taskTableDialog")
        self.task_table_dialog.setModal(False)
        self.task_table_dialog.setMinimumSize(900, 500)
        self.task_table_dialog.setLayout(QVBoxLayout())
        self.task_table_dialog.finished.connect(self._restore_task_panel)

        root_layout.addWidget(self.workspace_row, stretch=1)
        root_layout.addLayout(self._build_export_status())

        for card in (
            self.project_header,
            self.video_panel,
            self.annotation_panel,
            self.task_panel,
        ):
            self._apply_card_shadow(card)
        self._install_presentation_button_effects()

        self.setCentralWidget(self.workspace_content)

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
            self.shortcut_help_button,
            self.play_button,
            self.seek_back_button,
            self.seek_forward_button,
            self.set_start_button,
            self.set_end_button,
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

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
        self.video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
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
        layout.addSpacing(16)

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
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.setTracking(False)
        self.timeline_slider.setMinimumHeight(28)
        position_layout.addWidget(self.position_label)
        position_layout.addWidget(self.timeline_slider, stretch=1)
        position_layout.addWidget(self.duration_label)
        video_controls_layout.addLayout(position_layout)

        transport_controls = QHBoxLayout()
        transport_controls.setSpacing(8)
        self.play_button = QPushButton("播放")
        self.seek_back_button = QPushButton("-5s")
        self.seek_forward_button = QPushButton("+5s")
        self.set_start_button = QPushButton("设置起始点")
        self.set_end_button = QPushButton("设置结束点")
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

        transport_controls.addWidget(self.play_button)
        transport_controls.addWidget(self.seek_back_button)
        transport_controls.addWidget(self.seek_forward_button)
        transport_controls.addStretch(1)
        transport_controls.addWidget(self.set_start_button)
        transport_controls.addWidget(self.set_end_button)
        video_controls_layout.addLayout(transport_controls)

        playback_rate_layout = QHBoxLayout()
        playback_rate_layout.setSpacing(8)
        playback_rate_layout.addStretch(1)
        playback_rate_layout.addWidget(QLabel("播放速度"))
        playback_rate_layout.addWidget(self.playback_rate_badge)
        playback_rate_layout.addWidget(self.speed_combo)
        playback_rate_layout.addWidget(self.custom_speed_spin)
        video_controls_layout.addLayout(playback_rate_layout)
        layout.addWidget(self.video_controls_panel)
        return group

    def _build_clip_editor(self) -> QGroupBox:
        group = QGroupBox("片段标注")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

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

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.add_button = QPushButton("添加片段")
        self.remove_button = QPushButton("删除所选")
        self.undo_button = QPushButton("撤销")
        self.redo_button = QPushButton("重做")
        self.clear_button = QPushButton("清空编辑区")
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
        ):
            button.setMinimumHeight(34)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            actions.addWidget(button)
        layout.addLayout(actions)

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
        remove_custom_tag_layout.addWidget(self.custom_tag_library_combo, stretch=1)
        remove_custom_tag_layout.addWidget(
            self.remove_custom_behavior_tag_button
        )
        custom_tags_layout.addLayout(remove_custom_tag_layout)
        custom_tags_group_layout = QVBoxLayout(self.custom_tags_group)
        custom_tags_group_layout.setContentsMargins(6, 6, 6, 6)
        custom_tags_group_layout.addWidget(custom_tags_content)
        self.custom_tags_group.set_content(custom_tags_content)
        layout.addWidget(self.custom_tags_group)
        self._sync_custom_tag_library()

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
        while labels_form.count():
            labels_form.takeAt(0)

        self.lighting_group = CollapsibleGroupBox("光照条件")
        self.lighting_group.setChecked(False)
        lighting_content = QWidget()
        lighting_form = QFormLayout(lighting_content)
        lighting_form.addRow("光照", self.lighting_combo)
        lighting_layout = QVBoxLayout(self.lighting_group)
        lighting_layout.setContentsMargins(6, 6, 6, 6)
        lighting_layout.addWidget(lighting_content)
        self.lighting_group.set_content(lighting_content)
        layout.addWidget(self.lighting_group)

        self.polarity_group = CollapsibleGroupBox("正负例")
        self.polarity_group.setChecked(False)
        polarity_content = QWidget()
        polarity_form = QFormLayout(polarity_content)
        polarity_form.addRow("正负例", self.polarity_combo)
        polarity_layout = QVBoxLayout(self.polarity_group)
        polarity_layout.setContentsMargins(6, 6, 6, 6)
        polarity_layout.addWidget(polarity_content)
        self.polarity_group.set_content(polarity_content)
        layout.addWidget(self.polarity_group)

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

    def _sync_behavior_selection_from_combo(self) -> None:
        selected = set(self.behavior_tag_combo.checked_tags())
        for behavior, checkbox in self.behavior_checks.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(behavior in selected)
        self._update_filename_preview()

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
        self.task_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.task_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(34)
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for column, width in enumerate((72, 98, 98, 82, 210, 72, 150, 430, 80, 260)):
            self.task_table.setColumnWidth(column, width)

        self.table_filter_bar = QWidget()
        self.table_filter_bar.setObjectName("tableFilterBar")
        filter_layout = QVBoxLayout(self.table_filter_bar)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(6)
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
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("编号升序", ("sequence", False))
        self.sort_combo.addItem("编号降序", ("sequence", True))
        self.sort_combo.addItem("时长升序", ("duration", False))
        self.sort_combo.addItem("时长降序", ("duration", True))
        self.clear_filters_button = QPushButton("清空筛选")

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

    def _show_task_table_dialog(self) -> None:
        if self.task_panel.parentWidget() is self.task_table_dialog:
            self.task_table_dialog.raise_()
            self.task_table_dialog.activateWindow()
            return

        self.task_panel.setParent(None)
        dialog_layout = self.task_table_dialog.layout()
        assert dialog_layout is not None
        dialog_layout.addWidget(self.task_panel)
        self.task_table_dialog.show()
        self.task_table_dialog.raise_()
        self.task_table_dialog.activateWindow()

    def _restore_task_panel(self, *_args: object) -> None:
        if self.task_panel.parentWidget() is self.annotation_workspace:
            return

        dialog_layout = self.task_table_dialog.layout()
        if dialog_layout is not None:
            dialog_layout.removeWidget(self.task_panel)
        self.task_panel.setParent(None)
        self.annotation_workspace_layout.addWidget(self.task_panel, 1)
        self.task_panel.show()

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
        self.sequence_spin.valueChanged.connect(self._update_filename_preview)
        self.add_custom_behavior_tag_button.clicked.connect(
            self.add_custom_behavior_tag
        )
        self.custom_behavior_tag_edit.returnPressed.connect(
            self.add_custom_behavior_tag
        )
        self.remove_custom_behavior_tag_button.clicked.connect(
            self._remove_selected_custom_behavior_tag
        )

        self.add_button.clicked.connect(self.add_or_update_clip)
        self.remove_button.clicked.connect(self.remove_selected_clip)
        self.undo_button.clicked.connect(self.undo_segments)
        self.redo_button.clicked.connect(self.redo_segments)
        self.clear_button.clicked.connect(self.clear_editor)
        self.batch_edit_button.clicked.connect(self.show_batch_edit_dialog)
        self.batch_delete_button.clicked.connect(self._delete_selected_records)
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
        self._project_dirty = False
        self._backup_timer.stop()
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
        self._set_output_folder_display()
        self._mark_project_dirty()
        self._set_status(f"输出文件夹：{self.output_dir}")

    def set_clip_range(self, start_seconds: float, end_seconds: float) -> None:
        self.start_spin.setValue(start_seconds)
        self.end_spin.setValue(end_seconds)

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
        self._rebuild_behavior_controls(selected)
        self._mark_project_dirty()

    def _remove_selected_custom_behavior_tag(self) -> None:
        tag = self.custom_tag_library_combo.currentData()
        if isinstance(tag, str):
            self._remove_custom_behavior_tag(tag)

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
        self.historical_behavior_tags = ()
        self._rebuild_behavior_controls(())
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
        self.historical_behavior_tags = ()
        self._rebuild_behavior_controls(())
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

    def _update_duration(self, milliseconds: int) -> None:
        with QSignalBlocker(self.timeline_slider):
            self.timeline_slider.setRange(0, max(0, milliseconds))
        self.duration_label.setText(format_seconds(milliseconds / 1000))

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
        self._export_records = list(self.records)
        self._export_record_states = [
            (record.status, record.error) for record in self._export_records
        ]
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
        if not 0 <= _index < len(self._export_records):
            return
        record = self._export_records[_index]
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

    def _export_completed(self, summary: ExportSummary) -> None:
        self._refresh_table()
        self.export_button.setEnabled(True)
        self.cancel_export_button.setEnabled(False)
        self._export_worker = None
        self._export_records = []
        self._export_record_states = []
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
