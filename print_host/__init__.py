from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"

_VENDOR_SITE = Path(__file__).resolve().parent.parent / "app" / "vendor_site"
if _VENDOR_SITE.is_dir():
    vendor_path = str(_VENDOR_SITE)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
