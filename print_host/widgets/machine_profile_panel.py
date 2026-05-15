from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..profiles import AxisProfile, HostProfileBundle, MachineProfile, ToolProfile


class MachineProfilePanel(QWidget):
    profiles_saved = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_joint_labels: list[QLabel] = []
        self._axis_widgets: list[dict[str, QWidget]] = []

        self._machine_name = QLineEdit()
        self._machine_name.setPlaceholderText("例如：六轴机械臂 FDM 打印平台")

        self._tool_name = QLineEdit()
        self._tool_name.setPlaceholderText("例如：0.4 mm 喷嘴挤出头")

        self._axis_table = QTableWidget(6, 10)
        self._axis_table.setHorizontalHeaderLabels(
            [
                "角度",
                "零位",
                "最小",
                "最大",
                "方向",
                "减速",
                "速度",
                "加速",
                "电流",
                "步距",
            ]
        )
        self._axis_table.setAlternatingRowColors(True)
        self._axis_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._axis_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._axis_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._axis_table.setMinimumHeight(286)
        self._axis_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._axis_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._axis_table.verticalHeader().setVisible(True)
        self._axis_table.verticalHeader().setDefaultSectionSize(40)
        header = self._axis_table.horizontalHeader()
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self._build_axis_table()

        self._base_x = self._make_spin(-1000.0, 1000.0, 1, " mm")
        self._base_y = self._make_spin(-1000.0, 1000.0, 1, " mm")
        self._base_z = self._make_spin(-1000.0, 1000.0, 1, " mm")
        self._plate_x = self._make_spin(10.0, 2000.0, 1, " mm")
        self._plate_y = self._make_spin(10.0, 2000.0, 1, " mm")
        self._plate_z = self._make_spin(10.0, 2000.0, 1, " mm")
        self._clearance = self._make_spin(0.0, 200.0, 1, " mm")
        self._wrist_clearance = self._make_spin(0.0, 200.0, 1, " mm")
        self._elbow_clearance = self._make_spin(0.0, 200.0, 1, " mm")
        self._tool_backoff = self._make_spin(0.0, 200.0, 1, " mm")
        self._wrist_backoff = self._make_spin(0.0, 300.0, 1, " mm")

        self._nozzle_diameter = self._make_spin(0.1, 4.0, 2, " mm")
        self._tcp_x = self._make_spin(-300.0, 300.0, 1, " mm")
        self._tcp_y = self._make_spin(-300.0, 300.0, 1, " mm")
        self._tcp_z = self._make_spin(-300.0, 300.0, 1, " mm")
        self._mount_angle = self._make_spin(-180.0, 180.0, 1, " °")
        self._safe_lift = self._make_spin(0.0, 100.0, 1, " mm")
        self._extrusion_max = self._make_spin(0.1, 50.0, 1, " mm/s")

        intro = QLabel("在这里维护机械臂轴参数、工作空间和喷嘴 TCP 定义，保存后会立即联动到数字孪生和离线预检。")
        intro.setWordWrap(True)
        intro.setProperty("muted", True)

        self._joint_note = QLabel("当前角度来自数字孪生实时状态，用于答辩演示时同步展示各轴姿态。")
        self._joint_note.setWordWrap(True)
        self._joint_note.setProperty("muted", True)

        self._note = QLabel(
            "目前关节限位仍属于名义参数，用于仿真、预检和上位机联调。后续拿到实体尺寸后，再补实测零位、限位角和末端 TCP 偏置。"
        )
        self._note.setWordWrap(True)
        self._note.setProperty("muted", True)

        btn_save = QPushButton("保存并同步到数字孪生")
        btn_save.setProperty("role", "primary")
        btn_reset = QPushButton("恢复默认名义参数")
        btn_reset.setProperty("role", "secondary")
        btn_save.clicked.connect(self._emit_profiles)
        btn_reset.clicked.connect(self._load_defaults)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_reset)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(intro)
        layout.addWidget(self._build_meta_group())
        layout.addWidget(self._build_geometry_group())
        layout.addWidget(self._build_tool_group())
        layout.addLayout(buttons)
        layout.addWidget(self._note)
        layout.addStretch(1)

    def _build_axis_table(self) -> None:
        for row in range(6):
            self._axis_table.setVerticalHeaderItem(row, QTableWidgetItem(f"J{row + 1}"))
            current_label = QLabel("--")
            current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            current_label.setProperty("chip", True)
            self._current_joint_labels.append(current_label)
            self._axis_table.setCellWidget(row, 0, current_label)

            home = self._make_spin(-360.0, 360.0, 1, " °")
            low = self._make_spin(-720.0, 720.0, 1, " °")
            high = self._make_spin(-720.0, 720.0, 1, " °")

            direction = QComboBox()
            direction.addItems(["CCW", "CW"])

            reduction = self._make_spin(1.0, 500.0, 2)
            max_speed = self._make_spin(1.0, 1000.0, 1, " °/s")
            accel = self._make_spin(1.0, 5000.0, 1, " °/s²")
            current = self._make_spin(0.1, 10.0, 2, " A")
            steps = self._make_spin(0.1, 10000.0, 2, " step/°")

            widgets = {
                "home": home,
                "low": low,
                "high": high,
                "dir": direction,
                "reduction": reduction,
                "speed": max_speed,
                "accel": accel,
                "current": current,
                "steps": steps,
            }
            self._axis_widgets.append(widgets)
            for col, key in enumerate(
                ("home", "low", "high", "dir", "reduction", "speed", "accel", "current", "steps"),
                start=1,
            ):
                self._axis_table.setCellWidget(row, col, widgets[key])

    @staticmethod
    def _make_spin(low: float, high: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(low, high)
        spin.setSingleStep(1.0 if decimals == 0 else 0.1)
        if suffix:
            spin.setSuffix(suffix)
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.PlusMinus)
        return spin

    @staticmethod
    def _wrap_row(*widgets: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return wrap

    def _build_meta_group(self) -> QGroupBox:
        box = QGroupBox("轴参数与驱动")
        layout = QVBoxLayout(box)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("机器名称", self._machine_name)
        form.addRow("六轴参数", self._axis_table)
        layout.addLayout(form)
        layout.addWidget(self._joint_note)
        return box

    def _build_geometry_group(self) -> QGroupBox:
        box = QGroupBox("工作空间与安全边界")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("基座原点 X / Y / Z", self._wrap_row(self._base_x, self._base_y, self._base_z))
        form.addRow("平台尺寸 X / Y / Z", self._wrap_row(self._plate_x, self._plate_y, self._plate_z))
        form.addRow(
            "地面 / 腕部 / 肘部净空",
            self._wrap_row(self._clearance, self._wrist_clearance, self._elbow_clearance),
        )
        form.addRow("工具回退 / 腕部回退", self._wrap_row(self._tool_backoff, self._wrist_backoff))
        return box

    def _build_tool_group(self) -> QGroupBox:
        box = QGroupBox("末端执行器与 TCP")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("工具名称", self._tool_name)
        form.addRow("喷嘴直径", self._nozzle_diameter)
        form.addRow("TCP 偏置 X / Y / Z", self._wrap_row(self._tcp_x, self._tcp_y, self._tcp_z))
        form.addRow("安装角 / 安全抬升", self._wrap_row(self._mount_angle, self._safe_lift))
        form.addRow("名义最大挤出速率", self._extrusion_max)
        return box

    def set_profiles(self, machine: MachineProfile, tool: ToolProfile) -> None:
        self._machine_name.setText(machine.name)
        self._tool_name.setText(tool.name)
        for row, axis in enumerate(machine.axes):
            widgets = self._axis_widgets[row]
            widgets["home"].setValue(axis.home_deg)
            widgets["low"].setValue(axis.min_deg)
            widgets["high"].setValue(axis.max_deg)
            widgets["dir"].setCurrentText(axis.positive_dir)
            widgets["reduction"].setValue(axis.reduction_ratio)
            widgets["speed"].setValue(axis.max_speed_deg_s)
            widgets["accel"].setValue(axis.accel_deg_s2)
            widgets["current"].setValue(axis.motor_current_a)
            widgets["steps"].setValue(axis.steps_per_deg)
        self._base_x.setValue(machine.base_origin_mm[0])
        self._base_y.setValue(machine.base_origin_mm[1])
        self._base_z.setValue(machine.base_origin_mm[2])
        self._plate_x.setValue(machine.build_plate_mm[0])
        self._plate_y.setValue(machine.build_plate_mm[1])
        self._plate_z.setValue(machine.build_plate_mm[2])
        self._clearance.setValue(machine.link_clearance_mm)
        self._wrist_clearance.setValue(machine.wrist_clearance_mm)
        self._elbow_clearance.setValue(machine.elbow_clearance_mm)
        self._tool_backoff.setValue(machine.tool_backoff_mm)
        self._wrist_backoff.setValue(machine.wrist_backoff_mm)
        self._nozzle_diameter.setValue(tool.nozzle_diameter_mm)
        self._tcp_x.setValue(tool.tcp_offset_mm[0])
        self._tcp_y.setValue(tool.tcp_offset_mm[1])
        self._tcp_z.setValue(tool.tcp_offset_mm[2])
        self._mount_angle.setValue(tool.nozzle_mount_angle_deg)
        self._safe_lift.setValue(tool.safe_lift_mm)
        self._extrusion_max.setValue(tool.extrusion_max_mm_s)

    def set_joint_angles(self, joints_deg: list[float] | None) -> None:
        for row, label in enumerate(self._current_joint_labels):
            if joints_deg is None or row >= len(joints_deg):
                label.setText("--")
            else:
                label.setText(f"{joints_deg[row]:.1f}°")

    def _collect_machine(self) -> MachineProfile:
        default = HostProfileBundle.default().machine
        axes = []
        for row, default_axis in enumerate(default.axes):
            widgets = self._axis_widgets[row]
            axes.append(
                AxisProfile(
                    name=default_axis.name,
                    home_deg=float(widgets["home"].value()),
                    min_deg=float(widgets["low"].value()),
                    max_deg=float(widgets["high"].value()),
                    positive_dir=str(widgets["dir"].currentText()),
                    reduction_ratio=float(widgets["reduction"].value()),
                    max_speed_deg_s=float(widgets["speed"].value()),
                    accel_deg_s2=float(widgets["accel"].value()),
                    motor_current_a=float(widgets["current"].value()),
                    steps_per_deg=float(widgets["steps"].value()),
                )
            )
        return MachineProfile(
            name=self._machine_name.text().strip() or default.name,
            axes=axes,
            dh_table=[list(row) for row in default.dh_table],
            base_origin_mm=[self._base_x.value(), self._base_y.value(), self._base_z.value()],
            build_plate_mm=[self._plate_x.value(), self._plate_y.value(), self._plate_z.value()],
            link_clearance_mm=float(self._clearance.value()),
            wrist_clearance_mm=float(self._wrist_clearance.value()),
            elbow_clearance_mm=float(self._elbow_clearance.value()),
            tool_backoff_mm=float(self._tool_backoff.value()),
            wrist_backoff_mm=float(self._wrist_backoff.value()),
            nozzle_lead_blend=default.nozzle_lead_blend,
            nozzle_side_blend=default.nozzle_side_blend,
            wrist_path_blend=default.wrist_path_blend,
            wrist_side_blend=default.wrist_side_blend,
            wrist_radial_blend=default.wrist_radial_blend,
            wrist_down_blend=default.wrist_down_blend,
        )

    def _collect_tool(self) -> ToolProfile:
        default = HostProfileBundle.default().tool
        return ToolProfile(
            name=self._tool_name.text().strip() or default.name,
            nozzle_diameter_mm=float(self._nozzle_diameter.value()),
            tcp_offset_mm=[self._tcp_x.value(), self._tcp_y.value(), self._tcp_z.value()],
            nozzle_mount_angle_deg=float(self._mount_angle.value()),
            safe_lift_mm=float(self._safe_lift.value()),
            extrusion_max_mm_s=float(self._extrusion_max.value()),
        )

    def _load_defaults(self) -> None:
        defaults = HostProfileBundle.default()
        self.set_profiles(defaults.machine, defaults.tool)

    def _emit_profiles(self) -> None:
        self.profiles_saved.emit(self._collect_machine(), self._collect_tool())
