from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..gcode_motion import MotionSegment, parse_gcode_motion


class GcodeXyPreview(QWidget):
    """2D top-down preview of G-code XY moves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._segments: list[MotionSegment] = []
        self._pos_after_line: list[QPointF | None] = []
        self._exec_index: int | None = None
        self._title = "G-code XY 预览（俯视）"

    def clear(self) -> None:
        self._segments = []
        self._pos_after_line = []
        self._exec_index = None
        self.update()

    def load_gcode_lines(self, lines: list[str]) -> None:
        parsed = parse_gcode_motion(lines)
        self._segments = parsed.segments
        self._pos_after_line = [
            QPointF(pos[0], pos[1]) if pos is not None else None for pos in parsed.pos_after_line_xyz
        ]
        self._exec_index = None
        self.update()

    def set_exec_line_index(self, idx: int | None) -> None:
        self._exec_index = idx
        self.update()

    def _last_done_segment(self, exec_line: int) -> int:
        last = -1
        for seg_i, segment in enumerate(self._segments):
            if segment.line_index <= exec_line:
                last = seg_i
            else:
                break
        return last

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        width, height = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(0, 0, width, height, QColor("#f7fbff"))
        painter.setPen(QPen(QColor("#d7e8f6"), 1.0))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)

        painter.setPen(QPen(QColor("#36516b"), 1.0))
        painter.drawText(14, 24, self._title)
        if not self._segments:
            painter.setPen(QColor("#75889b"))
            painter.drawText(14, height // 2, "载入 G-code 后将显示 XY 轨迹")
            painter.end()
            return

        points = [QPointF(seg.start_xyz[0], seg.start_xyz[1]) for seg in self._segments]
        points.extend(QPointF(seg.end_xyz[0], seg.end_xyz[1]) for seg in self._segments)
        xs = [point.x() for point in points]
        ys = [point.y() for point in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max_x - min_x or 1.0
        span_y = max_y - min_y or 1.0
        margin = 28
        inner_w = max(1, width - 2 * margin)
        inner_h = max(1, height - 2 * margin)
        scale = min(inner_w / span_x, inner_h / span_y)
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        origin_x = width / 2.0 - scale * center_x
        origin_y = height / 2.0 + scale * center_y

        def to_screen(point: QPointF) -> QPointF:
            return QPointF(scale * point.x() + origin_x, -scale * point.y() + origin_y)

        plan_extrude = QPen(QColor("#ff9c66"), 2.2, Qt.PenStyle.SolidLine)
        plan_travel = QPen(QColor("#7ecbff"), 1.5, Qt.PenStyle.DashLine)
        done_extrude = QPen(QColor("#2ea6ff"), 2.4, Qt.PenStyle.SolidLine)
        done_travel = QPen(QColor("#57c7ff"), 1.6, Qt.PenStyle.DashLine)
        head_pen = QPen(QColor("#0f7ad8"), 8.0, Qt.PenStyle.SolidLine)

        painter.setPen(QPen(QColor("#6c8197"), 1.0))
        painter.drawText(width - 220, 24, "橙/蓝: 规划   深蓝: 已执行")

        done_seg = self._last_done_segment(self._exec_index) if self._exec_index is not None else -1
        for seg_i, segment in enumerate(self._segments):
            start = to_screen(QPointF(segment.start_xyz[0], segment.start_xyz[1]))
            end = to_screen(QPointF(segment.end_xyz[0], segment.end_xyz[1]))
            if segment.extrusion:
                painter.setPen(done_extrude if seg_i <= done_seg else plan_extrude)
            else:
                painter.setPen(done_travel if seg_i <= done_seg else plan_travel)
            painter.drawLine(start, end)

        if self._exec_index is not None and 0 <= self._exec_index < len(self._pos_after_line):
            head = self._pos_after_line[self._exec_index]
            if head is not None:
                painter.setPen(head_pen)
                painter.drawPoint(to_screen(head))

        painter.end()
