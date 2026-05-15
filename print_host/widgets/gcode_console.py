from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class GcodeConsole(QGroupBox):
    send_line = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("G-code 终端", parent)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMaximumBlockCount(5000)
        self._out.setPlaceholderText("串口日志、离线回放信息和名义电机输出会显示在这里。")
        self._in = QLineEdit()
        self._in.setPlaceholderText("输入指令后回车，例如 M115 或 G28")
        self._in.returnPressed.connect(self._emit_send)

        btn_send = QPushButton("发送")
        btn_send.setProperty("role", "primary")
        btn_send.clicked.connect(self._emit_send)
        btn_clear = QPushButton("清空显示")
        btn_clear.setProperty("role", "secondary")
        btn_clear.clicked.connect(self._out.clear)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._in, stretch=1)
        row.addWidget(btn_send)
        row.addWidget(btn_clear)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(self._out, stretch=1)
        lay.addLayout(row)

    def _emit_send(self) -> None:
        text = self._in.text().strip()
        if not text:
            return
        self._in.clear()
        self.append_line(f">> {text}")
        self.send_line.emit(text)

    def append_line(self, text: str) -> None:
        self._out.appendPlainText(text)
