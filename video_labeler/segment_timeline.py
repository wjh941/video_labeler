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
        if segment is None or segment[1] <= segment[0]:
            return
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0EA5A4"))
        left = self._position_for_value(segment[0])
        right = self._position_for_value(segment[1])
        painter.drawRoundedRect(
            QRectF(left, self.height() / 2 - 3, max(4, right - left), 6), 3, 3
        )

    def mousePressEvent(self, event) -> None:
        segment = self.segment_range()
        if event.button() == Qt.MouseButton.LeftButton and segment is not None:
            position = event.position().x()
            start = self._position_for_value(segment[0])
            end = self._position_for_value(segment[1])
            if abs(position - start) <= 10:
                self._dragged_edge = "start"
                event.accept()
                return
            if abs(position - end) <= 10:
                self._dragged_edge = "end"
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
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragged_edge is not None:
            self._dragged_edge = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
