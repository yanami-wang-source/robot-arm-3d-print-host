from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class TemperaturePanel(QGroupBox):
    set_hotend = Signal(int)
    set_bed = Signal(int)
    fan_on = Signal(int)
    fan_off = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("温度 / 风扇", parent)
        self._h_cur = QLabel("--")
        self._h_tgt = QLabel("--")
        self._b_cur = QLabel("--")
        self._b_tgt = QLabel("--")
        for label in (self._h_cur, self._h_tgt, self._b_cur, self._b_tgt):
            label.setProperty("chip", True)

        self._h_set = QSpinBox()
        self._h_set.setRange(0, 350)
        self._h_set.setValue(200)
        self._b_set = QSpinBox()
        self._b_set.setRange(0, 130)
        self._b_set.setValue(60)
        self._fan = QSpinBox()
        self._fan.setRange(0, 255)
        self._fan.setValue(180)

        btn_h = QPushButton("设置喷嘴")
        btn_b = QPushButton("设置热床")
        btn_f_on = QPushButton("风扇开启")
        btn_f_off = QPushButton("风扇关闭")
        btn_h.setProperty("role", "primary")
        btn_b.setProperty("role", "secondary")
        btn_f_on.setProperty("role", "secondary")
        btn_f_off.setProperty("role", "secondary")
        btn_h.clicked.connect(lambda: self.set_hotend.emit(self._h_set.value()))
        btn_b.clicked.connect(lambda: self.set_bed.emit(self._b_set.value()))
        btn_f_on.clicked.connect(lambda: self.fan_on.emit(self._fan.value()))
        btn_f_off.clicked.connect(self.fan_off.emit)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow("喷嘴 当前 / 目标", self._row(self._h_cur, self._h_tgt))
        form.addRow("热床 当前 / 目标", self._row(self._b_cur, self._b_tgt))
        form.addRow("喷嘴目标 (°C)", self._h_set)
        form.addRow("热床目标 (°C)", self._b_set)
        form.addRow("风扇 PWM", self._fan)

        row_h = QHBoxLayout()
        row_h.setSpacing(8)
        row_h.addWidget(btn_h)
        row_h.addWidget(btn_b)
        row_f = QHBoxLayout()
        row_f.setSpacing(8)
        row_f.addWidget(btn_f_on)
        row_f.addWidget(btn_f_off)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addLayout(form)
        lay.addLayout(row_h)
        lay.addLayout(row_f)

    @staticmethod
    def _row(a: QLabel, b: QLabel) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(a)
        h.addWidget(QLabel("/"))
        h.addWidget(b)
        h.addStretch(1)
        return w

    def update_display(
        self,
        hot_cur: float | None,
        hot_tgt: float | None,
        bed_cur: float | None,
        bed_tgt: float | None,
    ) -> None:
        def fmt(value: float | None) -> str:
            return f"{value:.1f}" if value is not None else "--"

        self._h_cur.setText(fmt(hot_cur))
        self._h_tgt.setText(fmt(hot_tgt))
        self._b_cur.setText(fmt(bed_cur))
        self._b_tgt.setText(fmt(bed_tgt))

    def set_presets(self, *, hotend: int | None = None, bed: int | None = None, fan: int | None = None) -> None:
        if hotend is not None:
            self._h_set.setValue(hotend)
        if bed is not None:
            self._b_set.setValue(bed)
        if fan is not None:
            self._fan.setValue(fan)
