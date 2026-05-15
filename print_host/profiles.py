from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _app_root() -> Path:
    return Path(__file__).resolve().parent.parent / "app"


def profiles_path() -> Path:
    return _app_root() / "host_profiles.json"


@dataclass
class AxisProfile:
    name: str
    home_deg: float
    min_deg: float
    max_deg: float
    positive_dir: str
    reduction_ratio: float
    max_speed_deg_s: float
    accel_deg_s2: float
    motor_current_a: float
    steps_per_deg: float


@dataclass
class MachineProfile:
    name: str = "课程设计机械臂平台"
    axes: list[AxisProfile] = field(default_factory=list)
    dh_table: list[list[float]] = field(default_factory=list)
    base_origin_mm: list[float] = field(default_factory=lambda: [-170.0, -120.0, 0.0])
    build_plate_mm: list[float] = field(default_factory=lambda: [220.0, 220.0, 180.0])
    link_clearance_mm: float = 18.0
    wrist_clearance_mm: float = 42.0
    elbow_clearance_mm: float = 58.0
    tool_backoff_mm: float = 24.0
    wrist_backoff_mm: float = 76.0
    nozzle_lead_blend: float = 0.14
    nozzle_side_blend: float = 0.05
    wrist_path_blend: float = 0.48
    wrist_side_blend: float = 0.22
    wrist_radial_blend: float = 0.12
    wrist_down_blend: float = 0.82


@dataclass
class ToolProfile:
    name: str = "FDM 喷头"
    nozzle_diameter_mm: float = 0.4
    tcp_offset_mm: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    nozzle_mount_angle_deg: float = 90.0
    safe_lift_mm: float = 12.0
    extrusion_max_mm_s: float = 8.0


@dataclass
class MaterialProfile:
    name: str = "PLA 演示材料"
    nozzle_temp_c: int = 205
    bed_temp_c: int = 60
    chamber_temp_c: int = 25
    fan_pwm: int = 180
    retract_len_mm: float = 1.2
    retract_speed_mm_min: int = 1800
    notes: str = "用于演示和离线回放。"


@dataclass
class ProcessProfile:
    name: str = "机械臂空间打印演示"
    layer_height_mm: float = 0.35
    line_width_mm: float = 0.48
    print_speed_mm_s: float = 28.0
    travel_speed_mm_s: float = 65.0
    flow_override_pct: int = 100
    speed_override_pct: int = 100
    pressure_advance: float = 0.0
    extrusion_multiplier: float = 1.0
    z_hop_mm: float = 0.8
    nozzle_dwell_ms: int = 0
    notes: str = "先用于答辩演示，真实打印前需按实际材料再次标定。"


@dataclass
class HostProfileBundle:
    machine: MachineProfile = field(default_factory=MachineProfile)
    tool: ToolProfile = field(default_factory=ToolProfile)
    material: MaterialProfile = field(default_factory=MaterialProfile)
    process: ProcessProfile = field(default_factory=ProcessProfile)

    @classmethod
    def default(cls) -> HostProfileBundle:
        return cls(
            machine=MachineProfile(
                axes=[
                    AxisProfile("J1", 90.0, -170.0, 170.0, "CCW", 50.0, 45.0, 120.0, 1.60, 50.0 * 3200.0 / 360.0),
                    AxisProfile("J2", 90.0, -90.0, 120.0, "CW", 50.89, 42.0, 120.0, 1.80, 50.89 * 3200.0 / 360.0),
                    AxisProfile("J3", -90.0, -135.0, 135.0, "CW", 50.89, 42.0, 120.0, 1.80, 50.89 * 3200.0 / 360.0),
                    AxisProfile("J4", 0.0, -180.0, 180.0, "CW", 51.0, 90.0, 180.0, 1.20, 51.0 * 3200.0 / 360.0),
                    AxisProfile("J5", 90.0, -120.0, 120.0, "CCW", 26.85, 90.0, 180.0, 1.00, 26.85 * 3200.0 / 360.0),
                    AxisProfile("J6", 0.0, -360.0, 360.0, "CW", 51.0, 120.0, 240.0, 0.80, 51.0 * 3200.0 / 360.0),
                ],
                dh_table=[
                    [0.0, 90.0, 155.0, 0.0],
                    [200.0, 0.0, 0.0, 0.0],
                    [40.0, 90.0, 40.0, 0.0],
                    [0.0, -90.0, 180.0, 0.0],
                    [0.0, 90.0, 0.0, 0.0],
                    [0.0, 0.0, 110.0, 0.0],
                ],
            ),
            tool=ToolProfile(),
            material=MaterialProfile(),
            process=ProcessProfile(),
        )

    @classmethod
    def load(cls) -> HostProfileBundle:
        path = profiles_path()
        if not path.is_file():
            bundle = cls.default()
            bundle.save()
            return bundle
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bundle = cls.default()
            bundle.save()
            return bundle
        default = cls.default()
        machine_raw = raw.get("machine", {})
        tool_raw = raw.get("tool", {})
        material_raw = raw.get("material", {})
        process_raw = raw.get("process", {})
        axes_raw = machine_raw.get("axes", [])
        axes: list[AxisProfile] = []
        for idx, default_axis in enumerate(default.machine.axes):
            axis_data = axes_raw[idx] if idx < len(axes_raw) and isinstance(axes_raw[idx], dict) else {}
            axes.append(
                AxisProfile(
                    name=str(axis_data.get("name", default_axis.name)),
                    home_deg=float(axis_data.get("home_deg", default_axis.home_deg)),
                    min_deg=float(axis_data.get("min_deg", default_axis.min_deg)),
                    max_deg=float(axis_data.get("max_deg", default_axis.max_deg)),
                    positive_dir=str(axis_data.get("positive_dir", default_axis.positive_dir)),
                    reduction_ratio=float(axis_data.get("reduction_ratio", default_axis.reduction_ratio)),
                    max_speed_deg_s=float(axis_data.get("max_speed_deg_s", default_axis.max_speed_deg_s)),
                    accel_deg_s2=float(axis_data.get("accel_deg_s2", default_axis.accel_deg_s2)),
                    motor_current_a=float(axis_data.get("motor_current_a", default_axis.motor_current_a)),
                    steps_per_deg=float(axis_data.get("steps_per_deg", default_axis.steps_per_deg)),
                )
            )
        machine = MachineProfile(
            name=str(machine_raw.get("name", default.machine.name)),
            axes=axes or default.machine.axes,
            dh_table=[
                [float(v) for v in row]
                for row in machine_raw.get("dh_table", default.machine.dh_table)
                if isinstance(row, list) and len(row) >= 4
            ]
            or default.machine.dh_table,
            base_origin_mm=[float(v) for v in machine_raw.get("base_origin_mm", default.machine.base_origin_mm)[:3]],
            build_plate_mm=[float(v) for v in machine_raw.get("build_plate_mm", default.machine.build_plate_mm)[:3]],
            link_clearance_mm=float(machine_raw.get("link_clearance_mm", default.machine.link_clearance_mm)),
            wrist_clearance_mm=float(machine_raw.get("wrist_clearance_mm", default.machine.wrist_clearance_mm)),
            elbow_clearance_mm=float(machine_raw.get("elbow_clearance_mm", default.machine.elbow_clearance_mm)),
            tool_backoff_mm=float(machine_raw.get("tool_backoff_mm", default.machine.tool_backoff_mm)),
            wrist_backoff_mm=float(machine_raw.get("wrist_backoff_mm", default.machine.wrist_backoff_mm)),
            nozzle_lead_blend=float(machine_raw.get("nozzle_lead_blend", default.machine.nozzle_lead_blend)),
            nozzle_side_blend=float(machine_raw.get("nozzle_side_blend", default.machine.nozzle_side_blend)),
            wrist_path_blend=float(machine_raw.get("wrist_path_blend", default.machine.wrist_path_blend)),
            wrist_side_blend=float(machine_raw.get("wrist_side_blend", default.machine.wrist_side_blend)),
            wrist_radial_blend=float(machine_raw.get("wrist_radial_blend", default.machine.wrist_radial_blend)),
            wrist_down_blend=float(machine_raw.get("wrist_down_blend", default.machine.wrist_down_blend)),
        )
        tool = ToolProfile(
            name=str(tool_raw.get("name", default.tool.name)),
            nozzle_diameter_mm=float(tool_raw.get("nozzle_diameter_mm", default.tool.nozzle_diameter_mm)),
            tcp_offset_mm=[float(v) for v in tool_raw.get("tcp_offset_mm", default.tool.tcp_offset_mm)[:3]],
            nozzle_mount_angle_deg=float(tool_raw.get("nozzle_mount_angle_deg", default.tool.nozzle_mount_angle_deg)),
            safe_lift_mm=float(tool_raw.get("safe_lift_mm", default.tool.safe_lift_mm)),
            extrusion_max_mm_s=float(tool_raw.get("extrusion_max_mm_s", default.tool.extrusion_max_mm_s)),
        )
        material = MaterialProfile(
            name=str(material_raw.get("name", default.material.name)),
            nozzle_temp_c=int(material_raw.get("nozzle_temp_c", default.material.nozzle_temp_c)),
            bed_temp_c=int(material_raw.get("bed_temp_c", default.material.bed_temp_c)),
            chamber_temp_c=int(material_raw.get("chamber_temp_c", default.material.chamber_temp_c)),
            fan_pwm=int(material_raw.get("fan_pwm", default.material.fan_pwm)),
            retract_len_mm=float(material_raw.get("retract_len_mm", default.material.retract_len_mm)),
            retract_speed_mm_min=int(
                material_raw.get("retract_speed_mm_min", default.material.retract_speed_mm_min)
            ),
            notes=str(material_raw.get("notes", default.material.notes)),
        )
        process = ProcessProfile(
            name=str(process_raw.get("name", default.process.name)),
            layer_height_mm=float(process_raw.get("layer_height_mm", default.process.layer_height_mm)),
            line_width_mm=float(process_raw.get("line_width_mm", default.process.line_width_mm)),
            print_speed_mm_s=float(process_raw.get("print_speed_mm_s", default.process.print_speed_mm_s)),
            travel_speed_mm_s=float(process_raw.get("travel_speed_mm_s", default.process.travel_speed_mm_s)),
            flow_override_pct=int(process_raw.get("flow_override_pct", default.process.flow_override_pct)),
            speed_override_pct=int(process_raw.get("speed_override_pct", default.process.speed_override_pct)),
            pressure_advance=float(process_raw.get("pressure_advance", default.process.pressure_advance)),
            extrusion_multiplier=float(
                process_raw.get("extrusion_multiplier", default.process.extrusion_multiplier)
            ),
            z_hop_mm=float(process_raw.get("z_hop_mm", default.process.z_hop_mm)),
            nozzle_dwell_ms=int(process_raw.get("nozzle_dwell_ms", default.process.nozzle_dwell_ms)),
            notes=str(process_raw.get("notes", default.process.notes)),
        )
        return cls(machine=machine, tool=tool, material=material, process=process)

    def save(self) -> None:
        path = profiles_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

