from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class ExtruderPanel(QGroupBox):
    extrude = Signal(float, int)
    retract = Signal(float, int)

    def __init__(self, parent=None) -> None:
        super().__init__("挤出控制", parent)
        self._len = QDoubleSpinBox()
        self._len.setRange(0.1, 500.0)
        self._len.setDecimals(2)
        self._len.setValue(2.0)
        self._speed = QSpinBox()
        self._speed.setRange(60, 12000)
        self._speed.setValue(300)
        self._speed.setSingleStep(60)

        btn_extrude = QPushButton("正向挤出")
        btn_retract = QPushButton("回抽")
        btn_extrude.setProperty("role", "primary")
        btn_retract.setProperty("role", "secondary")
        btn_extrude.clicked.connect(
            lambda: self.extrude.emit(float(self._len.value()), int(self._speed.value()))
        )
        btn_retract.clicked.connect(
            lambda: self.retract.emit(float(self._len.value()), int(self._speed.value()))
        )

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow("长度 (mm)", self._len)
        form.addRow("速度 (mm/min)", self._speed)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(btn_extrude)
        row.addWidget(btn_retract)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addLayout(form)
        lay.addLayout(row)

    def set_presets(self, *, length_mm: float | None = None, speed_mm_min: int | None = None) -> None:
        if length_mm is not None:
            self._len.setValue(length_mm)
        if speed_mm_min is not None:
            self._speed.setValue(speed_mm_min)
