from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..slicer_config import SlicerHostConfig


class SlicerSettingsDialog(QDialog):
    def __init__(self, cfg: SlicerHostConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("外部切片器设置")
        self.resize(560, 180)

        self._exe = QLineEdit(cfg.console_exe)
        self._ini = QLineEdit(cfg.profile_ini)

        btn_exe = QPushButton("浏览...")
        btn_ini = QPushButton("浏览...")
        btn_exe.clicked.connect(self._browse_exe)
        btn_ini.clicked.connect(self._browse_ini)

        row_exe = QHBoxLayout()
        row_exe.addWidget(self._exe, stretch=1)
        row_exe.addWidget(btn_exe)
        row_ini = QHBoxLayout()
        row_ini.addWidget(self._ini, stretch=1)
        row_ini.addWidget(btn_ini)

        form = QFormLayout()
        form.addRow("控制台程序", row_exe)
        form.addRow("工艺配置 .ini（可选）", row_ini)

        hint = QLabel(
            "填写 PrusaSlicer / OrcaSlicer 的 *-console.exe 路径。\n"
            "如果已经从切片软件导出了工艺配置，也可以在这里一并指定。"
        )
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(buttons)

    def _browse_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择切片器控制台程序",
            str(Path("C:/Program Files")),
            "可执行文件 (*.exe);;所有文件 (*.*)",
        )
        if path:
            self._exe.setText(path)

    def _browse_ini(self) -> None:
        suggested = Path(__file__).resolve().parents[2] / "slicer_profiles"
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择导出的配置 .ini",
            str(suggested if suggested.exists() else Path.home()),
            "INI (*.ini);;所有文件 (*.*)",
        )
        if path:
            self._ini.setText(path)

    def result_config(self) -> SlicerHostConfig:
        return SlicerHostConfig(
            console_exe=self._exe.text().strip(),
            profile_ini=self._ini.text().strip(),
        )
