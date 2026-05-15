from __future__ import annotations

from PySide6.QtCore import QObject

from .serial_io import LineSerialLink, MarlinSerialLink


class RobotArmSerialLink(LineSerialLink):
    """
    机械臂下位机 USART 文本协议（与 ``arm_motion.io.robot_client`` / 原 fdm_host 对齐）：
    每行以 \\n 结尾；不要依赖 \\r\\n；发送使用 ASCII。
    """

    def _frame_line(self, line: str) -> bytes:
        s = line.strip().replace("\r", "")
        if not s.endswith("\n"):
            s = s + "\n"
        return s.encode("ascii", errors="replace")

    def soft_reset(self) -> None:
        self.write_line("soft_reset")

    def hard_reset(self) -> None:
        self.write_line("hard_reset")

    def zero(self) -> None:
        self.write_line("zero")

    def auto_move(self, x: float, y: float, z: float) -> None:
        self.write_line(f"auto {x} {y} {z}")

    def rel_rotate(self, joint_id: int, degrees: float) -> None:
        self.write_line(f"rel_rotate {joint_id} {degrees}")


class PrintDeviceHub(QObject):
    """双路设备：独立 Marlin 板 + 机械臂串口，供主窗口集中挂信号与断开。"""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.marlin = MarlinSerialLink(self)
        self.robot = RobotArmSerialLink(self)

    def disconnect_all(self) -> None:
        self.marlin.disconnect_port()
        self.robot.disconnect_port()
