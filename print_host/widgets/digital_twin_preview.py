from __future__ import annotations

import math
import re
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QWidget

from ..gcode_motion import MotionSegment, parse_gcode_motion
from ..profiles import HostProfileBundle, MachineProfile, ToolProfile

_TOKEN = re.compile(r"([A-Za-z])(-?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)")
_FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

# These values are intentionally nominal. They keep the upper-computer preview
# usable before the real SolidWorks/physical limit calibration is finished.
NOMINAL_DH_MM = (
    (0.0, 90.0, 155.0, 0.0),
    (200.0, 0.0, 0.0, 0.0),
    (40.0, 90.0, 40.0, 0.0),
    (0.0, -90.0, 180.0, 0.0),
    (0.0, 90.0, 0.0, 0.0),
    (0.0, 0.0, 110.0, 0.0),
)
NOMINAL_LIMITS_DEG = (
    (-170.0, 170.0),
    (-90.0, 120.0),
    (-135.0, 135.0),
    (-180.0, 180.0),
    (-120.0, 120.0),
    (-360.0, 360.0),
)
NOMINAL_LINK_CLEARANCE_MM = 18.0
NOMINAL_WRIST_CLEARANCE_MM = 42.0
NOMINAL_ELBOW_CLEARANCE_MM = 58.0
NOMINAL_TOOL_BACKOFF_MM = 24.0
NOMINAL_WRIST_BACKOFF_MM = 76.0
NOMINAL_NOZZLE_LEAD_BLEND = 0.14
NOMINAL_NOZZLE_SIDE_BLEND = 0.05
NOMINAL_WRIST_PATH_BLEND = 0.48
NOMINAL_WRIST_SIDE_BLEND = 0.22
NOMINAL_WRIST_RADIAL_BLEND = 0.12
NOMINAL_WRIST_DOWN_BLEND = 0.82


@dataclass
class _PathPoint:
    x: float
    y: float
    z: float
    line_index: int
    extrusion: bool
    feed: float | None


@dataclass
class _RobotState:
    joints_deg: list[float] | None = None
    tcp_mm: tuple[float, float, float] | None = None
    line_index: int | None = None
    status: str = "未连接"
    source: str = "仿真"


@dataclass(frozen=True)
class NominalMotionState:
    line_index: int
    tcp_mm: tuple[float, float, float]
    joints_deg: tuple[float, float, float, float, float, float]
    extrusion: bool
    feed: float | None


@dataclass(frozen=True)
class _NominalPose:
    points: tuple[tuple[float, float, float], ...]
    joints_deg: tuple[float, float, float, float, float, float]


def _strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _parse_float_list(text: str) -> list[float]:
    return [float(x) for x in re.findall(_FLOAT, text)]


def _parse_gcode_path(lines: list[str]) -> list[_PathPoint]:
    parsed = parse_gcode_motion(lines)
    return [
        _PathPoint(
            x=pt.x,
            y=pt.y,
            z=pt.z,
            line_index=pt.line_index,
            extrusion=pt.extrusion,
            feed=pt.feed,
        )
        for pt in parsed.points
    ]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class DigitalTwinPreview(QWidget):
    """Nominal robotic-arm FDM process preview for the host UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(340)
        self.setMinimumWidth(560)
        defaults = HostProfileBundle.default()
        self._machine_profile = defaults.machine
        self._tool_profile = defaults.tool
        self._path: list[_PathPoint] = []
        self._segments: list[MotionSegment] = []
        self._exec_index: int | None = None
        self._robot = _RobotState()
        self._precheck = "待载入 G-code"
        self._precheck_color = QColor(170, 170, 170)
        self._path_bounds: tuple[float, float, float, float, float, float] | None = None
        self._result_complete = False
        self._scene_rect = QRectF()
        self._drag_mode: str | None = None
        self._drag_last = QPointF()
        self._view_yaw_deg = -38.0
        self._view_pitch_deg = 28.0
        self._view_zoom = 1.0
        self._view_pan = QPointF(0.0, 0.0)
        self._compact_mode = False

    def set_nominal_profiles(self, machine: MachineProfile, tool: ToolProfile) -> None:
        self._machine_profile = machine
        self._tool_profile = tool
        self._update_precheck()
        self.update()

    def set_compact_mode(self, compact: bool) -> None:
        self._compact_mode = compact
        self.setMinimumHeight(300 if compact else 340)
        self.update()

    def runtime_snapshot(self) -> dict[str, object]:
        motion = self.nominal_state_for_exec_line(self._exec_index)
        limit_text, limit_color = self._nominal_limit_summary()
        progress_pct = self._progress_pct()
        feed_text = "-" if motion is None or motion.feed is None else f"{motion.feed:.0f} mm/min"
        path_points = len(self._path)
        extrude_segments, travel_segments = self._segment_stats()
        if motion is None:
            segment_type = "待机"
        else:
            segment_type = "挤出段" if motion.extrusion else "空运行段"
        return {
            "line_index": self._robot.line_index if self._robot.line_index is not None else self._exec_index,
            "tcp_mm": self._nominal_tcp(),
            "joints_deg": list(self._estimated_joints()),
            "precheck_text": self._precheck,
            "precheck_level": self._level_from_color(self._precheck_color),
            "limit_text": limit_text,
            "limit_level": self._level_from_color(limit_color),
            "source": self._robot.source,
            "status": self._robot.status,
            "segment_type": segment_type,
            "feed": None if motion is None else motion.feed,
            "feed_text": feed_text,
            "progress_pct": progress_pct,
            "path_points": path_points,
            "segment_count": len(self._segments),
            "extrude_segments": extrude_segments,
            "travel_segments": travel_segments,
            "path_span_text": self._path_span_text(),
        }

    def clear(self) -> None:
        self._path = []
        self._segments = []
        self._exec_index = None
        self._robot = _RobotState()
        self._precheck = "待载入 G-code"
        self._precheck_color = QColor(170, 170, 170)
        self._path_bounds = None
        self._result_complete = False
        self.update()

    def load_gcode_lines(self, lines: list[str]) -> None:
        parsed = parse_gcode_motion(lines)
        self._path = [
            _PathPoint(
                x=pt.x,
                y=pt.y,
                z=pt.z,
                line_index=pt.line_index,
                extrusion=pt.extrusion,
                feed=pt.feed,
            )
            for pt in parsed.points
        ]
        self._segments = parsed.segments
        self._exec_index = None
        self._robot = _RobotState(status="待机", source="预览")
        self._path_bounds = self._calc_bounds(self._path)
        self._update_precheck()
        self._result_complete = False
        self.update()

    def set_exec_line_index(self, idx: int | None) -> None:
        self._exec_index = idx
        self._result_complete = False
        if idx is not None:
            self._robot.line_index = idx
            self._robot.status = "打印预览"
            self._robot.source = "G-code"
        else:
            self._robot.line_index = None
        self.update()

    def show_completed_result(self) -> None:
        if not self._path:
            self._result_complete = False
            self.update()
            return
        last_idx = self._path[-1].line_index
        state = self.set_simulated_robot_state(last_idx, status="打印完成", source=self._robot.source or "离线仿真")
        if state is None:
            self._exec_index = last_idx
        self._result_complete = True
        self.update()

    def nominal_state_for_exec_line(self, idx: int | None) -> NominalMotionState | None:
        path_index = self._path_index_for_exec_index(idx)
        if path_index is None:
            return None
        pt = self._path[path_index]
        pose = self._nominal_pose_for_exec_index(idx)
        if pose is None:
            return None
        return NominalMotionState(
            line_index=pt.line_index,
            tcp_mm=pose.points[-1],
            joints_deg=tuple(float(v) for v in pose.joints_deg[:6]),
            extrusion=pt.extrusion,
            feed=pt.feed,
        )

    def set_simulated_robot_state(
        self,
        idx: int | None,
        *,
        status: str = "离线演示",
        source: str = "离线仿真",
    ) -> NominalMotionState | None:
        self._exec_index = idx
        self._result_complete = False
        state = self.nominal_state_for_exec_line(idx)
        if state is None:
            self._robot.line_index = idx
            self._robot.status = status
            self._robot.source = source
            self.update()
            return None
        self._robot.line_index = state.line_index
        self._robot.tcp_mm = state.tcp_mm
        self._robot.joints_deg = list(state.joints_deg)
        self._robot.status = status
        self._robot.source = source
        self.update()
        return state

    def set_robot_state_from_line(self, line: str) -> None:
        parsed = self._parse_robot_line(line)
        if parsed is None:
            return
        self._result_complete = False
        if parsed.joints_deg is not None:
            self._robot.joints_deg = parsed.joints_deg
        if parsed.tcp_mm is not None:
            self._robot.tcp_mm = parsed.tcp_mm
        if parsed.line_index is not None:
            self._robot.line_index = parsed.line_index
            self._exec_index = parsed.line_index
        self._robot.status = parsed.status
        self._robot.source = parsed.source
        self.update()

    def _parse_robot_line(self, line: str) -> _RobotState | None:
        state = _RobotState(status="机械臂反馈", source="串口")
        idx_m = re.search(r"\bidx\s*=\s*(\d+)", line, flags=re.IGNORECASE)
        if idx_m:
            state.line_index = int(idx_m.group(1))

        status_m = re.search(r"\bstatus\s*=\s*([A-Za-z0-9_\-]+)", line, flags=re.IGNORECASE)
        if status_m:
            state.status = status_m.group(1)

        q_m = re.search(r"\b(?:q|joint|joints)\s*=\s*([^\s\]]+)", line, flags=re.IGNORECASE)
        if q_m:
            vals = _parse_float_list(q_m.group(1))
            if len(vals) >= 6:
                state.joints_deg = vals[:6]

        tcp_m = re.search(r"\btcp\s*=\s*([^\s\]]+)", line, flags=re.IGNORECASE)
        if tcp_m:
            vals = _parse_float_list(tcp_m.group(1))
            if len(vals) >= 3:
                state.tcp_mm = (vals[0], vals[1], vals[2])

        bracket_chunks = re.findall(r"\[([^\]]+)\]", line)
        if state.joints_deg is None and bracket_chunks:
            vals = _parse_float_list(bracket_chunks[-1])
            if len(vals) >= 6:
                state.joints_deg = vals[:6]

        if state.joints_deg is None and state.tcp_mm is None and state.line_index is None:
            return None
        return state

    def _calc_bounds(
        self, points: list[_PathPoint]
    ) -> tuple[float, float, float, float, float, float] | None:
        if not points:
            return None
        xs = [pt.x for pt in points]
        ys = [pt.y for pt in points]
        zs = [pt.z for pt in points]
        return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

    def _update_precheck(self) -> None:
        if not self._path_bounds:
            self._precheck = "待载入 G-code"
            self._precheck_color = QColor(170, 170, 170)
            return
        min_x, max_x, min_y, max_y, min_z, max_z = self._path_bounds
        span_x = max_x - min_x
        span_y = max_y - min_y
        span_z = max_z - min_z
        plate_x, plate_y, plate_z = self._machine_profile.build_plate_mm
        nominal_z_limit = max(plate_z, self._dh(0, 2) + self._dh(1, 0) + self._dh(3, 2))
        if min_z < -0.2:
            self._precheck = "Z 低于名义打印平面"
            self._precheck_color = QColor(235, 110, 100)
        elif max_z > nominal_z_limit or span_x > plate_x or span_y > plate_y or span_z > nominal_z_limit:
            self._precheck = "路径接近或超出名义范围"
            self._precheck_color = QColor(235, 180, 80)
        else:
            self._precheck = "名义预检通过（非最终）"
            self._precheck_color = QColor(94, 205, 130)

    def _progress_pct(self) -> int:
        if not self._path:
            return 0
        if self._result_complete:
            return 100
        if self._exec_index is None:
            return 0
        done = max(0, self._last_done_vertex() + 1)
        return int(100 * done / max(1, len(self._path)))

    def _segment_stats(self) -> tuple[int, int]:
        extrude = sum(1 for segment in self._segments if segment.extrusion)
        travel = len(self._segments) - extrude
        return extrude, travel

    def _path_span_text(self) -> str:
        if not self._path_bounds:
            return "-"
        min_x, max_x, min_y, max_y, min_z, max_z = self._path_bounds
        return f"{max_x - min_x:.1f} x {max_y - min_y:.1f} x {max_z - min_z:.1f} mm"

    def _last_done_vertex(self) -> int:
        if self._exec_index is None:
            return -1
        last = -1
        for i, pt in enumerate(self._path):
            if pt.line_index <= self._exec_index:
                last = i
            else:
                break
        return last

    def _path_point_for_exec_index(self, idx: int | None) -> _PathPoint | None:
        path_index = self._path_index_for_exec_index(idx)
        if path_index is None:
            return None
        return self._path[path_index]

    def _path_index_for_exec_index(self, idx: int | None) -> int | None:
        if idx is None or not self._path:
            return None
        last_index: int | None = None
        for i, pt in enumerate(self._path):
            if pt.line_index <= idx:
                last_index = i
            else:
                break
        return last_index

    def _current_path_point(self) -> _PathPoint | None:
        if not self._path:
            return None
        last = self._last_done_vertex()
        if last >= 0:
            return self._path[min(last, len(self._path) - 1)]
        return self._path[0]

    def _path_to_bed_world(self, pt: _PathPoint) -> tuple[float, float, float]:
        return self._xyz_to_bed_world((pt.x, pt.y, pt.z))

    def _xyz_to_bed_world(self, xyz: tuple[float, float, float]) -> tuple[float, float, float]:
        plate_x = self._machine_profile.build_plate_mm[0]
        if self._path_bounds is None:
            return (plate_x / 2.0, 0.0, max(0.0, xyz[2]))
        min_x, max_x, min_y, max_y, _min_z, _max_z = self._path_bounds
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        return (xyz[0] - cx + plate_x / 2.0, xyz[1] - cy, max(0.0, xyz[2]))

    def _nominal_tcp_for_point(self, pt: _PathPoint | None) -> tuple[float, float, float]:
        if pt is None:
            return (self._machine_profile.build_plate_mm[0] / 2.0, 0.0, 60.0)
        return self._path_to_bed_world(pt)

    def _nominal_tcp(self) -> tuple[float, float, float]:
        if self._robot.tcp_mm is not None:
            return self._robot.tcp_mm
        pt = self._current_path_point()
        return self._nominal_tcp_for_point(pt)

    def _base_and_shoulder(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        base = tuple(self._machine_profile.base_origin_mm)
        shoulder = (base[0], base[1], base[2] + self._dh(0, 2))
        return base, shoulder

    def _dh(self, row: int, col: int) -> float:
        return float(self._machine_profile.dh_table[row][col])

    @staticmethod
    def _level_from_color(color: QColor) -> str:
        if color.red() >= 230 and color.green() <= 140:
            return "bad"
        if color.red() >= 220 and color.green() >= 160:
            return "warn"
        if color.green() >= 180:
            return "good"
        return "neutral"

    def _vec_sub(
        self, a: tuple[float, float, float], b: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def _vec_add(
        self, a: tuple[float, float, float], b: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def _vec_scale(self, v: tuple[float, float, float], s: float) -> tuple[float, float, float]:
        return (v[0] * s, v[1] * s, v[2] * s)

    def _vec_dot(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def _vec_cross(
        self, a: tuple[float, float, float], b: tuple[float, float, float]
    ) -> tuple[float, float, float]:
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def _vec_norm(self, v: tuple[float, float, float]) -> float:
        return math.sqrt(self._vec_dot(v, v))

    def _vec_unit(self, v: tuple[float, float, float]) -> tuple[float, float, float]:
        norm = self._vec_norm(v)
        if norm < 1e-6:
            return (1.0, 0.0, 0.0)
        return (v[0] / norm, v[1] / norm, v[2] / norm)

    def _lerp_point(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        t: float,
    ) -> tuple[float, float, float]:
        return (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t,
        )

    def _clamp_reach(
        self,
        origin: tuple[float, float, float],
        target: tuple[float, float, float],
        min_dist: float,
        max_dist: float,
    ) -> tuple[float, float, float]:
        vec = self._vec_sub(target, origin)
        dist = self._vec_norm(vec)
        if dist < 1e-6:
            vec = (1.0, 0.0, 0.0)
            dist = 1.0
        desired = _clamp(dist, min_dist, max_dist)
        return self._vec_add(origin, self._vec_scale(self._vec_unit(vec), desired))

    def _path_world_point(self, path_index: int) -> tuple[float, float, float]:
        return self._path_to_bed_world(self._path[path_index])

    def _path_tangent_for_index(self, path_index: int) -> tuple[float, float, float]:
        current = self._path_world_point(path_index)
        prev = self._path_world_point(max(0, path_index - 1))
        nxt = self._path_world_point(min(len(self._path) - 1, path_index + 1))
        tangent = self._vec_sub(nxt, prev)
        if self._vec_norm(tangent) < 1e-6 and path_index > 0:
            tangent = self._vec_sub(current, prev)
        if self._vec_norm(tangent) < 1e-6 and path_index + 1 < len(self._path):
            tangent = self._vec_sub(nxt, current)
        if self._vec_norm(tangent) < 1e-6:
            tangent = (1.0, 0.0, 0.0)
        return self._vec_unit(tangent)

    def _signed_angle_on_axis(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        axis: tuple[float, float, float],
    ) -> float:
        axis_u = self._vec_unit(axis)
        a_plane = self._vec_sub(a, self._vec_scale(axis_u, self._vec_dot(a, axis_u)))
        b_plane = self._vec_sub(b, self._vec_scale(axis_u, self._vec_dot(b, axis_u)))
        if self._vec_norm(a_plane) < 1e-6 or self._vec_norm(b_plane) < 1e-6:
            return 0.0
        a_u = self._vec_unit(a_plane)
        b_u = self._vec_unit(b_plane)
        sin_term = self._vec_dot(axis_u, self._vec_cross(a_u, b_u))
        cos_term = _clamp(self._vec_dot(a_u, b_u), -1.0, 1.0)
        return math.degrees(math.atan2(sin_term, cos_term))

    def _solve_elbow_point(
        self,
        shoulder: tuple[float, float, float],
        wrist: tuple[float, float, float],
        l1: float,
        l2: float,
    ) -> tuple[float, float, float]:
        vec = self._vec_sub(wrist, shoulder)
        dist = max(1e-6, self._vec_norm(vec))
        u = self._vec_unit(vec)
        up = (0.0, 0.0, 1.0)
        n = self._vec_sub(up, self._vec_scale(u, self._vec_dot(up, u)))
        if self._vec_norm(n) < 1e-6:
            n = (-u[1], u[0], 0.0)
        n = self._vec_unit(n)
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
        h_sq = max(0.0, l1 * l1 - a * a)
        h = math.sqrt(h_sq)
        center = self._vec_add(shoulder, self._vec_scale(u, a))
        elbow_a = self._vec_add(center, self._vec_scale(n, h))
        elbow_b = self._vec_add(center, self._vec_scale(n, -h))
        return elbow_a if elbow_a[2] >= elbow_b[2] else elbow_b

    def _nominal_pose_for_tcp(
        self,
        target: tuple[float, float, float],
        tangent: tuple[float, float, float] | None = None,
    ) -> _NominalPose:
        base, shoulder = self._base_and_shoulder()
        tcp = (target[0], target[1], max(0.0, target[2]))
        l1 = self._dh(1, 0)
        l2 = self._dh(3, 2)

        shoulder_to_tcp = self._vec_sub(tcp, shoulder)
        radial = (shoulder_to_tcp[0], shoulder_to_tcp[1], 0.0)
        radial_unit = self._vec_unit(radial) if self._vec_norm(radial) >= 1e-6 else (1.0, 0.0, 0.0)
        path_dir = tangent if tangent is not None and self._vec_norm(tangent) >= 1e-6 else radial_unit
        path_dir = self._vec_unit(path_dir)
        up = (0.0, 0.0, 1.0)
        side = self._vec_cross(up, path_dir)
        if self._vec_norm(side) < 1e-6:
            side = self._vec_cross(up, radial_unit)
        if self._vec_norm(side) < 1e-6:
            side = (0.0, 1.0, 0.0)
        side = self._vec_unit(side)
        if self._vec_dot(side, radial_unit) < 0.0:
            side = self._vec_scale(side, -1.0)

        nozzle_dir = self._vec_unit(
            self._vec_add(
                self._vec_add(
                    self._vec_scale(up, -1.0),
                    self._vec_scale(path_dir, self._machine_profile.nozzle_lead_blend),
                ),
                self._vec_scale(side, self._machine_profile.nozzle_side_blend),
            )
        )
        tool = self._vec_add(tcp, self._vec_scale(nozzle_dir, -self._machine_profile.tool_backoff_mm))
        tool = (tool[0], tool[1], max(self._machine_profile.link_clearance_mm + 10.0, tool[2]))

        wrist_dir = self._vec_unit(
            self._vec_add(
                self._vec_add(
                    self._vec_scale(path_dir, self._machine_profile.wrist_path_blend),
                    self._vec_scale(side, self._machine_profile.wrist_side_blend),
                ),
                self._vec_add(
                    self._vec_scale(up, -self._machine_profile.wrist_down_blend),
                    self._vec_scale(radial_unit, self._machine_profile.wrist_radial_blend),
                ),
            )
        )
        wrist = self._vec_add(tool, self._vec_scale(wrist_dir, -self._machine_profile.wrist_backoff_mm))
        wrist = (
            wrist[0],
            wrist[1],
            max(
                self._machine_profile.wrist_clearance_mm,
                wrist[2],
            ),
        )
        wrist = self._clamp_reach(
            shoulder,
            wrist,
            abs(l1 - l2) + 18.0,
            l1 + l2 - 10.0,
        )
        wrist = (wrist[0], wrist[1], max(self._machine_profile.wrist_clearance_mm, wrist[2]))

        elbow = self._solve_elbow_point(shoulder, wrist, l1, l2)
        for _ in range(7):
            min_chain_z = min(elbow[2], wrist[2], tool[2])
            if (
                min_chain_z >= self._machine_profile.link_clearance_mm
                and elbow[2] >= self._machine_profile.elbow_clearance_mm
            ):
                break
            wrist = (
                wrist[0],
                wrist[1],
                max(self._machine_profile.wrist_clearance_mm, wrist[2] + 14.0),
            )
            wrist = self._clamp_reach(
                shoulder,
                wrist,
                abs(l1 - l2) + 18.0,
                l1 + l2 - 10.0,
            )
            elbow = self._solve_elbow_point(shoulder, wrist, l1, l2)

        upper = self._vec_sub(elbow, shoulder)
        lower = self._vec_sub(wrist, elbow)
        wrist_link = self._vec_sub(tool, wrist)
        nozzle = self._vec_sub(tcp, tool)

        q1 = math.degrees(math.atan2(upper[1], upper[0]))
        q2 = math.degrees(math.atan2(upper[2], max(1e-6, math.hypot(upper[0], upper[1]))))
        cos_elbow = _clamp(
            self._vec_dot(upper, lower) / max(1e-6, self._vec_norm(upper) * self._vec_norm(lower)),
            -1.0,
            1.0,
        )
        elbow_inner = math.degrees(math.acos(cos_elbow))
        q3 = -(180.0 - elbow_inner)
        lower_heading = math.degrees(math.atan2(lower[1], lower[0]))
        wrist_heading = math.degrees(math.atan2(wrist_link[1], wrist_link[0]))
        wrist_pitch = math.degrees(math.atan2(wrist_link[2], max(1e-6, math.hypot(wrist_link[0], wrist_link[1]))))
        nozzle_pitch = math.degrees(math.atan2(nozzle[2], max(1e-6, math.hypot(nozzle[0], nozzle[1]))))
        q4 = _clamp((wrist_heading - lower_heading + 180.0) % 360.0 - 180.0, -175.0, 175.0)
        q5 = _clamp(nozzle_pitch - wrist_pitch, -115.0, 115.0)
        q6 = _clamp(self._signed_angle_on_axis(up, side, nozzle), -180.0, 180.0)

        points = (base, shoulder, elbow, wrist, tool, tcp)
        joints = (q1, q2, q3, q4, q5, q6)
        return _NominalPose(points=points, joints_deg=joints)

    def _nominal_pose_for_exec_index(self, idx: int | None) -> _NominalPose | None:
        path_index = self._path_index_for_exec_index(idx)
        if path_index is None:
            return None
        pt = self._path[path_index]
        tcp = self._nominal_tcp_for_point(pt)
        tangent = self._path_tangent_for_index(path_index)
        return self._nominal_pose_for_tcp(tcp, tangent=tangent)

    def _estimated_joints_for_tcp(self, target: tuple[float, float, float]) -> list[float]:
        pose = self._nominal_pose_for_tcp(target)
        return list(pose.joints_deg)

    def _estimated_joints(self) -> list[float]:
        if self._robot.joints_deg is not None:
            return self._robot.joints_deg
        return self._estimated_joints_for_tcp(self._nominal_tcp())

    def _arm_points(self) -> list[tuple[float, float, float]]:
        pose = self._nominal_pose_for_exec_index(self._robot.line_index)
        if pose is None:
            pose = self._nominal_pose_for_tcp(self._nominal_tcp())
        return list(pose.points)

    def _nominal_limit_summary(self) -> tuple[str, QColor]:
        q = self._estimated_joints()
        over = []
        for i, (angle, axis) in enumerate(zip(q, self._machine_profile.axes), start=1):
            low, high = axis.min_deg, axis.max_deg
            if angle < low or angle > high:
                over.append(f"J{i}")
        if over:
            return ("名义限位预警: " + ", ".join(over), QColor(235, 180, 80))
        return ("名义限位: 暂未触发", QColor(94, 205, 130))

    def _reset_view(self) -> None:
        self._view_yaw_deg = -38.0
        self._view_pitch_deg = 28.0
        self._view_zoom = 1.0
        self._view_pan = QPointF(0.0, 0.0)
        self.update()

    def _rotate_world(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        yaw = math.radians(self._view_yaw_deg)
        pitch = math.radians(self._view_pitch_deg)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)

        x1 = x * cy - y * sy
        y1 = x * sy + y * cy
        z1 = z

        y2 = y1 * cp - z1 * sp
        z2 = y1 * sp + z1 * cp
        return (x1, y2, z2)

    def _scene_world_points(self) -> list[tuple[float, float, float]]:
        plate_x, plate_y = self._machine_profile.build_plate_mm[:2]
        half_y = plate_y / 2.0
        points = [
            (0.0, -half_y, 0.0),
            (plate_x, -half_y, 0.0),
            (plate_x, half_y, 0.0),
            (0.0, half_y, 0.0),
        ]
        points.extend(self._arm_points())
        for segment in self._segments:
            points.append(self._xyz_to_bed_world(segment.start_xyz))
            points.append(self._xyz_to_bed_world(segment.end_xyz))
        return points

    def _make_projector(self, rect: QRectF):
        margin = 28.0
        world_points = self._scene_world_points()
        rotated = [self._rotate_world(*pt) for pt in world_points]
        xs = [pt[0] for pt in rotated]
        zs = [pt[2] for pt in rotated]
        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)
        span_x = max(1.0, max_x - min_x)
        span_z = max(1.0, max_z - min_z)
        base_scale = min(
            max(0.2, (rect.width() - 2 * margin) / span_x),
            max(0.2, (rect.height() - 2 * margin) / span_z),
        )
        scale = max(0.12, base_scale * self._view_zoom)
        center_x = (min_x + max_x) / 2.0
        center_z = (min_z + max_z) / 2.0
        origin = QPointF(
            rect.center().x() - center_x * scale + self._view_pan.x(),
            rect.center().y() + center_z * scale + self._view_pan.y(),
        )

        def project(x: float, y: float, z: float) -> QPointF:
            vx, _depth, vz = self._rotate_world(x, y, z)
            return QPointF(origin.x() + vx * scale, origin.y() - vz * scale)

        return project

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._scene_rect.contains(event.position()):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_mode = "rotate"
                self._drag_last = event.position()
                event.accept()
                return
            if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
                self._drag_mode = "pan"
                self._drag_last = event.position()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode is None:
            super().mouseMoveEvent(event)
            return
        delta = event.position() - self._drag_last
        self._drag_last = event.position()
        if self._drag_mode == "rotate":
            self._view_yaw_deg += delta.x() * 0.45
            self._view_pitch_deg = max(8.0, min(82.0, self._view_pitch_deg + delta.y() * 0.25))
        elif self._drag_mode == "pan":
            self._view_pan += delta
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_mode = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._scene_rect.contains(event.position()):
            self._reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._scene_rect.contains(event.position()):
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        factor = 1.12 if delta > 0 else 0.9
        self._view_zoom = max(0.35, min(4.0, self._view_zoom * factor))
        self.update()
        event.accept()

    @staticmethod
    def _draw_card(p: QPainter, rect: QRectF, fill: QColor, border: QColor) -> None:
        p.save()
        p.setPen(QPen(border, 1.0))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 12.0, 12.0)
        p.restore()

    def _draw_info_chip(
        self,
        p: QPainter,
        rect: QRectF,
        text: str,
        fill: QColor,
        border: QColor,
        text_color: QColor,
    ) -> QRectF:
        font = QFont(self.font())
        font.setPointSize(max(9, font.pointSize()))
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        text_rect = metrics.boundingRect(0, 0, int(rect.width()), 200, int(Qt.TextFlag.TextWordWrap), text)
        chip_rect = QRectF(rect.left(), rect.top(), rect.width(), max(28.0, text_rect.height() + 12.0))
        p.setPen(QPen(border, 1.0))
        p.setBrush(fill)
        p.drawRoundedRect(chip_rect, 9.0, 9.0)
        p.setPen(text_color)
        p.drawText(chip_rect.adjusted(10.0, 6.0, -10.0, -6.0), int(Qt.TextFlag.TextWordWrap), text)
        return chip_rect

    def _draw_info_row(
        self,
        p: QPainter,
        rect: QRectF,
        label: str,
        value: str,
        *,
        value_color: QColor = QColor("#102033"),
    ) -> QRectF:
        title_font = QFont(self.font())
        title_font.setPointSize(max(8, title_font.pointSize() - 1))
        title_font.setBold(True)
        body_font = QFont(self.font())
        body_font.setPointSize(max(9, body_font.pointSize()))

        p.setFont(title_font)
        p.setPen(QColor("#6b7d8f"))
        p.drawText(rect.adjusted(0.0, 0.0, 0.0, -2.0), int(Qt.TextFlag.TextSingleLine), label)

        p.setFont(body_font)
        p.setPen(value_color)
        metrics = p.fontMetrics()
        value_rect = metrics.boundingRect(
            0,
            0,
            int(rect.width()),
            300,
            int(Qt.TextFlag.TextWordWrap),
            value,
        )
        top = rect.top() + 18.0
        draw_rect = QRectF(rect.left(), top, rect.width(), max(20.0, value_rect.height() + 2.0))
        p.drawText(draw_rect, int(Qt.TextFlag.TextWordWrap), value)
        return QRectF(rect.left(), rect.top(), rect.width(), draw_rect.bottom() - rect.top())

    def _draw_scene_badge(
        self,
        p: QPainter,
        x: float,
        y: float,
        text: str,
        *,
        fill: QColor,
        border: QColor,
        text_color: QColor,
    ) -> QRectF:
        font = QFont(self.font())
        font.setPointSize(max(8, font.pointSize() - 1))
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        width = metrics.horizontalAdvance(text) + 18
        height = max(22, metrics.height() + 8)
        rect = QRectF(x, y, width, height)
        p.setPen(QPen(border, 1.0))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 9.0, 9.0)
        p.setPen(text_color)
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        return rect

    def _draw_joint_axes(
        self,
        p: QPainter,
        iso,
        point: tuple[float, float, float],
        axis_scale_mm: float,
    ) -> None:
        origin = iso(*point)
        axis_specs = (
            (QColor("#ef4444"), (axis_scale_mm, 0.0, 0.0)),
            (QColor("#10b981"), (0.0, axis_scale_mm, 0.0)),
            (QColor("#3b82f6"), (0.0, 0.0, axis_scale_mm)),
        )
        for color, delta in axis_specs:
            tip = iso(point[0] + delta[0], point[1] + delta[1], point[2] + delta[2])
            p.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(origin, tip)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#eef7ff"))

        outer = QRectF(6.0, 6.0, max(0.0, self.width() - 12.0), max(0.0, self.height() - 12.0))
        panel_w = min(320, max(260, int(outer.width() * 0.31))) if self._compact_mode else min(
            360,
            max(292, int(outer.width() * 0.34)),
        )
        scene = QRectF(outer.left(), outer.top(), outer.width() - panel_w - 12.0, outer.height())
        panel = QRectF(scene.right() + 12.0, outer.top(), panel_w, outer.height())
        self._scene_rect = scene

        self._draw_card(p, scene, QColor("#ffffff"), QColor("#d7e8f6"))
        self._draw_card(p, panel, QColor("#f7fbff"), QColor("#d7e8f6"))

        self._draw_scene(p, scene)
        self._draw_status_panel(p, panel)
        p.end()

    def _draw_scene(self, p: QPainter, rect: QRectF) -> None:
        viewport = rect.adjusted(16.0, 42.0, -16.0, -16.0)
        project = self._make_projector(viewport)
        snapshot = self.runtime_snapshot()

        title_font = QFont(self.font())
        title_font.setPointSize(max(10, title_font.pointSize() + 1))
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#124f82"))
        p.drawText(
            QRectF(rect.left() + 16.0, rect.top() + 14.0, rect.width() - 32.0, 22.0),
            "数字孪生 / 3D 打印过程预览",
        )

        meta_font = QFont(self.font())
        meta_font.setPointSize(max(8, meta_font.pointSize() - 1))
        p.setFont(meta_font)
        p.setPen(QColor("#6c8197"))
        p.drawText(
            QRectF(rect.left() + 16.0, rect.top() + 34.0, rect.width() - 32.0, 18.0),
            int(Qt.TextFlag.TextSingleLine),
            "橙/绿表示挤出段，蓝色虚线表示空运行段；左键旋转，滚轮缩放，右键平移。",
        )

        badge_y = rect.top() + 58.0
        badge_x = rect.left() + 16.0
        badge_rect = self._draw_scene_badge(
            p,
            badge_x,
            badge_y,
            f"模式 {snapshot['status']}",
            fill=QColor("#eef8ff"),
            border=QColor("#cfe3f5"),
            text_color=QColor("#124f82"),
        )
        badge_x = badge_rect.right() + 8.0
        badge_rect = self._draw_scene_badge(
            p,
            badge_x,
            badge_y,
            f"线段 {snapshot['segment_type']}",
            fill=QColor("#f8fcff"),
            border=QColor("#d6eaf8"),
            text_color=QColor("#215a8d"),
        )
        badge_x = badge_rect.right() + 8.0
        self._draw_scene_badge(
            p,
            badge_x,
            badge_y,
            f"进给 {snapshot['feed_text']}",
            fill=QColor("#fff8ee"),
            border=QColor("#f3d3a4"),
            text_color=QColor("#9a5f12"),
        )

        self._draw_build_plate(p, project)
        self._draw_print_path(p, rect, project)
        self._draw_robot_arm(p, project)

    def _draw_build_plate(self, p: QPainter, iso) -> None:  # noqa: ANN001
        plate_x, plate_y = self._machine_profile.build_plate_mm[:2]
        half_y = plate_y / 2.0
        corners = [(0.0, -half_y, 0.0), (plate_x, -half_y, 0.0), (plate_x, half_y, 0.0), (0.0, half_y, 0.0)]
        poly = QPolygonF([iso(*c) for c in corners])
        p.setPen(QPen(QColor("#8abfe3"), 1.0))
        p.setBrush(QColor("#f3faff"))
        p.drawPolygon(poly)
        p.setPen(QPen(QColor("#d2e8f7"), 1.0))
        for i in range(1, 5):
            x = plate_x * i / 5.0
            p.drawLine(iso(x, -half_y, 0.0), iso(x, half_y, 0.0))
            y = -half_y + plate_y * i / 5.0
            p.drawLine(iso(0.0, y, 0.0), iso(plate_x, y, 0.0))

        p.setPen(QPen(QColor("#5a7489"), 1.0))
        p.drawText(iso(0.0, -half_y - 10.0, 0.0), "打印平台 / 工件坐标")

    def _draw_print_path(self, p: QPainter, rect: QRectF, iso) -> None:  # noqa: ANN001
        if not self._segments:
            p.setPen(QColor("#75889b"))
            p.drawText(
                QRectF(rect.left() + 22.0, rect.center().y() - 12.0, rect.width() - 44.0, 24.0),
                int(Qt.AlignmentFlag.AlignCenter),
                "载入 G-code 后将在这里显示路径、喷嘴位置和机械臂姿态。",
            )
            return

        pen_plan_extrude = QPen(QColor("#ff9a62"), 2.2)
        pen_plan_travel = QPen(QColor("#77c8ff"), 1.4, Qt.PenStyle.DashLine)
        pen_done_extrude = QPen(QColor("#20b36c"), 2.5)
        pen_done_travel = QPen(QColor("#2d97e8"), 1.6, Qt.PenStyle.DashLine)
        pen_complete_extrude = QPen(QColor("#0da768"), 2.6)
        pen_complete_travel = QPen(QColor("#4d9fdc"), 1.5, Qt.PenStyle.DashLine)
        for segment in self._segments:
            start_world = self._xyz_to_bed_world(segment.start_xyz)
            end_world = self._xyz_to_bed_world(segment.end_xyz)
            start = iso(*start_world)
            end = iso(*end_world)
            if self._result_complete:
                p.setPen(pen_complete_extrude if segment.extrusion else pen_complete_travel)
            elif self._exec_index is not None and segment.line_index <= self._exec_index:
                p.setPen(pen_done_extrude if segment.extrusion else pen_done_travel)
            elif segment.extrusion:
                p.setPen(pen_plan_extrude)
            else:
                p.setPen(pen_plan_travel)
            p.drawLine(start, end)

        cur = self._current_path_point()
        if cur is not None and not self._result_complete:
            head = iso(*self._path_to_bed_world(cur))
            p.setPen(QPen(QColor("#0f8ddd"), 7.0))
            p.drawPoint(head)
            p.setPen(QPen(QColor("#57c7ff"), 1.2))
            p.drawEllipse(head, 8.0, 8.0)

    def _draw_robot_arm(self, p: QPainter, iso) -> None:  # noqa: ANN001
        pts = self._arm_points()
        screen = [iso(*pt) for pt in pts]

        base_top = screen[0]
        base_bottom = QPointF(base_top.x(), base_top.y() + 28.0)
        p.setPen(QPen(QColor("#4f6377"), 10.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(base_top, base_bottom)
        p.setPen(QPen(QColor("#334155"), 15.0))
        p.drawPoint(base_bottom)

        link_specs = [
            (QColor("#4c8ec4"), QColor("#315879")),
            (QColor("#5e7fe0"), QColor("#3f57a8")),
            (QColor("#57b3d9"), QColor("#2d7fa0")),
            (QColor("#71c9ff"), QColor("#4192d1")),
            (QColor("#ffab66"), QColor("#d77d2f")),
        ]
        for index in range(len(screen) - 1):
            start = screen[index]
            end = screen[index + 1]
            fill_color, edge_color = link_specs[min(index, len(link_specs) - 1)]
            p.setPen(QPen(edge_color, 11.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(start, end)
            p.setPen(QPen(fill_color, 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(start, end)

        axis_scale_mm = 14.0
        for world_point, screen_point in zip(pts[1:-1], screen[1:-1]):
            self._draw_joint_axes(p, iso, world_point, axis_scale_mm)
            p.setPen(QPen(QColor("#26445f"), 2.2))
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(screen_point, 6.4, 6.4)
            p.setBrush(QColor("#5aaee5"))
            p.drawEllipse(screen_point, 2.4, 2.4)

        p.setPen(QPen(QColor("#1f3650"), 2.4))
        p.setBrush(QColor("#e9f6ff"))
        p.drawEllipse(screen[0], 7.4, 7.4)
        p.setBrush(QColor("#ffb274"))
        p.setPen(QPen(QColor("#d77d2f"), 1.8))
        p.drawEllipse(screen[-1], 5.6, 5.6)

        p.setPen(QPen(QColor("#ffab66"), 1.4))
        p.drawLine(screen[-2], screen[-1])
        p.drawText(screen[-1] + QPointF(8, -8), "喷嘴/TCP")

    def _draw_status_panel(self, p: QPainter, rect: QRectF) -> None:
        inner = rect.adjusted(18.0, 18.0, -18.0, -18.0)
        y = inner.top()
        snapshot = self.runtime_snapshot()

        title_font = QFont(self.font())
        title_font.setPointSize(max(10, title_font.pointSize() + 1))
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#124f82"))
        p.drawText(QRectF(inner.left(), y, inner.width(), 24.0), "数字孪生状态")
        y += 28.0

        pct = int(snapshot["progress_pct"])

        track_rect = QRectF(inner.left(), y, inner.width(), 16.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6f2fb"))
        p.drawRoundedRect(track_rect, 8.0, 8.0)
        chunk_width = track_rect.width() * pct / 100.0
        if chunk_width > 0:
            p.setBrush(QColor("#71c9ff"))
            p.drawRoundedRect(QRectF(track_rect.left(), track_rect.top(), chunk_width, track_rect.height()), 8.0, 8.0)
        p.setPen(QColor("#4c6478"))
        meta_font = QFont(self.font())
        meta_font.setPointSize(max(8, meta_font.pointSize() - 1))
        p.setFont(meta_font)
        p.drawText(track_rect, int(Qt.AlignmentFlag.AlignCenter), f"路径回放 {pct}%")
        y += 26.0

        row_rect = self._draw_info_row(
            p,
            QRectF(inner.left(), y, inner.width(), 40.0),
            "路径点 / 当前行",
            f"{len(self._path)} 个点 / {self._exec_index if self._exec_index is not None else '-'}",
        )
        y = row_rect.bottom() + 10.0

        limit_text, limit_color = self._nominal_limit_summary()
        chip_rect = self._draw_info_chip(
            p,
            QRectF(inner.left(), y, inner.width(), 40.0),
            self._precheck,
            QColor("#f4fbff") if self._precheck_color.green() >= 180 else QColor("#fff8ee"),
            QColor("#d6eaf8") if self._precheck_color.green() >= 180 else QColor("#f3d3a4"),
            QColor("#155f43") if self._precheck_color.green() >= 180 else QColor("#9a5f12"),
        )
        y = chip_rect.bottom() + 8.0
        chip_rect = self._draw_info_chip(
            p,
            QRectF(inner.left(), y, inner.width(), 40.0),
            limit_text,
            QColor("#f4fbff") if limit_color.green() >= 180 else QColor("#fff8ee"),
            QColor("#d6eaf8") if limit_color.green() >= 180 else QColor("#f3d3a4"),
            QColor("#155f43") if limit_color.green() >= 180 else QColor("#9a5f12"),
        )
        y = chip_rect.bottom() + 12.0

        tcp = self._nominal_tcp()
        q = self._estimated_joints()
        if self._compact_mode:
            rows = [
                ("状态来源", self._robot.source),
                ("运行状态", self._robot.status),
                ("当前线段", str(snapshot["segment_type"])),
                ("进给速度", str(snapshot["feed_text"])),
                ("TCP 位置", f"X{tcp[0]:.1f}  Y{tcp[1]:.1f}  Z{tcp[2]:.1f} mm"),
                ("关节姿态 A", f"J1 {q[0]:.1f}°  J2 {q[1]:.1f}°  J3 {q[2]:.1f}°"),
                ("轨迹统计", f"{snapshot['path_points']} 点 / {snapshot['segment_count']} 段"),
            ]
        else:
            rows = [
                ("状态来源", self._robot.source),
                ("运行状态", self._robot.status),
                ("当前线段", str(snapshot["segment_type"])),
                ("进给速度", str(snapshot["feed_text"])),
                ("挤出 / 空走", f"{snapshot['extrude_segments']} / {snapshot['travel_segments']} 段"),
                ("路径跨度", str(snapshot["path_span_text"])),
                ("TCP 位置", f"X{tcp[0]:.1f}  Y{tcp[1]:.1f}  Z{tcp[2]:.1f} mm"),
                ("关节姿态 A", f"J1 {q[0]:.1f}°   J2 {q[1]:.1f}°   J3 {q[2]:.1f}°"),
                ("关节姿态 B", f"J4 {q[3]:.1f}°   J5 {q[4]:.1f}°   J6 {q[5]:.1f}°"),
                ("轨迹统计", f"{snapshot['path_points']} 点 / {snapshot['segment_count']} 段"),
                ("模型说明", "DH 参数已接入，真实限位与外观仍待根据实体继续校准。"),
            ]
        for label, value in rows:
            row_rect = self._draw_info_row(p, QRectF(inner.left(), y, inner.width(), 42.0), label, value)
            y = row_rect.bottom() + 10.0

        if self._compact_mode:
            return

        subtitle_font = QFont(self.font())
        subtitle_font.setPointSize(max(9, subtitle_font.pointSize()))
        subtitle_font.setBold(True)
        p.setFont(subtitle_font)
        p.setPen(QColor("#124f82"))
        p.drawText(QRectF(inner.left(), y, inner.width(), 20.0), "后续待标定")
        y += 24.0

        body_font = QFont(self.font())
        body_font.setPointSize(max(9, body_font.pointSize()))
        p.setFont(body_font)
        p.setPen(QColor("#51687c"))
        for text in ("关节零位", "真实限位角", "平台-机械臂坐标系", "末端喷嘴偏置"):
            p.drawText(QRectF(inner.left(), y, inner.width(), 18.0), f"• {text}")
            y += 19.0
