from __future__ import annotations

from pathlib import Path

from .slicer_config import SlicerHostConfig


def validate_console_exe(path: str) -> bool:
    p = Path(path)
    return p.is_file() and p.suffix.lower() in (".exe", "")


def build_slice_command(cfg: SlicerHostConfig, stl_path: Path, out_gcode: Path) -> list[str]:
    """
    PrusaSlicer / OrcaSlicer / SuperSlicer 控制台模式常用参数。
    详见: https://github.com/prusa3d/PrusaSlicer/wiki/Using-PrusaSlicer-from-command-line
    """
    exe = Path(cfg.console_exe)
    stl_path = stl_path.resolve()
    out_gcode = out_gcode.resolve()
    out_gcode.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = [str(exe)]
    ini = (cfg.profile_ini or "").strip()
    if ini and Path(ini).is_file():
        args.extend(["--load", str(Path(ini).resolve())])
    args.extend(
        [
            "--slice",
            str(stl_path),
            "--export-gcode",
            "--output",
            str(out_gcode),
        ]
    )
    return args
