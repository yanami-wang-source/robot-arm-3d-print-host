from __future__ import annotations

from collections import deque

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class HistoryPlotWidget(QWidget):
    def __init__(self, title: str, series_names: list[tuple[str, QColor]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._series_names = series_names
        self._data = {name: deque(maxlen=180) for name, _ in series_names}
        self.setMinimumHeight(180)

    def append(self, **values: float | None) -> None:
        for name, _color in self._series_names:
            value = values.get(name)
            self._data[name].append(None if value is None else float(value))
        self.update()

    def clear(self) -> None:
        for series in self._data.values():
            series.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f7fbff"))

        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#d7e8f6"), 1.0))
        painter.drawRoundedRect(outer, 8, 8)

        painter.setPen(QPen(QColor("#26415b"), 1.0))
        painter.drawText(14, 24, self._title)

        rect = QRectF(16, 36, max(80, self.width() - 32), max(60, self.height() - 56))
        painter.setPen(QPen(QColor("#dce9f4"), 1.0))
        painter.drawRoundedRect(rect, 6, 6)

        values = [value for series in self._data.values() for value in series if value is not None]
        if not values:
            painter.setPen(QColor("#71859a"))
            painter.drawText(int(rect.left() + 12), int(rect.center().y()), "等待运行数据...")
            painter.end()
            return

        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-6:
            max_v = min_v + 1.0

        for line_idx in range(1, 4):
            y = rect.top() + rect.height() * line_idx / 4.0
            painter.setPen(QPen(QColor("#edf4fa"), 1.0))
            painter.drawLine(rect.left() + 6, y, rect.right() - 6, y)

        for name, color in self._series_names:
            series = list(self._data[name])
            if len(series) < 2:
                continue
            painter.setPen(QPen(color, 2.0))
            prev_point = None
            for idx, value in enumerate(series):
                if value is None:
                    prev_point = None
                    continue
                x = rect.left() + rect.width() * idx / max(1, len(series) - 1)
                y = rect.bottom() - rect.height() * (value - min_v) / (max_v - min_v)
                point = (x, y)
                if prev_point is not None:
                    painter.drawLine(prev_point[0], prev_point[1], point[0], point[1])
                prev_point = point

        legend_x = rect.left() + 6
        for idx, (name, color) in enumerate(self._series_names):
            line_y = rect.top() + 14 + idx * 18
            painter.setPen(QPen(color, 2.4))
            painter.drawLine(legend_x, line_y, legend_x + 18, line_y)
            painter.setPen(QColor("#40586f"))
            painter.drawText(int(legend_x + 24), int(line_y + 4), name)
        painter.end()


class DiagnosticsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._temp_plot = HistoryPlotWidget(
            "温度趋势",
            [("hotend", QColor("#ff8f5a")), ("bed", QColor("#53b7ff"))],
        )
        self._motion_plot = HistoryPlotWidget(
            "运动趋势",
            [("feed", QColor("#2ea6ff")), ("progress", QColor("#8ed2ff"))],
        )
        self._summary_labels = {
            "Marlin": QLabel("未连接"),
            "机械臂": QLabel("未连接"),
            "当前段": QLabel("-"),
            "进给": QLabel("-"),
            "TCP": QLabel("-"),
            "关节": QLabel("-"),
        }
        for label in self._summary_labels.values():
            label.setWordWrap(True)
            label.setProperty("chip", True)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(4000)
        self._log.setPlaceholderText("诊断日志、状态切换和提示信息会显示在这里。")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._temp_plot, 1)
        top.addWidget(self._motion_plot, 1)
        layout.addLayout(top)
        layout.addWidget(self._build_summary_box())
        layout.addWidget(self._build_log_box(), 1)

    def _build_summary_box(self) -> QGroupBox:
        box = QGroupBox("诊断摘要")
        form = QFormLayout(box)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        for key, label in self._summary_labels.items():
            form.addRow(key, label)
        return box

    def _build_log_box(self) -> QGroupBox:
        box = QGroupBox("运行日志 / 预警")
        layout = QVBoxLayout(box)
        layout.addWidget(self._log)
        return box

    def append_temperature(self, hotend: float | None, bed: float | None) -> None:
        self._temp_plot.append(hotend=hotend, bed=bed)

    def append_motion(
        self,
        *,
        progress_pct: float | None,
        feed: float | None,
        segment_type: str,
        tcp_text: str,
        joints_text: str,
    ) -> None:
        self._motion_plot.append(feed=feed, progress=progress_pct)
        self._summary_labels["当前段"].setText(segment_type)
        self._summary_labels["进给"].setText("-" if feed is None else f"{feed:.0f} mm/min")
        self._summary_labels["TCP"].setText(tcp_text)
        self._summary_labels["关节"].setText(joints_text)

    def set_connection_states(self, marlin_ok: bool, robot_ok: bool) -> None:
        self._summary_labels["Marlin"].setText("已连接" if marlin_ok else "未连接")
        self._summary_labels["机械臂"].setText("已连接" if robot_ok else "未连接")

    def add_log(self, text: str) -> None:
        self._log.appendPlainText(text)
