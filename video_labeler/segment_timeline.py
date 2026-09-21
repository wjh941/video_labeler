"""Timeline slider with visual segment edges that users can drag."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class SegmentTimelineSlider(QSlider):
    segment_range_changed = Signal(int, int)
    range_drafted = Signal(int, int)

    _DRAFT_MIN_MS = 200

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._segment_start: int | None = None
        self._segment_end: int | None = None
        self._dragged_edge: str | None = None
        self._segment_ranges: list[tuple[int, int]] = []
        self._draft_start: int | None = None
        self._draft_value: int | None = None
        self._activity_marks: list[int] = []
        self.setMouseTracking(True)
        self.setToolTip(
            "拖动片段左右边缘调整起止时间；在空白处按住拖动可直接框选新片段"
        )

    def set_segment_range(self, start: int, end: int) -> None:
        low = self.minimum()
        high = self.maximum()
        start = max(low, min(high, int(start)))
        end = max(start, min(high, int(end)))
        if (start, end) == (self._segment_start, self._segment_end):
            return
        self._segment_start = start
        self._segment_end = end
        self.update()

    def set_segment_ranges(self, ranges: list[tuple[int, int]]) -> None:
        low, high = self.minimum(), self.maximum()
        normalized = []
        for start, end in ranges:
            start = max(low, min(high, int(start)))
            end = max(start, min(high, int(end)))
            if end > start:
                normalized.append((start, end))
        if normalized != self._segment_ranges:
            self._segment_ranges = normalized
            self.update()

    def set_activity_marks(self, marks: list[int]) -> None:
        low, high = self.minimum(), self.maximum()
        normalized = sorted(
            int(mark) for mark in marks if low <= int(mark) <= high
        )
        if normalized != self._activity_marks:
            self._activity_marks = normalized
            self.update()

    def activity_marks(self) -> list[int]:
        return list(self._activity_marks)

    def segment_range(self) -> tuple[int, int] | None:
        if self._segment_start is None or self._segment_end is None:
            return None
        return self._segment_start, self._segment_end

    def adjust_segment_edge(self, edge: str, value: int) -> None:
        if self.segment_range() is None or edge not in {"start", "end"}:
            return
        start, end = self.segment_range()
        bounded = max(self.minimum(), min(self.maximum(), int(value)))
        if edge == "start":
            start = min(bounded, end)
        else:
            end = max(start, bounded)
        self.set_segment_range(start, end)
        self.segment_range_changed.emit(start, end)

    _TICK_STEPS = (
        1_000,
        2_000,
        5_000,
        10_000,
        15_000,
        30_000,
        60_000,
        120_000,
        300_000,
        600_000,
        900_000,
        1_800_000,
        3_600_000,
        7_200_000,
        10_800_000,
        21_600_000,
    )

    def _draw_time_ticks(self, painter: QPainter, groove) -> None:
        """Draw absolute-time ticks so long videos stay navigable."""
        span = self.maximum() - self.minimum()
        if span <= 0 or groove.width() <= 0:
            return
        rough = span * 90.0 / groove.width()
        interval = next(
            (step for step in self._TICK_STEPS if step >= rough),
            self._TICK_STEPS[-1],
        )
        painter.setPen(QPen(QColor(148, 163, 184), 1))
        font = QFont(painter.font())
        font.setPointSize(6)
        painter.setFont(font)
        value = interval
        while value < self.maximum():
            x = self._position_for_value(value)
            painter.drawLine(int(x), 11, int(x), 15)
            painter.drawText(
                QRectF(x - 34, 0, 68, 11),
                Qt.AlignmentFlag.AlignCenter,
                self._format_time(value),
            )
            value += interval

    def _draw_playback_progress(self, painter: QPainter, groove) -> None:
        """Paint the played portion on top so annotation bands never hide it."""
        progress = self.sliderPosition() if self.isSliderDown() else self.value()
        progress = min(max(progress, self.minimum()), self.maximum())
        if self.maximum() <= 0 or progress <= self.minimum():
            return
        x = self._position_for_value(progress)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(37, 99, 235, 225))
        painter.drawRoundedRect(
            QRectF(
                groove.x() + 1,
                groove.center().y() - 2,
                max(0.0, x - groove.x() - 1),
                4,
            ),
            2,
            2,
        )

    def _draw_activity_marks(self, painter: QPainter, groove) -> None:
        if not self._activity_marks:
            return
        painter.setPen(QPen(QColor("#f59e0b"), 1))
        for mark in self._activity_marks:
            x = self._position_for_value(mark)
            painter.drawLine(int(x), 15, int(x), groove.bottom() - 2)

    def _draw_draft_range(self, painter: QPainter, groove) -> None:
        if self._draft_start is None or self._draft_value is None:
            return
        left_value = min(self._draft_start, self._draft_value)
        right_value = max(self._draft_start, self._draft_value)
        left = self._position_for_value(left_value)
        right = self._position_for_value(right_value)
        center_y = self.height() / 2
        painter.setPen(QPen(QColor("#22c55e"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(34, 197, 94, 60))
        painter.drawRoundedRect(
            QRectF(left, center_y - 4, max(4, right - left), 8), 4, 4
        )
        painter.setBrush(QColor("#facc15"))
        for position in (left, right):
            painter.drawRoundedRect(
                QRectF(position - 3, center_y - 6, 6, 12), 3, 3
            )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        groove = self._groove_rect()
        self._draw_time_ticks(painter, groove)
        self._draw_activity_marks(painter, groove)
        segment = self.segment_range()
        if (segment is None or segment[1] <= segment[0]) and not self._segment_ranges:
            self._draw_playback_progress(painter, groove)
            return
        painter.setPen(Qt.PenStyle.NoPen)
        # Show existing annotations as quiet context bands; the active range
        # is painted above them in a brighter color below.
        for start, end in self._segment_ranges:
            left = self._position_for_value(start)
            right = self._position_for_value(end)
            painter.setBrush(QColor(56, 189, 248, 72))
            painter.drawRoundedRect(QRectF(left, groove.center().y() - 3, max(3, right - left), 6), 3, 3)
        if segment is not None and segment[1] > segment[0]:
            painter.setBrush(QColor("#22c55e"))
            left = self._position_for_value(segment[0])
            right = self._position_for_value(segment[1])
            center_y = self.height() / 2
            painter.drawRoundedRect(
                QRectF(left, center_y - 4, max(4, right - left), 8), 4, 4
            )
            painter.setBrush(QColor("#facc15"))
            for position in (left, right):
                painter.drawRoundedRect(
                    QRectF(position - 4, center_y - 7, 8, 14), 4, 4
                )
            self._draw_playback_progress(painter, groove)
            painter.setPen(QColor("#e2e8f0"))
            font = QFont(painter.font())
            font.setPointSize(7)
            painter.setFont(font)
            painter.drawText(
                QRectF(left - 52, center_y + 7, 104, 12),
                Qt.AlignmentFlag.AlignCenter,
                self._format_time(segment[0]),
            )
            painter.drawText(
                QRectF(right - 52, center_y + 7, 104, 12),
                Qt.AlignmentFlag.AlignCenter,
                self._format_time(segment[1]),
            )
        self._draw_draft_range(painter, groove)

    @staticmethod
    def _format_time(milliseconds: int) -> str:
        total_ms = int(milliseconds)
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, ms = divmod(rem, 1000)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}.{ms:03d}"

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        segment = self.segment_range()
        if segment is not None:
            self._dragged_edge = self._edge_at_position(event.position().x())
            if self._dragged_edge is not None:
                event.accept()
                return
        self._draft_start = self._value_for_position(event.position().x())
        self._draft_value = self._draft_start
        event.accept()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        hover_value = self._value_for_position(event.position().x())
        if self._dragged_edge is not None:
            self.adjust_segment_edge(self._dragged_edge, hover_value)
            event.accept()
            return
        if self._draft_start is not None:
            self._draft_value = hover_value
            low, high = sorted((self._draft_start, self._draft_value))
            self.setToolTip(
                f"{self._format_time(low)} → {self._format_time(high)}"
            )
            self.update()
            event.accept()
            return
        self.setToolTip(self._format_time(hover_value))
        edge = self._edge_at_position(event.position().x())
        if edge is not None:
            self.setToolTip(
                "拖动调整片段"
                + ("起点" if edge == "start" else "终点")
                + f"（当前 {self._format_time(hover_value)}）"
            )
        self.setCursor(
            Qt.CursorShape.SizeHorCursor
            if edge is not None
            else Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragged_edge is not None:
            self._dragged_edge = None
            event.accept()
            return
        if self._draft_start is not None:
            press = self._draft_start
            current = self._draft_value
            low = min(press, current)
            high = max(press, current)
            self._draft_start = None
            self._draft_value = None
            if high - low >= self._DRAFT_MIN_MS:
                self.range_drafted.emit(low, high)
            else:
                # 视为单击：恢复默认的点按跳转行为
                self.setValue(press)
                self.sliderReleased.emit()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self._dragged_edge is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def _edge_at_position(self, position: float) -> str | None:
        segment = self.segment_range()
        if segment is None:
            return None
        if abs(position - self._position_for_value(segment[0])) <= 10:
            return "start"
        if abs(position - self._position_for_value(segment[1])) <= 10:
            return "end"
        return None

    def _position_for_value(self, value: int) -> int:
        groove = self._groove_rect()
        span = max(0, groove.width() - 1)
        return groove.x() + QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), value, span
        )

    def _value_for_position(self, position: float) -> int:
        groove = self._groove_rect()
        span = max(1, groove.width() - 1)
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), int(position - groove.x()), span
        )

    def _groove_rect(self):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
