from __future__ import annotations

import re

_TOK = re.compile(
    r"T:\s*([0-9.-]+)(?:\s*/\s*([0-9.-]+))?"
    r"|B:\s*([0-9.-]+)(?:\s*/\s*([0-9.-]+))?",
    re.IGNORECASE,
)


def parse_temperature_line(line: str) -> tuple[float | None, float | None, float | None, float | None]:
    """Return (hotend_cur, hotend_target, bed_cur, bed_target) from a Marlin-style status line."""
    hot_cur: float | None = None
    hot_tgt: float | None = None
    bed_cur: float | None = None
    bed_tgt: float | None = None
    for m in _TOK.finditer(line):
        if m.group(1) is not None:
            try:
                hot_cur = float(m.group(1))
            except ValueError:
                pass
            if m.group(2) is not None:
                try:
                    hot_tgt = float(m.group(2))
                except ValueError:
                    pass
        if m.group(3) is not None:
            try:
                bed_cur = float(m.group(3))
            except ValueError:
                pass
            if m.group(4) is not None:
                try:
                    bed_tgt = float(m.group(4))
                except ValueError:
                    pass
    return hot_cur, hot_tgt, bed_cur, bed_tgt
