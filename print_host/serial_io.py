from __future__ import annotations

import serial
from PySide6.QtCore import QObject, QThread, Signal


class SerialReadThread(QThread):
    line_received = Signal(str)

    def __init__(self, port: serial.Serial) -> None:
        super().__init__()
        self._port = port
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        buf = b""
        while self._running and self._port.is_open:
            try:
                chunk = self._port.read(256)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        text = line.decode("utf-8", errors="replace").strip("\r")
                    except Exception:
                        text = ""
                    if text:
                        self.line_received.emit(text)
            except Exception:
                break


class LineSerialLink(QObject):
    """
    通用「按行收发」串口封装：后台线程读行，主线程写。
    帧格式（编码、换行）由子类实现 _frame_line。
    """

    connected_changed = Signal(bool)
    line_received = Signal(str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ser: serial.Serial | None = None
        self._reader: SerialReadThread | None = None

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def _frame_line(self, line: str) -> bytes:
        raise NotImplementedError

    def connect_port(self, port: str, baudrate: int = 115200) -> bool:
        self.disconnect_port()
        try:
            self._ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.05,
                write_timeout=2.0,
            )
        except Exception as e:
            self.error.emit(str(e))
            self._ser = None
            self.connected_changed.emit(False)
            return False
        self._reader = SerialReadThread(self._ser)
        self._reader.line_received.connect(self.line_received.emit)
        self._reader.start()
        self.connected_changed.emit(True)
        return True

    def disconnect_port(self) -> None:
        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(3000)
            self._reader = None
        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
            except Exception:
                pass
            self._ser = None
        self.connected_changed.emit(False)

    def write_line(self, line: str) -> None:
        if not self.is_open or self._ser is None:
            return
        self._ser.write(self._frame_line(line))


class MarlinSerialLink(LineSerialLink):
    """Marlin 挤出/加热板：UTF-8，strip 后加换行（G-code）。"""

    def _frame_line(self, line: str) -> bytes:
        return (line.strip() + "\n").encode("utf-8", errors="replace")


SerialLink = MarlinSerialLink
