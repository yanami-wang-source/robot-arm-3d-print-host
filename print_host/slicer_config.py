from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_CONFIG_NAME = "slicer_host.json"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return _project_root() / _CONFIG_NAME


@dataclass
class SlicerHostConfig:
    """外部切片器（PrusaSlicer / OrcaSlicer 等）路径与可选工艺配置。"""

    console_exe: str = ""
    profile_ini: str = ""

    @classmethod
    def load(cls) -> SlicerHostConfig:
        p = config_path()
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls(
            console_exe=str(data.get("console_exe", "") or ""),
            profile_ini=str(data.get("profile_ini", "") or ""),
        )

    def save(self) -> None:
        p = config_path()
        p.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
