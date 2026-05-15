from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._run_labels = self._build_label_map(
            (
                "Marlin 状态",
                "机械臂状态",
                "运行模式",
                "当前任务",
                "进度",
                "预检结果",
            )
        )
        self._job_labels = self._build_label_map(
            (
                "材料",
                "工艺",
                "喷嘴 / 热床",
                "风扇",
                "打印 / 空走速度",
                "流量 / 速度倍率",
            )
        )
        self._motion_labels = self._build_label_map(
            (
                "当前段类型",
                "执行行",
                "进给速度",
                "TCP",
                "关节 1-3",
                "关节 4-6",
            )
        )
        self._risk_labels = self._build_label_map(
            (
                "名义限位",
                "仿真来源",
                "平台尺寸",
                "基座原点",
                "待标定项",
                "建议动作",
            )
        )
        self._events = QPlainTextEdit()
        self._events.setReadOnly(True)
        self._events.setMinimumHeight(170)
        self._events.setPlaceholderText("运行事件、预警和答辩提示会显示在这里。")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(self._build_top_grid())
        layout.addWidget(self._build_events_box())

    def _build_label_map(self, titles: tuple[str, ...]) -> dict[str, QLabel]:
        labels: dict[str, QLabel] = {}
        for title in titles:
            label = QLabel("-")
            label.setWordWrap(True)
            label.setProperty("chip", True)
            labels[title] = label
        return labels

    def _build_group(self, title: str, labels: dict[str, QLabel]) -> QGroupBox:
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        for row, (key, value) in enumerate(labels.items()):
            name = QLabel(key)
            name.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            name.setProperty("muted", True)
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
        grid.setColumnStretch(1, 1)
        return box

    def _build_top_grid(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        right = QVBoxLayout()
        right.setSpacing(12)
        left.addWidget(self._build_group("运行概览", self._run_labels))
        left.addWidget(self._build_group("材料与工艺摘要", self._job_labels))
        right.addWidget(self._build_group("运动与轨迹", self._motion_labels))
        right.addWidget(self._build_group("风险与完善项", self._risk_labels))
        layout.addLayout(left, 1)
        layout.addLayout(right, 1)
        return layout

    def _build_events_box(self) -> QGroupBox:
        box = QGroupBox("最近事件 / 答辩提示")
        layout = QVBoxLayout(box)
        layout.addWidget(self._events)
        return box

    def update_snapshot(self, snapshot: dict[str, object]) -> None:
        run = self._run_labels
        run["Marlin 状态"].setText(str(snapshot.get("marlin_status", "-")))
        run["机械臂状态"].setText(str(snapshot.get("robot_status", "-")))
        run["运行模式"].setText(str(snapshot.get("mode", "-")))
        run["当前任务"].setText(str(snapshot.get("job_name", "-")))
        run["进度"].setText(str(snapshot.get("progress", "-")))
        self._set_highlight(
            run["预检结果"],
            str(snapshot.get("precheck", "-")),
            snapshot.get("precheck_level", "neutral"),
        )

        job = self._job_labels
        job["材料"].setText(str(snapshot.get("material_name", "-")))
        job["工艺"].setText(str(snapshot.get("process_name", "-")))
        job["喷嘴 / 热床"].setText(str(snapshot.get("temperature_targets", "-")))
        job["风扇"].setText(str(snapshot.get("fan", "-")))
        job["打印 / 空走速度"].setText(str(snapshot.get("speed_pair", "-")))
        job["流量 / 速度倍率"].setText(str(snapshot.get("override_pair", "-")))

        motion = self._motion_labels
        motion["当前段类型"].setText(str(snapshot.get("segment_type", "-")))
        motion["执行行"].setText(str(snapshot.get("line_index", "-")))
        motion["进给速度"].setText(str(snapshot.get("feed", "-")))
        motion["TCP"].setText(str(snapshot.get("tcp", "-")))
        motion["关节 1-3"].setText(str(snapshot.get("joints_a", "-")))
        motion["关节 4-6"].setText(str(snapshot.get("joints_b", "-")))

        risk = self._risk_labels
        self._set_highlight(
            risk["名义限位"],
            str(snapshot.get("limit_summary", "-")),
            snapshot.get("limit_level", "neutral"),
        )
        risk["仿真来源"].setText(str(snapshot.get("source", "-")))
        risk["平台尺寸"].setText(str(snapshot.get("build_plate", "-")))
        risk["基座原点"].setText(str(snapshot.get("base_origin", "-")))
        risk["待标定项"].setText(str(snapshot.get("calibration_todo", "-")))
        risk["建议动作"].setText(str(snapshot.get("next_action", "-")))

    def set_recent_events(self, items: list[str]) -> None:
        self._events.setPlainText("\n".join(items[-12:]))

    @staticmethod
    def _set_highlight(label: QLabel, text: str, level: object) -> None:
        color = QColor("#2f4356")
        background = "#f3fbff"
        border = "#d2e8f7"
        if level == "good":
            color = QColor("#13795b")
            background = "#e9fff3"
            border = "#bfe9d2"
        elif level == "warn":
            color = QColor("#9a5b00")
            background = "#fff6e6"
            border = "#f3ddb3"
        elif level == "bad":
            color = QColor("#b42318")
            background = "#fff1f1"
            border = "#f3c9c6"
        label.setText(text)
        label.setStyleSheet(
            f"color: rgb({color.red()}, {color.green()}, {color.blue()});"
            f"background: {background}; border: 1px solid {border}; border-radius: 8px; padding: 6px 10px;"
        )
