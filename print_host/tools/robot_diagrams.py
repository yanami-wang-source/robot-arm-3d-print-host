"""
生成机械臂控制部分答辩用示意图。

运行方式：
    python -m print_host.tools.robot_diagrams

输出目录：
    demo_assets/ppt_export/
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _out_dir() -> Path:
    out_dir = _project_root() / "demo_assets" / "ppt_export"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _title_font() -> QFont:
    font = QFont("Microsoft YaHei UI", 14)
    font.setBold(True)
    return font


def _body_font(size: int = 10, bold: bool = False) -> QFont:
    font = QFont("Microsoft YaHei UI", size)
    font.setBold(bold)
    return font


def _new_canvas(width: int, height: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(250, 252, 255))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(42, 54, 74), 2))
    return pixmap, painter


def _draw_box(
    painter: QPainter,
    rect: QRectF,
    title: str,
    lines: list[str],
    fill: QColor | None = None,
) -> None:
    painter.save()
    fill_color = fill or QColor(255, 255, 255)
    painter.setBrush(fill_color)
    painter.drawRoundedRect(rect, 10, 10)

    painter.setFont(_body_font(10, bold=True))
    painter.drawText(
        QRectF(rect.left() + 12, rect.top() + 10, rect.width() - 24, 24),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        title,
    )

    painter.setFont(_body_font(9))
    y = rect.top() + 40
    for line in lines:
        painter.drawText(
            QRectF(rect.left() + 12, y, rect.width() - 24, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            line,
        )
        y += 20
    painter.restore()


def _draw_arrow(painter: QPainter, x1: int, y1: int, x2: int, y2: int, label: str = "") -> None:
    painter.save()
    painter.setPen(QPen(QColor(39, 125, 161), 3))
    painter.drawLine(x1, y1, x2, y2)
    if label:
        painter.setFont(_body_font(9, bold=True))
        painter.drawText((x1 + x2) // 2 - 24, (y1 + y2) // 2 - 8, label)
    painter.restore()


def render_01_motor_topology(path: Path) -> None:
    pixmap, painter = _new_canvas(1180, 640)
    painter.setFont(_title_font())
    painter.drawText(24, 36, "机械臂电机控制拓扑")

    _draw_box(
        painter,
        QRectF(40, 80, 280, 210),
        "STM32F407 主控板",
        [
            "FreeRTOS 多任务调度",
            "CAN1 管理六轴驱动器",
            "USART1 接收上位机文本指令",
            "GPIO / EXTI 处理限位与急停",
            "可扩展 ESP8266 / MQTT",
        ],
        QColor(236, 245, 255),
    )

    painter.setFont(_body_font(10, bold=True))
    painter.drawText(340, 175, "CAN 总线")
    painter.setPen(QPen(QColor(39, 125, 161), 4))
    painter.drawLine(320, 190, 420, 190)
    painter.setPen(QPen(QColor(42, 54, 74), 2))

    driver_positions = [
        (450, 70),
        (610, 70),
        (770, 70),
        (450, 190),
        (610, 190),
        (770, 190),
    ]
    for idx, (x, y) in enumerate(driver_positions, start=1):
        _draw_box(
            painter,
            QRectF(x, y, 130, 90),
            f"关节 J{idx}",
            [
                "Emm V5 闭环步进",
                f"CAN 地址 {idx}",
                "位置 / 速度模式",
            ],
            QColor(255, 255, 255),
        )

    _draw_box(
        painter,
        QRectF(40, 350, 1060, 230),
        "说明",
        [
            "1. 上位机通过串口或离线回放产生运动指令，主控负责关节级执行。",
            "2. 位置模式用于到点、回零、联动轨迹；速度模式用于手柄远程控制与实时跟随。",
            "3. 驱动器、限位、状态回读共同构成后续实机闭环扩展基础。",
            "4. 该图适合在答辩时说明硬件连接关系与控制链路。",
        ],
        QColor(248, 250, 252),
    )

    painter.end()
    pixmap.save(str(path))


def render_02_software_flow(path: Path) -> None:
    pixmap, painter = _new_canvas(1100, 720)
    painter.setFont(_title_font())
    painter.drawText(24, 36, "固件任务与事件队列")

    _draw_box(
        painter,
        QRectF(40, 70, 260, 120),
        "串口接收层",
        [
            "USART1 中断 / DMA 接收",
            "解析上位机文本命令",
            "封装为命令事件",
        ],
        QColor(236, 245, 255),
    )
    _draw_box(
        painter,
        QRectF(360, 70, 300, 120),
        "命令服务层",
        [
            "robot_cmd_service",
            "参数解析与合法性检查",
            "生成运动或控制事件",
        ],
        QColor(255, 255, 255),
    )
    _draw_box(
        painter,
        QRectF(720, 70, 320, 120),
        "事件输入源",
        [
            "串口指令",
            "手柄远程控制",
            "限位 / 复位 / 同步命令",
        ],
        QColor(255, 255, 255),
    )

    _draw_arrow(painter, 300, 130, 360, 130)
    _draw_arrow(painter, 660, 130, 720, 130)

    _draw_box(
        painter,
        QRectF(220, 240, 460, 140),
        "event_queue",
        [
            "统一进入事件队列",
            "支持绝对运动、相对运动、自动轨迹、远程模式",
            "实现控制逻辑解耦",
        ],
        QColor(243, 248, 255),
    )
    _draw_arrow(painter, 450, 190, 450, 240)

    _draw_box(
        painter,
        QRectF(180, 430, 720, 220),
        "robot_control_task",
        [
            "根据事件类型选择位置模式或速度模式",
            "调用运动学求解、插补、PID 或关节目标换算",
            "输出到 Emm V5 驱动器",
            "更新机械臂状态，供上位机 / 反馈链路显示",
        ],
        QColor(255, 255, 255),
    )
    _draw_arrow(painter, 450, 380, 450, 430)

    _draw_box(
        painter,
        QRectF(40, 560, 120, 90),
        "运动学模块",
        [
            "DH 参数",
            "正逆解",
        ],
        QColor(255, 255, 255),
    )
    _draw_arrow(painter, 160, 605, 180, 560)

    painter.end()
    pixmap.save(str(path))


def render_03_uart_command_table(path: Path) -> None:
    pixmap, painter = _new_canvas(1000, 580)
    painter.setFont(_title_font())
    painter.drawText(24, 36, "USART1 文本指令表")

    headers = ["指令关键字", "参数形式", "作用"]
    rows = [
        ("remote_enable", "无", "进入远程控制模式"),
        ("remote_disable", "无", "退出远程控制模式"),
        ("remote_event", "6 个浮点量", "更新末端速度或姿态控制量"),
        ("rel_rotate", "joint_id, angle, speed", "执行单关节相对转动"),
        ("auto", "x y z ...", "触发末端自动运动"),
        ("hard_reset", "无", "执行硬件复位流程"),
        ("soft_reset", "无", "执行软件复位流程"),
        ("zero", "无", "关节当前位置清零"),
    ]

    x0 = 24
    y0 = 70
    col_w = [180, 280, 470]
    row_h = 46

    painter.setFont(_body_font(10, bold=True))
    x = x0
    for idx, header in enumerate(headers):
        painter.fillRect(x, y0, col_w[idx], row_h, QColor(236, 245, 255))
        painter.drawRect(x, y0, col_w[idx], row_h)
        painter.drawText(QRectF(x + 8, y0 + 8, col_w[idx] - 16, row_h - 16), header)
        x += col_w[idx]

    painter.setFont(_body_font(9))
    y = y0 + row_h
    for row in rows:
        x = x0
        for idx, cell in enumerate(row):
            painter.drawRect(x, y, col_w[idx], row_h)
            painter.drawText(
                QRectF(x + 8, y + 8, col_w[idx] - 16, row_h - 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                cell,
            )
            x += col_w[idx]
        y += row_h

    painter.end()
    pixmap.save(str(path))


def render_04_remote_joystick_flow(path: Path) -> None:
    pixmap, painter = _new_canvas(1040, 540)
    painter.setFont(_title_font())
    painter.drawText(24, 36, "手柄远程控制数据流")

    _draw_box(
        painter,
        QRectF(40, 80, 190, 120),
        "PC / 手柄输入",
        [
            "pygame 读取摇杆",
            "映射为速度量",
            "周期发送 remote_event",
        ],
        QColor(236, 245, 255),
    )
    _draw_box(
        painter,
        QRectF(290, 95, 120, 90),
        "USB / 串口",
        [
            "文本协议",
        ],
        QColor(255, 255, 255),
    )
    _draw_box(
        painter,
        QRectF(470, 80, 200, 120),
        "STM32 USART1",
        [
            "解析文本命令",
            "写入远程控制状态",
            "驱动事件流程",
        ],
        QColor(255, 255, 255),
    )
    _draw_box(
        painter,
        QRectF(730, 70, 250, 140),
        "g_remote_control",
        [
            "vx, vy, vz",
            "rx, ry",
            "限幅、积分、保护",
        ],
        QColor(255, 255, 255),
    )

    _draw_arrow(painter, 230, 140, 290, 140)
    _draw_arrow(painter, 410, 140, 470, 140)
    _draw_arrow(painter, 670, 140, 730, 140)

    _draw_box(
        painter,
        QRectF(180, 280, 720, 190),
        "remote 控制循环",
        [
            "按固定周期将末端速度积分为目标位姿",
            "调用逆运动学求解目标关节角",
            "PID / 速度控制输出到各轴电机",
            "逆解失败、超限或异常时触发保护",
        ],
        QColor(243, 248, 255),
    )

    painter.end()
    pixmap.save(str(path))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    out_dir = _out_dir()
    render_01_motor_topology(out_dir / "robot_01_电机与CAN拓扑.png")
    render_02_software_flow(out_dir / "robot_02_固件任务与事件队列.png")
    render_03_uart_command_table(out_dir / "robot_03_UART文本指令表.png")
    render_04_remote_joystick_flow(out_dir / "robot_04_手柄远程控制数据流.png")

    print(f"已写入: {out_dir}")
    for file in sorted(out_dir.glob("robot_*.png")):
        print(f"  - {file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

