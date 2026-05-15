from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PrintJobPanel(QGroupBox):
    open_file = Signal(str)
    request_external_slice = Signal()
    start_print = Signal()
    pause_print = Signal()
    resume_print = Signal()
    cancel_print = Signal()
    emergency_stop = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("打印任务", parent)
        self._path = QLabel("未选择文件")
        self._path.setWordWrap(True)
        self._path.setProperty("chip", True)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFormat("%p%")

        self._btn_open = QPushButton("打开 G-code")
        self._btn_slice = QPushButton("导入 STL 并外部切片")
        self._btn_start = QPushButton("开始")
        self._btn_pause = QPushButton("暂停")
        self._btn_resume = QPushButton("继续")
        self._btn_cancel = QPushButton("停止")
        self._btn_estop = QPushButton("急停 M112")

        self._btn_open.setProperty("role", "secondary")
        self._btn_slice.setProperty("role", "secondary")
        self._btn_start.setProperty("role", "primary")
        self._btn_pause.setProperty("role", "secondary")
        self._btn_resume.setProperty("role", "secondary")
        self._btn_cancel.setProperty("role", "secondary")
        self._btn_estop.setProperty("role", "danger")

        self._btn_open.clicked.connect(self._pick_file)
        self._btn_slice.clicked.connect(self.request_external_slice.emit)
        self._btn_start.clicked.connect(self.start_print.emit)
        self._btn_pause.clicked.connect(self.pause_print.emit)
        self._btn_resume.clicked.connect(self.resume_print.emit)
        self._btn_cancel.clicked.connect(self.cancel_print.emit)
        self._btn_estop.clicked.connect(self.emergency_stop.emit)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(self._btn_open, 0, 0)
        grid.addWidget(self._btn_slice, 0, 1)
        grid.addWidget(self._btn_start, 0, 2)
        grid.addWidget(self._btn_pause, 0, 3)
        grid.addWidget(self._btn_resume, 1, 2)
        grid.addWidget(self._btn_cancel, 1, 3)
        grid.addWidget(self._btn_estop, 1, 0, 1, 2)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(self._path)
        lay.addWidget(self._bar)
        lay.addLayout(grid)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 G-code",
            str(Path.home()),
            "G-code (*.gcode *.gco *.nc *.txt);;所有文件 (*.*)",
        )
        if path:
            self._path.setText(path)
            self.open_file.emit(path)

    def set_progress(self, pct: int) -> None:
        self._bar.setValue(max(0, min(100, pct)))

    def set_slice_busy(self, busy: bool) -> None:
        self._btn_slice.setEnabled(not busy)

    def current_file(self) -> str | None:
        text = self._path.text()
        if not text or text == "未选择文件":
            return None
        return text

    def set_gcode_path(self, path: str) -> None:
        self._path.setText(path)
