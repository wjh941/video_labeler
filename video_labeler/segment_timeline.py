"""Timeline slider with visual segment edges that users can drag."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class SegmentTimelineSlider(QSlider):
    segment_range_changed = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._segment_start: int | None = None
        self._segment_end: int | None = None
        self._dragged_edge: str | None = None
        self._segment_ranges: list[tuple[int, int]] = []
        self.setMouseTracking(True)
        self.setToolTip("拖动片段左右边缘调整起止时间")

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

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        segment = self.segment_range()
        if (segment is None or segment[1] <= segment[0]) and not self._segment_ranges:
            return
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        groove = self._groove_rect()
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

    def mousePressEvent(self, event) -> None:
        segment = self.segment_range()
        if event.button() == Qt.MouseButton.LeftButton and segment is not None:
            self._dragged_edge = self._edge_at_position(event.position().x())
            if self._dragged_edge is not None:
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragged_edge is not None:
            self.adjust_segment_edge(
                self._dragged_edge, self._value_for_position(event.position().x())
            )
            event.accept()
            return
        edge = self._edge_at_position(event.position().x())
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
