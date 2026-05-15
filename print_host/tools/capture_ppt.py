"""
导出答辩 PPT 可直接使用的上位机截图与软件关系图。

运行方式：
    python -m print_host.tools.capture_ppt

输出目录：
    demo_assets/ppt_export/
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QTabWidget


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _render_software_overview_png(path: Path) -> None:
    width_px, height_px = 1000, 560
    pixmap = QPixmap(width_px, height_px)
    pixmap.fill(QColor(250, 252, 255))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(42, 54, 74), 2))

    title_font = QFont("Microsoft YaHei UI", 14)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(24, 36, "上位机软件模块关系图")

    body_font = QFont("Microsoft YaHei UI", 10)
    bold_font = QFont("Microsoft YaHei UI", 10)
    bold_font.setBold(True)

    def box(x: int, y: int, w: int, h: int, title: str, lines: list[str], fill: QColor) -> None:
        painter.save()
        painter.setBrush(fill)
        painter.drawRoundedRect(x, y, w, h, 10, 10)
        painter.setFont(bold_font)
        painter.drawText(QRectF(x + 12, y + 10, w - 24, 22), title)
        painter.setFont(body_font)
        line_y = y + 42
        for line in lines:
            painter.drawText(QRectF(x + 12, line_y, w - 24, 20), Qt.AlignmentFlag.AlignLeft, line)
            line_y += 20
        painter.restore()

    box(
        40,
        40,
        300,
        200,
        "print_host（PySide6 上位机）",
        [
            "串口连接、G-code 终端",
            "温度、点动、挤出控制",
            "G-code XY 预览",
            "数字孪生预览与离线回放",
        ],
        QColor(236, 245, 255),
    )
    box(
        380,
        40,
        280,
        160,
        "FDM 打印机（Marlin 类）",
        [
            "接收 G-code 行流",
            "温度回读",
            "后续可接入真实打印硬件",
        ],
        QColor(255, 255, 255),
    )
    box(
        700,
        40,
        260,
        160,
        "外部切片器",
        [
            "PrusaSlicer / OrcaSlicer",
            "导出 .gcode",
            "供上位机载入与回放",
        ],
        QColor(255, 255, 255),
    )
    box(
        380,
        260,
        580,
        220,
        "机械臂控制链路",
        [
            "机械臂控制器串口通讯",
            "关节参数、DH 参数、工艺参数",
            "数字孪生姿态联动",
            "为后续实机闭环与打印验证预留接口",
        ],
        QColor(248, 250, 252),
    )

    painter.setPen(QPen(QColor(39, 125, 161), 3))
    painter.drawLine(340, 140, 380, 120)
    painter.drawLine(660, 120, 700, 120)
    painter.drawLine(520, 200, 520, 260)

    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))


def main() -> int:
    root = _project_root()
    demo_dir = root / "demo_assets"
    gcode_path = demo_dir / "sample_demo.gcode"
    out_dir = demo_dir / "ppt_export"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not gcode_path.is_file():
        print(f"缺少示例文件: {gcode_path}", file=sys.stderr)
        return 1

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    from print_host.main_window import MainWindow
    from print_host.tools import robot_diagrams

    window = MainWindow()
    window.resize(1100, 720)
    window.show()
    QApplication.processEvents()

    window._load_gcode_path(str(gcode_path))
    window._job.set_gcode_path(str(gcode_path))
    window._conn.set_connected(True)
    window._console.append_line("ok")
    window._on_serial_line("T:210.3 / 220.0 B:59.9 / 60.0")
    window._console.append_line("echo:busy processing")
    QApplication.processEvents()

    window.grab().save(str(out_dir / "01_上位机_打印与终端_演示数据.png"))

    tabs = window.findChild(QTabWidget)
    if tabs is not None:
        tabs.setCurrentIndex(1)
        QApplication.processEvents()
        window.grab().save(str(out_dir / "02_上位机_手动与挤出.png"))
        tabs.setCurrentIndex(0)

    line_count = len(window._gcode_lines)
    if line_count > 0:
        window._preview.set_exec_line_index(max(0, line_count // 2))
        QApplication.processEvents()
        window.grab().save(str(out_dir / "03_上位机_XY预览_模拟打印进度.png"))
        window._preview.set_exec_line_index(None)

    _render_software_overview_png(out_dir / "04_软件模块关系_示意图.png")
    robot_diagrams.main()

    window.close()
    QApplication.processEvents()

    print(f"已写入（上位机）: {out_dir}")
    for file in sorted(out_dir.glob("*.png")):
        print(f"  - {file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

