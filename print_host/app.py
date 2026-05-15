import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import apply_modern_theme


def main() -> int:
    app = QApplication([])
    app.setApplicationName("Print Host")
    apply_modern_theme(app)
    w = MainWindow()
    w.show()
    smoke_ms_raw = os.environ.get("PRINT_HOST_SMOKETEST_MS", "").strip()
    if smoke_ms_raw:
        try:
            smoke_ms = max(1, int(smoke_ms_raw))
        except ValueError:
            smoke_ms = 0
        if smoke_ms > 0:
            QTimer.singleShot(smoke_ms, app.quit)
    return app.exec()
