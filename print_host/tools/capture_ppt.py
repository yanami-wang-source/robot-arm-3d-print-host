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
    width_px, height_px = 1080, 620
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
        210,
        "print_host（PySide6 上位机）",
        [
            "总览、任务与预览、数字孪生",
            "机器与调试、材料与工艺、诊断",
            "串口连接、温控、运行摘要",
            "离线回放与答辩演示",
        ],
        QColor(236, 245, 255),
    )
    box(
        390,
        40,
        290,
        180,
        "FDM 打印机（Marlin 类）",
        [
            "接收 G-code 行流",
            "温度回读",
            "后续可接入真实打印硬件",
        ],
        QColor(255, 255, 255),
    )
    box(
        720,
        40,
        310,
        180,
        "外部切片器",
        [
            "PrusaSlicer / OrcaSlicer",
            "导出 .gcode",
            "供上位机自动回载与预览",
        ],
        QColor(255, 255, 255),
    )
    box(
        390,
        280,
        640,
        250,
        "机械臂控制链路 / 数字孪生",
        [
            "机械臂控制器串口通讯",
            "关节参数、DH 参数、TCP 与工作空间配置",
            "数字孪生姿态联动、轨迹预检与风险提示",
            "为后续真实限位、坐标标定和闭环控制预留接口",
        ],
        QColor(248, 250, 252),
    )

    painter.setPen(QPen(QColor(39, 125, 161), 3))
    painter.drawLine(340, 145, 390, 125)
    painter.drawLine(680, 125, 720, 125)
    painter.drawLine(540, 220, 540, 280)

    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))


def _prepare_demo_window() -> tuple[QApplication, object, QTabWidget]:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    from print_host.main_window import MainWindow

    root = _project_root()
    demo_dir = root / "demo_assets"
    gcode_path = demo_dir / "demo_solid_spatial_arch_beam.gcode"
    if not gcode_path.is_file():
        raise FileNotFoundError(f"缺少示例文件: {gcode_path}")

    window = MainWindow()
    window.resize(1360, 860)
    window.show()
    QApplication.processEvents()

    window._load_gcode_path(str(gcode_path))
    window._job.set_gcode_path(str(gcode_path))
    window._console.append_line("[演示] 已载入实心空间拱梁")
    window._console.append_line("[离线演示] 当前未连接 Marlin，将以软件回放模式执行 G-code。")
    window._on_marlin_line("T:210.3 / 220.0 B:59.9 / 60.0")
    QApplication.processEvents()

    if window._gcode_lines:
        mid_idx = max(0, len(window._gcode_lines) // 2)
        window._set_job_progress(52)
        window._preview.set_exec_line_index(mid_idx)
        state = window._set_simulated_twin_state(mid_idx, status="离线演示", source="离线仿真")
        if state is not None:
            window._current_segment_type = "挤出段" if state.extrusion else "空运行段"
            window._current_feed = state.feed
        window._printing = True
        window._paused = False
        window._offline_print = True
        window._append_event("开始离线 G-code 回放与数字孪生联动。")
    window._refresh_live_panels()

    tabs = window.findChild(QTabWidget)
    if tabs is None:
        raise RuntimeError("未找到主标签页。")

    return app, window, tabs


def main() -> int:
    root = _project_root()
    out_dir = root / "demo_assets" / "ppt_export"
    out_dir.mkdir(parents=True, exist_ok=True)

    from print_host.tools import robot_diagrams

    try:
        app, window, tabs = _prepare_demo_window()
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    tabs.setCurrentIndex(0)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "01_上位机_总览_运行摘要.png"))

    tabs.setCurrentIndex(1)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "02_上位机_任务与预览_离线回放.png"))

    tabs.setCurrentIndex(2)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "03_上位机_数字孪生_空间打印预览.png"))

    tabs.setCurrentIndex(3)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "04_上位机_机器与调试_六轴参数.png"))

    tabs.setCurrentIndex(4)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "05_上位机_材料与工艺_参数管理.png"))

    window._diagnostics.append_temperature(198.4, 58.6)
    window._diagnostics.append_temperature(203.8, 59.3)
    window._diagnostics.append_temperature(207.1, 60.0)
    window._diagnostics.append_motion(
        progress_pct=52.0,
        feed=1680.0,
        segment_type="挤出段",
        tcp_text="X118.2 Y-36.4 Z84.9 mm",
        joints_text="J1 18.4°  J2 42.2°  J3 -36.8° | J4 22.0°  J5 35.4°  J6 8.6°",
    )
    window._diagnostics.add_log("已载入实心空间拱梁演示轨迹。")
    window._diagnostics.add_log("离线回放运行中，数字孪生姿态与轨迹已同步。")
    window._diagnostics.add_log("当前版本可直接用于答辩展示与流程预演。")
    tabs.setCurrentIndex(5)
    QApplication.processEvents()
    window.grab().save(str(out_dir / "06_上位机_诊断_趋势与日志.png"))

    _render_software_overview_png(out_dir / "07_软件模块关系_示意图.png")
    robot_diagrams.main()

    tabs.setCurrentIndex(0)
    QApplication.processEvents()
    window.grab().save(str(root / "demo_assets" / "host_smoke_preview.png"))

    window.close()
    QApplication.processEvents()

    print(f"已写入（上位机）: {out_dir}")
    for file in sorted(out_dir.glob("*.png")):
        print(f"  - {file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
