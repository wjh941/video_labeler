from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
from ..naming import build_filename, next_sequence, parse_filename


TABLE_COLUMNS = (
    "Sequence",
    "Start",
    "End",
    "Duration",
    "Behaviors",
    "Polarity",
    "Lighting",
    "Output Filename",
    "Status",
    "Error",
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[ClipRecord] = []
        self.source_path: Path | None = None
        self.source_name = ""
        self.output_dir: Path | None = None
        self._editing_index: int | None = None
        self._export_worker: ExportWorker | None = None

        self.setWindowTitle("Video Segment Labeler")
        self.setMinimumSize(1120, 720)
        self.resize(1440, 900)

        self._build_ui()
        self._connect_signals()
        self._update_filename_preview()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_project_header())

        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_splitter.setChildrenCollapsible(False)
        editor_splitter.addWidget(self._build_video_panel())
        editor_splitter.addWidget(self._build_clip_editor())
        editor_splitter.setSizes([940, 360])
        root_layout.addWidget(editor_splitter, stretch=3)

        root_layout.addWidget(self._build_task_table(), stretch=2)
        root_layout.addLayout(self._build_export_status())

        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f8; }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #cfd6dd;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: 600;
                padding: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { min-height: 28px; padding: 4px 10px; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 26px;
                background: #ffffff;
            }
            QTableWidget {
                background: #ffffff;
                gridline-color: #d7dde3;
                selection-background-color: #cfe8ff;
                selection-color: #1f2933;
            }
            QHeaderView::section {
                background: #e8edf2;
                border: 0;
                border-right: 1px solid #cfd6dd;
                border-bottom: 1px solid #cfd6dd;
                padding: 5px;
                font-weight: 600;
            }
            """
        )

    def _build_project_header(self) -> QGroupBox:
        group = QGroupBox("Project")
        layout = QGridLayout(group)
        layout.setColumnStretch(5, 1)

        self.open_video_button = QPushButton("Open Video")
        self.import_csv_button = QPushButton("Import CSV")
        self.save_csv_button = QPushButton("Save Annotation CSV")
        self.output_folder_button = QPushButton("Output Folder")
        self.output_folder_label = QLabel("No output folder selected")
        self.output_folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYYMMDD")
        self.camera_edit = QLineEdit()
        self.camera_edit.setPlaceholderText("cam02")
        self.view_combo = QComboBox()
        self.view_combo.addItems(VIEW_TYPES)

        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.setPlaceholderText("Leave empty to use FFmpeg on PATH")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(("encode", "copy"))
        self.overwrite_check = QCheckBox("Overwrite existing clips")
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 64)
        self.workers_spin.setValue(0)
        self.workers_spin.setSpecialValueText("Auto")

        layout.addWidget(self.open_video_button, 0, 0)
        layout.addWidget(self.import_csv_button, 0, 1)
        layout.addWidget(self.save_csv_button, 0, 2)
        layout.addWidget(self.output_folder_button, 0, 3)
        layout.addWidget(self.output_folder_label, 0, 4, 1, 2)

        layout.addWidget(QLabel("Date"), 1, 0)
        layout.addWidget(self.date_edit, 1, 1)
        layout.addWidget(QLabel("Camera"), 1, 2)
        layout.addWidget(self.camera_edit, 1, 3)
        layout.addWidget(QLabel("View"), 1, 4)
        layout.addWidget(self.view_combo, 1, 5)

        layout.addWidget(QLabel("FFmpeg"), 2, 0)
        layout.addWidget(self.ffmpeg_edit, 2, 1, 1, 3)
        layout.addWidget(QLabel("Mode"), 2, 4)
        layout.addWidget(self.mode_combo, 2, 5)
        layout.addWidget(self.overwrite_check, 3, 0, 1, 2)
        layout.addWidget(QLabel("Parallel exports"), 3, 2)
        layout.addWidget(self.workers_spin, 3, 3)
        return group

    def _build_video_panel(self) -> QGroupBox:
        group = QGroupBox("Video Review")
        layout = QVBoxLayout(group)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(300)
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
        self.play_button = QPushButton("Play")
        self.seek_back_button = QPushButton("-5s")
        self.seek_forward_button = QPushButton("+5s")
        self.set_start_button = QPushButton("Set Start")
        self.set_end_button = QPushButton("Set End")
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
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(self.speed_combo)
        layout.addLayout(controls)
        return group

    def _build_clip_editor(self) -> QGroupBox:
        group = QGroupBox("Clip Annotation")
        layout = QVBoxLayout(group)

        self.source_label = QLabel("No video selected")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        time_form = QFormLayout()
        self.start_spin = self._new_time_spin()
        self.end_spin = self._new_time_spin()
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 999999)
        self.sequence_spin.setValue(1)
        time_form.addRow("Start", self.start_spin)
        time_form.addRow("End", self.end_spin)
        time_form.addRow("Sequence", self.sequence_spin)
        layout.addLayout(time_form)

        layout.addWidget(QLabel("Behaviors"))
        self.behavior_checks: dict[str, QCheckBox] = {}
        behaviors_widget = QWidget()
        behaviors_layout = QVBoxLayout(behaviors_widget)
        behaviors_layout.setContentsMargins(2, 2, 2, 2)
        behaviors_layout.setSpacing(2)
        for behavior in BEHAVIOR_LABELS:
            checkbox = QCheckBox(behavior)
            self.behavior_checks[behavior] = checkbox
            behaviors_layout.addWidget(checkbox)
        behaviors_layout.addStretch(1)

        behavior_scroll = QScrollArea()
        behavior_scroll.setWidgetResizable(True)
        behavior_scroll.setWidget(behaviors_widget)
        behavior_scroll.setMinimumHeight(155)
        layout.addWidget(behavior_scroll)

        labels_form = QFormLayout()
        self.polarity_combo = QComboBox()
        self.polarity_combo.addItems(POLARITIES)
        self.lighting_combo = QComboBox()
        self.lighting_combo.addItems(LIGHTING_VALUES)
        labels_form.addRow("Polarity", self.polarity_combo)
        labels_form.addRow("Lighting", self.lighting_combo)
        layout.addLayout(labels_form)

        layout.addWidget(QLabel("Generated filename"))
        self.filename_preview = QLineEdit()
        self.filename_preview.setReadOnly(True)
        layout.addWidget(self.filename_preview)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Add Clip")
        self.remove_button = QPushButton("Remove Selected")
        self.clear_button = QPushButton("Clear Editor")
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)
        return group

    def _build_task_table(self) -> QGroupBox:
        group = QGroupBox("Clip Tasks")
        layout = QVBoxLayout(group)

        self.task_table = QTableWidget(0, len(TABLE_COLUMNS))
        self.task_table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.task_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.task_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.task_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(28)
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for column, width in enumerate((72, 98, 98, 82, 210, 72, 150, 430, 80, 260)):
            self.task_table.setColumnWidth(column, width)
        layout.addWidget(self.task_table)
        return group

    def _build_export_status(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.export_button = QPushButton("Batch Export")
        self.cancel_export_button = QPushButton("Cancel Export")
        self.cancel_export_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.status_label = QLabel("Ready")

        layout.addWidget(self.export_button)
        layout.addWidget(self.cancel_export_button)
        layout.addWidget(self.progress_bar, stretch=1)
        layout.addWidget(self.status_label)
        return layout

    def _new_time_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 7 * 24 * 60 * 60)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        return spin

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
        self.task_table.itemSelectionChanged.connect(self._load_selected_clip)
        self.task_table.cellChanged.connect(self._table_cell_changed)

        self.export_button.clicked.connect(self.start_export)
        self.cancel_export_button.clicked.connect(self.cancel_export)

    def set_source_path(self, path: Path) -> None:
        self.source_path = path
        self.source_name = path.name
        self.source_label.setText(path.name)
        self._set_status(f"Video selected: {path.name}")

    def open_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video files (*.mp4 *.avi *.mkv *.mov *.m4v);;All files (*.*)",
        )
        if not filename:
            return
        path = Path(filename)
        self.set_source_path(path)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.pause()

    def import_csv(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Clip CSV", "", "CSV files (*.csv)"
        )
        if not filename:
            return
        try:
            self.records = read_clip_csv(Path(filename))
        except (OSError, ValueError) as error:
            self._show_error("Could not import CSV", str(error))
            return

        if self.records:
            self.source_name = self.records[0].source
            self.source_label.setText(self.source_name)
            parsed = parse_filename(self.records[0].output)
            if parsed:
                self.date_edit.setText(parsed.metadata.date)
                self.camera_edit.setText(parsed.metadata.camera)
                self.view_combo.setCurrentText(parsed.metadata.view)
            self.sequence_spin.setValue(
                next_sequence([record.sequence for record in self.records])
            )
        self._editing_index = None
        self._refresh_table()
        self._set_status(f"Imported {len(self.records)} task(s)")

    def save_csv(self) -> None:
        if not self.records:
            self._show_error("No clip tasks", "Add at least one clip before saving CSV.")
            return
        default_name = (
            f"{Path(self.source_name).stem}_clips.csv"
            if self.source_name
            else "clips.csv"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Annotation CSV",
            default_name,
            "CSV files (*.csv)",
        )
        if not filename:
            return
        try:
            write_clip_csv(Path(filename), self.records)
        except OSError as error:
            self._show_error("Could not save CSV", str(error))
            return
        self._set_status(f"Saved CSV: {filename}")

    def select_output_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", str(self.output_dir or Path.home())
        )
        if not directory:
            return
        self.output_dir = Path(directory)
        self.output_folder_label.setText(str(self.output_dir))
        self._set_status(f"Output folder: {self.output_dir}")

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
                raise ValueError("Select a source video before adding a clip.")
            start_seconds = self.start_spin.value()
            end_seconds = self.end_spin.value()
            if end_seconds <= start_seconds:
                raise ValueError("End time must be later than start time.")

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
            self._show_error("Cannot add clip", str(error))
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
            self._set_status(f"Added clip {sequence:03d}")
        else:
            self.records[self._editing_index] = record
            self._set_status(f"Updated clip {sequence:03d}")

        self._editing_index = None
        self.add_button.setText("Add Clip")
        self._refresh_table()

    def remove_selected_clip(self) -> None:
        selected = self.task_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        del self.records[row]
        self._editing_index = None
        self.add_button.setText("Add Clip")
        self._refresh_table()
        self._set_status("Removed selected clip")

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
        self.add_button.setText("Add Clip")
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
            "Pause"
            if state == QMediaPlayer.PlaybackState.PlayingState
            else "Play"
        )

    def _media_error(self, _error: QMediaPlayer.Error, text: str) -> None:
        if text:
            self._set_status(f"Video playback error: {text}")

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
                raise ValueError(f"Duplicate output filename: {output}")

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
                    record.status,
                    record.error,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column != 7:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if column == 8:
                        self._apply_status_color(item, record.status)
                    self.task_table.setItem(row, column, item)

    @staticmethod
    def _apply_status_color(item: QTableWidgetItem, status: str) -> None:
        colors = {
            "ok": "#0f766e",
            "skip": "#a16207",
            "fail": "#b91c1c",
            "canceled": "#475569",
            "queued": "#334155",
        }
        item.setForeground(QColor(colors.get(status, "#334155")))

    def _load_selected_clip(self) -> None:
        selected = self.task_table.selectionModel().selectedRows()
        if not selected:
            return
        index = selected[0].row()
        record = self.records[index]
        self._editing_index = index
        self.start_spin.setValue(record.start_seconds)
        self.end_spin.setValue(record.end_seconds)
        self.sequence_spin.setValue(max(1, record.sequence))
        for behavior, checkbox in self.behavior_checks.items():
            checkbox.setChecked(behavior in record.behaviors)
        if record.polarity in POLARITIES:
            self.polarity_combo.setCurrentText(record.polarity)
        if record.lighting in LIGHTING_VALUES:
            self.lighting_combo.setCurrentText(record.lighting)
        self.add_button.setText("Update Clip")
        self.player.setPosition(int(record.start_seconds * 1000))
        self._update_filename_preview()

    def _table_cell_changed(self, row: int, column: int) -> None:
        if column != 7 or row >= len(self.records):
            return
        item = self.task_table.item(row, column)
        if item is None:
            return
        output = item.text().strip()
        if not output.lower().endswith(".mp4"):
            self._show_error("Invalid filename", "Output filename must end with .mp4")
            self._refresh_table()
            return
        try:
            editing_index = self._editing_index
            self._editing_index = row
            self._assert_output_is_unique(output)
            self._editing_index = editing_index
        except ValueError as error:
            self._editing_index = editing_index
            self._show_error("Duplicate filename", str(error))
            self._refresh_table()
            return
        self.records[row].output = output
        self._set_status(f"Updated output filename for clip {row + 1}")

    def start_export(self) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            return
        if self.source_path is None or not self.source_path.is_file():
            self._show_error("No video source", "Open the source video before exporting.")
            return
        if not self.records:
            self._show_error("No clip tasks", "Add at least one clip before exporting.")
            return
        if self.output_dir is None:
            self._show_error("No output folder", "Select an output folder before exporting.")
            return

        try:
            ffmpeg = resolve_ffmpeg(self.ffmpeg_edit.text())
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if not self.output_dir.is_dir():
                raise OSError("output path is not a folder")
            outputs = [record.output.lower() for record in self.records]
            if len(outputs) != len(set(outputs)):
                raise ValueError("The task list contains duplicate output filenames.")
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error("Cannot start export", str(error))
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
        self._set_status("Exporting clips...")
        self._export_worker.start()

    def cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()
            self.cancel_export_button.setEnabled(False)
            self._set_status("Cancel requested. Finishing active FFmpeg tasks...")

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
            "Export complete: "
            f"success={summary.success} skipped={summary.skipped} "
            f"failed={summary.failed} canceled={summary.canceled}"
        )

    def _show_error(self, title: str, text: str) -> None:
        self._set_status(text)
        QMessageBox.warning(self, title, text)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
