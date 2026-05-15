from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TOKEN = re.compile(r"([A-Za-z])(-?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)")
_EPS = 1e-9


@dataclass(frozen=True)
class MotionPoint:
    x: float
    y: float
    z: float
    line_index: int
    extrusion: bool
    feed: float | None


@dataclass(frozen=True)
class MotionSegment:
    start_xyz: tuple[float, float, float]
    end_xyz: tuple[float, float, float]
    line_index: int
    extrusion: bool
    rapid: bool
    feed: float | None


@dataclass(frozen=True)
class ParsedGcodeMotion:
    points: list[MotionPoint]
    segments: list[MotionSegment]
    pos_after_line_xyz: list[tuple[float, float, float] | None]


def _strip_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(
        (a[0] - b[0]) * (a[0] - b[0])
        + (a[1] - b[1]) * (a[1] - b[1])
        + (a[2] - b[2]) * (a[2] - b[2])
    )


def parse_gcode_motion(lines: list[str]) -> ParsedGcodeMotion:
    abs_xyz = True
    abs_e = True
    x = 0.0
    y = 0.0
    z = 0.0
    e = 0.0
    feed: float | None = None
    has_position = False
    points: list[MotionPoint] = []
    segments: list[MotionSegment] = []
    pos_after_line_xyz: list[tuple[float, float, float] | None] = []

    for raw in lines:
        s = _strip_comment(raw)
        if not s:
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue

        head = s.split(None, 1)[0].upper()
        toks = {m.group(1).upper(): float(m.group(2)) for m in _TOKEN.finditer(s)}

        if head == "G90":
            abs_xyz = True
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue
        if head == "G91":
            abs_xyz = False
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue
        if head == "M82":
            abs_e = True
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue
        if head == "M83":
            abs_e = False
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue
        if head == "G92":
            if "X" in toks:
                x = toks["X"]
                has_position = True
            if "Y" in toks:
                y = toks["Y"]
                has_position = True
            if "Z" in toks:
                z = toks["Z"]
                has_position = True
            if "E" in toks:
                e = toks["E"]
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue

        is_move = head in {"G0", "G00", "G1", "G01"} or head.startswith(("G0 ", "G1 "))
        if not is_move:
            pos_after_line_xyz.append((x, y, z) if has_position else None)
            continue

        prev_xyz = (x, y, z)
        prev_e = e

        if "F" in toks:
            feed = toks["F"]

        axis_present = False
        if "X" in toks:
            x = toks["X"] if abs_xyz else x + toks["X"]
            axis_present = True
            has_position = True
        if "Y" in toks:
            y = toks["Y"] if abs_xyz else y + toks["Y"]
            axis_present = True
            has_position = True
        if "Z" in toks:
            z = toks["Z"] if abs_xyz else z + toks["Z"]
            axis_present = True
            has_position = True
        if "E" in toks:
            e = toks["E"] if abs_e else e + toks["E"]

        current_xyz = (x, y, z)
        moved_distance = _distance(prev_xyz, current_xyz)
        if axis_present and has_position and moved_distance > _EPS:
            extrusion = e > prev_e + _EPS
            points.append(
                MotionPoint(
                    x=x,
                    y=y,
                    z=z,
                    line_index=len(pos_after_line_xyz),
                    extrusion=extrusion,
                    feed=feed,
                )
            )
            segments.append(
                MotionSegment(
                    start_xyz=prev_xyz,
                    end_xyz=current_xyz,
                    line_index=len(pos_after_line_xyz),
                    extrusion=extrusion,
                    rapid=head in {"G0", "G00"} or head.startswith("G0 "),
                    feed=feed,
                )
            )

        pos_after_line_xyz.append((x, y, z) if has_position else None)

    return ParsedGcodeMotion(
        points=points,
        segments=segments,
        pos_after_line_xyz=pos_after_line_xyz,
    )
