from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class JogPanel(QGroupBox):
    jog = Signal(str, float)
    home = Signal(str)
    motors_off = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("手动移动 (Jog)", parent)
        self._step_group = QButtonGroup(self)
        steps = [0.1, 1.0, 10.0]
        step_row = QHBoxLayout()
        step_row.setSpacing(10)
        step_row.addWidget(QLabel("步长 (mm):"))
        for step in steps:
            button = QRadioButton(str(step))
            button.setProperty("step_mm", step)
            self._step_group.addButton(button)
            step_row.addWidget(button)
        self._step_group.buttons()[1].setChecked(True)
        step_row.addStretch(1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(self._mk_jog("Y+", "Y", +1), 0, 1)
        grid.addWidget(self._mk_jog("X-", "X", -1), 1, 0)
        grid.addWidget(self._mk_home_xy(), 1, 1)
        grid.addWidget(self._mk_jog("X+", "X", +1), 1, 2)
        grid.addWidget(self._mk_jog("Y-", "Y", -1), 2, 1)

        z_col = QVBoxLayout()
        z_col.setSpacing(8)
        z_col.addWidget(self._mk_jog("Z+", "Z", +1))
        z_col.addWidget(self._mk_jog("Z-", "Z", -1))
        z_wrap = QWidget()
        z_wrap.setLayout(z_col)
        grid.addWidget(z_wrap, 0, 3, 3, 1)

        home_row = QHBoxLayout()
        home_row.setSpacing(8)
        for text, axes in [("回零 XYZ", "XYZ"), ("回零 Z", "Z")]:
            button = QPushButton(text)
            button.setProperty("role", "secondary")
            button.clicked.connect(lambda _, a=axes: self.home.emit(a))
            home_row.addWidget(button)
        motors_off = QPushButton("释放电机 M84")
        motors_off.setProperty("role", "secondary")
        motors_off.clicked.connect(self.motors_off.emit)
        home_row.addWidget(motors_off)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addLayout(step_row)
        lay.addLayout(grid)
        lay.addLayout(home_row)

    def _step_mm(self) -> float:
        for button in self._step_group.buttons():
            if button.isChecked():
                return float(button.property("step_mm"))
        return 1.0

    def _mk_jog(self, title: str, axis: str, direction: int) -> QPushButton:
        button = QPushButton(title)
        button.setProperty("jog", True)
        button.clicked.connect(lambda: self.jog.emit(axis, direction * self._step_mm()))
        return button

    def _mk_home_xy(self) -> QPushButton:
        button = QPushButton("回零 XY")
        button.setProperty("role", "primary")
        button.setProperty("jog", True)
        button.clicked.connect(lambda: self.home.emit("XY"))
        return button
