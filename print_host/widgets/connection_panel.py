from __future__ import annotations

import serial.tools.list_ports
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ConnectionPanel(QGroupBox):
    connect_clicked = Signal()
    disconnect_clicked = Signal()
    refresh_clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, title: str = "连接") -> None:
        super().__init__(title, parent)
        self._port = QComboBox()
        self._port.setMinimumWidth(180)
        self._baud = QSpinBox()
        self._baud.setRange(9600, 2_000_000)
        self._baud.setValue(115200)
        self._baud.setSingleStep(9600)
        self._btn_refresh = QPushButton("刷新串口")
        self._btn_connect = QPushButton("连接")
        self._btn_disconnect = QPushButton("断开")
        self._btn_disconnect.setEnabled(False)
        self._status = QLabel("未连接")

        self._btn_refresh.setProperty("role", "secondary")
        self._btn_connect.setProperty("role", "primary")
        self._btn_disconnect.setProperty("role", "secondary")
        self._status.setProperty("chip", True)

        self._btn_refresh.clicked.connect(self.refresh_clicked.emit)
        self._btn_connect.clicked.connect(self.connect_clicked.emit)
        self._btn_disconnect.clicked.connect(self.disconnect_clicked.emit)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._port, stretch=1)
        row.addWidget(self._btn_refresh)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow("串口", row)
        form.addRow("波特率", self._baud)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addWidget(self._btn_connect)
        btns.addWidget(self._btn_disconnect)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addLayout(form)
        lay.addLayout(btns)
        lay.addWidget(self._status)

        self.refresh_ports()

    def refresh_ports(self) -> None:
        cur = self._port.currentData()
        self._port.clear()
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            self._port.addItem("未发现串口设备", None)
            return
        for port in ports:
            desc = port.description or "未知设备"
            label = f"{port.device} - {desc}"
            self._port.addItem(label, port.device)
        if cur:
            idx = self._port.findData(cur)
            if idx >= 0:
                self._port.setCurrentIndex(idx)

    def selected_port(self) -> str | None:
        data = self._port.currentData()
        return str(data) if data else None

    def baudrate(self) -> int:
        return int(self._baud.value())

    def set_connected(self, ok: bool) -> None:
        self._btn_connect.setEnabled(not ok)
        self._btn_disconnect.setEnabled(ok)
        self._status.setText("已连接" if ok else "未连接")
