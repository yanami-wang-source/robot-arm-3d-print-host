from __future__ import annotations

import math
from pathlib import Path


Point3 = tuple[float, float, float]


def _demo_assets_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "demo_assets"


def _dist(a: Point3, b: Point3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _fmt_point(pt: Point3) -> str:
    return f"X{pt[0]:.3f} Y{pt[1]:.3f} Z{pt[2]:.3f}"


def _arch_point(t: float, y: float) -> Point3:
    x = 40.0 + 140.0 * t
    z = 20.0 + 74.0 * (math.sin(math.pi * t) ** 1.18)
    return (x, y, z)


def _crown_stringer_point(t: float) -> Point3:
    x = 58.0 + 104.0 * t
    y = 70.0
    z = 46.0 + 58.0 * (math.sin(math.pi * t) ** 1.10)
    return (x, y, z)


def _cantilever_points() -> list[Point3]:
    return [
        (110.0, 70.0, 94.0),
        (126.0, 60.0, 84.0),
        (144.0, 48.0, 71.0),
        (162.0, 36.0, 58.0),
        (178.0, 26.0, 46.0),
    ]


def _emit_travel(lines: list[str], target: Point3, *, feed: float | None = None) -> None:
    prefix = "G0"
    if feed is not None:
        prefix += f" F{feed:.0f}"
    lines.append(f"{prefix} {_fmt_point(target)}")


def _emit_extrude(
    lines: list[str],
    start: Point3,
    target: Point3,
    *,
    feed: float | None = None,
    e_per_mm: float = 0.028,
) -> None:
    prefix = "G1"
    if feed is not None:
        prefix += f" F{feed:.0f}"
    e_mm = max(0.18, _dist(start, target) * e_per_mm)
    lines.append(f"{prefix} {_fmt_point(target)} E{e_mm:.3f}")


def build_curved_truss_bridge() -> str:
    front_arch = [_arch_point(i / 16.0, 50.0) for i in range(17)]
    back_arch = [_arch_point(i / 16.0, 90.0) for i in range(17)]
    rib_indices = [0, 3, 5, 8, 11, 13, 16]
    rib_pairs = [(front_arch[i], back_arch[i]) for i in rib_indices]
    crown = [_crown_stringer_point(i / 10.0) for i in range(11)]
    cantilever = _cantilever_points()

    lines: list[str] = [
        "; Curved spatial truss bridge demo for robotic-arm printing",
        "; Generated parametrically to keep the arch continuous instead of piecewise-zigzag.",
        "; Features: dual curved arches, transverse ribs, diagonal braces, crown stringer, and anti-gravity cantilever.",
        "G90",
        "G21",
        "M83",
        "",
        "; front curved arch",
        f"G92 {_fmt_point(front_arch[0])} E0",
    ]

    current = front_arch[0]
    for i, pt in enumerate(front_arch[1:], start=1):
        _emit_extrude(lines, current, pt, feed=820.0 if i == 1 else None, e_per_mm=0.026)
        current = pt

    lines.append("")
    lines.append("; back curved arch")
    _emit_travel(lines, back_arch[0], feed=1450.0)
    current = back_arch[0]
    for i, pt in enumerate(back_arch[1:], start=1):
        _emit_extrude(lines, current, pt, feed=820.0 if i == 1 else None, e_per_mm=0.026)
        current = pt

    lines.append("")
    lines.append("; transverse ribs between the two arches")
    for i, (front_pt, back_pt) in enumerate(rib_pairs):
        _emit_travel(lines, front_pt, feed=1400.0 if i == 0 else None)
        _emit_extrude(lines, front_pt, back_pt, feed=760.0, e_per_mm=0.024)

    lines.append("")
    lines.append("; alternating diagonal braces")
    for i in range(len(rib_pairs) - 1):
        front_a, back_a = rib_pairs[i]
        front_b, back_b = rib_pairs[i + 1]
        _emit_travel(lines, front_a)
        _emit_extrude(lines, front_a, back_b, feed=740.0, e_per_mm=0.023)
        _emit_travel(lines, back_a)
        _emit_extrude(lines, back_a, front_b, e_per_mm=0.023)

    lines.append("")
    lines.append("; suspended curved crown stringer")
    _emit_travel(lines, crown[0], feed=1320.0)
    current = crown[0]
    for i, pt in enumerate(crown[1:], start=1):
        _emit_extrude(lines, current, pt, feed=720.0 if i == 1 else None, e_per_mm=0.025)
        current = pt

    lines.append("")
    lines.append("; anti-gravity leaning cantilever showcase")
    _emit_travel(lines, cantilever[0], feed=1360.0)
    current = cantilever[0]
    for i, pt in enumerate(cantilever[1:], start=1):
        _emit_extrude(lines, current, pt, feed=700.0 if i == 1 else None, e_per_mm=0.027)
        current = pt

    lines.extend(
        [
            "",
            "M104 S0",
            "M140 S0",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    out_dir = _demo_assets_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    bridge_path = out_dir / "demo_spatial_truss_bridge.gcode"
    bridge_path.write_text(build_curved_truss_bridge(), encoding="utf-8")
    print(f"Wrote {bridge_path}")


if __name__ == "__main__":
    main()
