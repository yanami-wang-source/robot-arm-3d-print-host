from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..profiles import HostProfileBundle, MaterialProfile, ProcessProfile


class ProcessProfilePanel(QWidget):
    profiles_saved = Signal(object, object)
    slicer_settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._material_name = QLineEdit()
        self._material_name.setPlaceholderText("例如：PLA / PETG / 课程演示材料")

        self._nozzle_temp = QSpinBox()
        self._nozzle_temp.setRange(0, 450)
        self._nozzle_temp.setSuffix(" °C")

        self._bed_temp = QSpinBox()
        self._bed_temp.setRange(0, 200)
        self._bed_temp.setSuffix(" °C")

        self._chamber_temp = QSpinBox()
        self._chamber_temp.setRange(0, 120)
        self._chamber_temp.setSuffix(" °C")

        self._fan_pwm = QSpinBox()
        self._fan_pwm.setRange(0, 255)

        self._retract_len = self._make_dspin(0.0, 20.0, 2, " mm")
        self._retract_speed = QSpinBox()
        self._retract_speed.setRange(0, 20000)
        self._retract_speed.setSuffix(" mm/min")

        self._material_notes = QTextEdit()
        self._material_notes.setMaximumHeight(88)
        self._material_notes.setPlaceholderText("可记录材料特性、烘料要求、展示时的注意事项。")

        self._process_name = QLineEdit()
        self._process_name.setPlaceholderText("例如：演示版高速打印 / 稳定版参数")

        self._layer_height = self._make_dspin(0.05, 3.0, 2, " mm")
        self._line_width = self._make_dspin(0.1, 5.0, 2, " mm")
        self._print_speed = self._make_dspin(1.0, 500.0, 1, " mm/s")
        self._travel_speed = self._make_dspin(1.0, 1000.0, 1, " mm/s")

        self._flow_override = QSpinBox()
        self._flow_override.setRange(10, 300)
        self._flow_override.setSuffix(" %")

        self._speed_override = QSpinBox()
        self._speed_override.setRange(10, 300)
        self._speed_override.setSuffix(" %")

        self._pressure_advance = self._make_dspin(0.0, 2.0, 3)
        self._extrusion_multiplier = self._make_dspin(0.1, 3.0, 2)
        self._z_hop = self._make_dspin(0.0, 10.0, 2, " mm")

        self._nozzle_dwell = QSpinBox()
        self._nozzle_dwell.setRange(0, 60000)
        self._nozzle_dwell.setSuffix(" ms")

        self._process_notes = QTextEdit()
        self._process_notes.setMaximumHeight(88)
        self._process_notes.setPlaceholderText("可记录对应展示轨迹、答辩版本说明或待实测项。")

        intro = QLabel("这里负责 3D 打印工艺层面的参数管理，既服务离线预览，也服务后续真实设备接入。")
        intro.setWordWrap(True)
        intro.setProperty("muted", True)

        self._hint = QLabel(
            "建议至少保留两套参数：一套用于离线演示和数字孪生展示，另一套标记为“待实机标定”，便于答辩时说明工程完整度。"
        )
        self._hint.setWordWrap(True)
        self._hint.setProperty("muted", True)

        btn_save = QPushButton("保存材料 / 工艺参数")
        btn_save.setProperty("role", "primary")
        btn_defaults = QPushButton("恢复默认工艺")
        btn_defaults.setProperty("role", "secondary")
        btn_slicer = QPushButton("切片器路径设置")
        btn_slicer.setProperty("role", "secondary")
        btn_save.clicked.connect(self._emit_profiles)
        btn_defaults.clicked.connect(self._load_defaults)
        btn_slicer.clicked.connect(self.slicer_settings_requested.emit)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_defaults)
        buttons.addWidget(btn_slicer)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(intro)
        layout.addWidget(self._build_material_group())
        layout.addWidget(self._build_process_group())
        layout.addLayout(buttons)
        layout.addWidget(self._hint)
        layout.addStretch(1)

    @staticmethod
    def _make_dspin(low: float, high: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(low, high)
        spin.setSingleStep(0.1)
        if suffix:
            spin.setSuffix(suffix)
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

    def _build_material_group(self) -> QGroupBox:
        box = QGroupBox("材料参数")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("材料名称", self._material_name)
        form.addRow("喷嘴 / 热床 / 腔体温度", self._wrap_row(self._nozzle_temp, self._bed_temp, self._chamber_temp))
        form.addRow("风扇 PWM", self._fan_pwm)
        form.addRow("回抽长度 / 回抽速度", self._wrap_row(self._retract_len, self._retract_speed))
        form.addRow("材料说明", self._material_notes)
        return box

    def _build_process_group(self) -> QGroupBox:
        box = QGroupBox("工艺参数")
        form = QFormLayout(box)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.addRow("工艺名称", self._process_name)
        form.addRow("层高 / 线宽", self._wrap_row(self._layer_height, self._line_width))
        form.addRow("打印 / 空走速度", self._wrap_row(self._print_speed, self._travel_speed))
        form.addRow("流量 / 速度倍率", self._wrap_row(self._flow_override, self._speed_override))
        form.addRow("Pressure Advance", self._pressure_advance)
        form.addRow("挤出倍率 / Z-hop", self._wrap_row(self._extrusion_multiplier, self._z_hop))
        form.addRow("喷嘴驻留", self._nozzle_dwell)
        form.addRow("工艺说明", self._process_notes)
        return box

    def set_profiles(self, material: MaterialProfile, process: ProcessProfile) -> None:
        self._material_name.setText(material.name)
        self._nozzle_temp.setValue(material.nozzle_temp_c)
        self._bed_temp.setValue(material.bed_temp_c)
        self._chamber_temp.setValue(material.chamber_temp_c)
        self._fan_pwm.setValue(material.fan_pwm)
        self._retract_len.setValue(material.retract_len_mm)
        self._retract_speed.setValue(material.retract_speed_mm_min)
        self._material_notes.setPlainText(material.notes)

        self._process_name.setText(process.name)
        self._layer_height.setValue(process.layer_height_mm)
        self._line_width.setValue(process.line_width_mm)
        self._print_speed.setValue(process.print_speed_mm_s)
        self._travel_speed.setValue(process.travel_speed_mm_s)
        self._flow_override.setValue(process.flow_override_pct)
        self._speed_override.setValue(process.speed_override_pct)
        self._pressure_advance.setValue(process.pressure_advance)
        self._extrusion_multiplier.setValue(process.extrusion_multiplier)
        self._z_hop.setValue(process.z_hop_mm)
        self._nozzle_dwell.setValue(process.nozzle_dwell_ms)
        self._process_notes.setPlainText(process.notes)

    def apply_to_live_panels(
        self,
        target_hotend: QSpinBox,
        target_bed: QSpinBox,
        target_fan: QSpinBox,
    ) -> None:
        target_hotend.setValue(self._nozzle_temp.value())
        target_bed.setValue(self._bed_temp.value())
        target_fan.setValue(self._fan_pwm.value())

    def _collect_material(self) -> MaterialProfile:
        default = HostProfileBundle.default().material
        return MaterialProfile(
            name=self._material_name.text().strip() or default.name,
            nozzle_temp_c=int(self._nozzle_temp.value()),
            bed_temp_c=int(self._bed_temp.value()),
            chamber_temp_c=int(self._chamber_temp.value()),
            fan_pwm=int(self._fan_pwm.value()),
            retract_len_mm=float(self._retract_len.value()),
            retract_speed_mm_min=int(self._retract_speed.value()),
            notes=self._material_notes.toPlainText().strip() or default.notes,
        )

    def _collect_process(self) -> ProcessProfile:
        default = HostProfileBundle.default().process
        return ProcessProfile(
            name=self._process_name.text().strip() or default.name,
            layer_height_mm=float(self._layer_height.value()),
            line_width_mm=float(self._line_width.value()),
            print_speed_mm_s=float(self._print_speed.value()),
            travel_speed_mm_s=float(self._travel_speed.value()),
            flow_override_pct=int(self._flow_override.value()),
            speed_override_pct=int(self._speed_override.value()),
            pressure_advance=float(self._pressure_advance.value()),
            extrusion_multiplier=float(self._extrusion_multiplier.value()),
            z_hop_mm=float(self._z_hop.value()),
            nozzle_dwell_ms=int(self._nozzle_dwell.value()),
            notes=self._process_notes.toPlainText().strip() or default.notes,
        )

    def _load_defaults(self) -> None:
        defaults = HostProfileBundle.default()
        self.set_profiles(defaults.material, defaults.process)

    def _emit_profiles(self) -> None:
        self.profiles_saved.emit(self._collect_material(), self._collect_process())
