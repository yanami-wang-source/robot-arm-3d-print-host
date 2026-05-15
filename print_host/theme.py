from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


def _register_ui_fonts() -> None:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhl.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


def _pick_ui_font() -> QFont:
    _register_ui_fonts()
    families = set(QFontDatabase.families())
    for family in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Segoe UI",
        "Noto Sans CJK SC",
        "Arial",
    ):
        if family in families:
            font = QFont(family, 10)
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            return font
    font = QFont()
    font.setPointSize(10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def apply_modern_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(_pick_ui_font())

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#eef7ff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f4faff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#7dcfff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f172a"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QWidget {
            color: #111827;
            background: #eef7ff;
            selection-background-color: #bfe7ff;
            selection-color: #111827;
        }

        QToolTip {
            background: #ffffff;
            color: #0f172a;
            border: 1px solid #cfe3f5;
            padding: 6px 8px;
        }

        QMainWindow, QDialog {
            background: #eef7ff;
        }

        QMenuBar {
            background: #ffffff;
            color: #0f172a;
            border-bottom: 1px solid #d7e8f6;
            padding: 4px 8px;
        }

        QMenuBar::item {
            spacing: 10px;
            padding: 6px 12px;
            border-radius: 7px;
            background: transparent;
        }

        QMenuBar::item:selected {
            background: #e7f6ff;
        }

        QMenu {
            background: #ffffff;
            border: 1px solid #d7e8f6;
            padding: 6px;
        }

        QMenu::item {
            padding: 7px 22px;
            border-radius: 6px;
        }

        QMenu::item:selected {
            background: #e7f6ff;
        }

        QStatusBar {
            background: #f8fcff;
            border-top: 1px solid #d7e8f6;
        }

        QTabWidget::pane {
            background: #ffffff;
            border: 1px solid #d7e8f6;
            border-radius: 8px;
            top: -1px;
        }

        QTabBar::tab {
            background: #f4fbff;
            color: #3b4d63;
            border: 1px solid #d7e8f6;
            border-bottom-color: #cfe3f5;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            padding: 9px 18px;
            margin-right: 6px;
            min-width: 88px;
        }

        QTabBar::tab:selected {
            background: #ffffff;
            color: #0f4c81;
            border-color: #8fcfff;
        }

        QTabBar::tab:hover:!selected {
            background: #ebf8ff;
        }

        QGroupBox {
            background: #ffffff;
            border: 1px solid #d9e9f7;
            border-radius: 8px;
            margin-top: 16px;
            padding: 14px 14px 12px 14px;
            font-weight: 600;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: 3px;
            padding: 0 6px;
            color: #14558a;
            background: #ffffff;
        }

        QPushButton {
            background: #eef8ff;
            color: #102033;
            border: 1px solid #cfe6f7;
            border-radius: 8px;
            padding: 8px 14px;
            min-height: 24px;
            font-weight: 500;
        }

        QPushButton:hover {
            background: #e2f3ff;
            border-color: #b8dcf6;
        }

        QPushButton:pressed {
            background: #d6edff;
        }

        QPushButton:disabled {
            background: #f5f8fb;
            color: #9aa8b6;
            border-color: #dde7ef;
        }

        QPushButton[role="primary"] {
            background: #71c9ff;
            border-color: #5fbeff;
            color: #0b2237;
            font-weight: 600;
        }

        QPushButton[role="primary"]:hover {
            background: #60c2ff;
            border-color: #4cb8fa;
        }

        QPushButton[role="danger"] {
            background: #fff2f2;
            border-color: #f2b8b8;
            color: #b42318;
            font-weight: 600;
        }

        QPushButton[role="danger"]:hover {
            background: #ffe7e7;
            border-color: #eea7a7;
        }

        QPushButton[role="secondary"] {
            background: #f7fbff;
            border-color: #cfe3f5;
            color: #12324d;
        }

        QPushButton[role="secondary"]:hover {
            background: #edf7ff;
            border-color: #b9daf3;
        }

        QPushButton[jog="true"] {
            min-width: 58px;
            min-height: 34px;
            padding: 6px 8px;
        }

        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
        QComboBox,
        QTextEdit,
        QPlainTextEdit,
        QTableWidget {
            background: #fcfeff;
            color: #111827;
            border: 1px solid #cfe3f5;
            border-radius: 8px;
            padding: 6px 8px;
            min-height: 24px;
        }

        QScrollArea {
            background: transparent;
            border: none;
        }

        QLineEdit:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus,
        QComboBox:focus,
        QTextEdit:focus,
        QPlainTextEdit:focus,
        QTableWidget:focus {
            border: 1px solid #76c9ff;
        }

        QComboBox::drop-down,
        QSpinBox::down-button,
        QSpinBox::up-button,
        QDoubleSpinBox::down-button,
        QDoubleSpinBox::up-button {
            border: none;
            width: 20px;
            background: transparent;
        }

        QHeaderView::section {
            background: #f1f8ff;
            color: #16324b;
            border: none;
            border-right: 1px solid #dae8f3;
            border-bottom: 1px solid #dae8f3;
            padding: 8px 6px;
            font-weight: 600;
        }

        QTableWidget {
            gridline-color: #e2edf6;
            alternate-background-color: #f7fbff;
        }

        QProgressBar {
            background: #edf6fd;
            color: #0f172a;
            border: 1px solid #cfe3f5;
            border-radius: 8px;
            text-align: center;
            min-height: 20px;
            font-weight: 600;
        }

        QProgressBar::chunk {
            background: #6fc7ff;
            border-radius: 7px;
            margin: 1px;
        }

        QRadioButton, QCheckBox {
            spacing: 8px;
        }

        QRadioButton::indicator,
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }

        QRadioButton::indicator:unchecked,
        QCheckBox::indicator:unchecked {
            border: 1px solid #b7d8f0;
            background: #ffffff;
            border-radius: 8px;
        }

        QRadioButton::indicator:checked,
        QCheckBox::indicator:checked {
            border: 1px solid #71c9ff;
            background: #71c9ff;
            border-radius: 8px;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 3px;
        }

        QScrollBar::handle:vertical {
            background: #c8e4f7;
            border-radius: 5px;
            min-height: 28px;
        }

        QScrollBar::handle:vertical:hover {
            background: #9fd4f8;
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical,
        QScrollBar:horizontal,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: transparent;
            border: none;
            height: 0px;
            width: 0px;
        }

        QSplitter::handle {
            background: #d9eaf7;
        }

        QSplitter::handle:hover {
            background: #aad8f5;
        }

        QLabel[muted="true"] {
            color: #5e7186;
        }

        QLabel[chip="true"] {
            background: #f3fbff;
            border: 1px solid #d2e8f7;
            border-radius: 8px;
            padding: 6px 10px;
        }

        QLabel[sectionTitle="true"] {
            color: #124f82;
            font-weight: 600;
        }
        """
    )
