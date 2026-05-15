from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .device_link import PrintDeviceHub
from .marlin_parse import parse_temperature_line
from .profiles import HostProfileBundle, MachineProfile, MaterialProfile, ProcessProfile, ToolProfile
from .slicer_config import SlicerHostConfig
from .slicer_runner import build_slice_command, validate_console_exe
from .widgets import (
    ConnectionPanel,
    DashboardPage,
    DiagnosticsPanel,
    DigitalTwinPreview,
    ExtruderPanel,
    GcodeConsole,
    GcodeXyPreview,
    JogPanel,
    MachineProfilePanel,
    PrintJobPanel,
    ProcessProfilePanel,
    TemperaturePanel,
)
from .widgets.slicer_settings_dialog import SlicerSettingsDialog

_DEMO_GCODES = (
    ("平面基础示例", "sample_demo.gcode"),
    ("空间曲线", "demo_space_curve.gcode"),
    ("空间规则正方体", "demo_space_cube.gcode"),
    ("反重力斜向打印", "demo_antigravity_slope.gcode"),
    ("空间桁架桥", "demo_spatial_truss_bridge.gcode"),
    ("实心空间拱梁", "demo_solid_spatial_arch_beam.gcode"),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Print Host - 机械臂 3D 打印上位机")
        self.setObjectName("mainWindow")
        self._apply_responsive_window_geometry()
        self.statusBar().setSizeGripEnabled(False)

        self._profile_bundle = HostProfileBundle.load()
        self._recent_events: list[str] = []
        self._loaded_gcode_path: Path | None = None
        self._job_progress = 0
        self._current_segment_type = "待机"
        self._current_feed: float | None = None
        self._hotend_current: float | None = None
        self._hotend_target: float | None = None
        self._bed_current: float | None = None
        self._bed_target: float | None = None
        self._sim_joint_angles: list[float] | None = None

        self._devices = PrintDeviceHub(self)
        self._devices.marlin.line_received.connect(self._on_marlin_line)
        self._devices.marlin.error.connect(self._on_marlin_error)
        self._devices.marlin.connected_changed.connect(self._on_marlin_connected)
        self._devices.robot.line_received.connect(self._on_robot_line)
        self._devices.robot.error.connect(self._on_robot_error)
        self._devices.robot.connected_changed.connect(self._on_robot_connected)

        self._conn_marlin = ConnectionPanel(title="Marlin / 挤出与温控")
        self._conn_marlin.refresh_clicked.connect(self._conn_marlin.refresh_ports)
        self._conn_marlin.connect_clicked.connect(self._do_connect_marlin)
        self._conn_marlin.disconnect_clicked.connect(self._devices.marlin.disconnect_port)

        self._conn_robot = ConnectionPanel(title="机械臂控制器")
        self._conn_robot.refresh_clicked.connect(self._conn_robot.refresh_ports)
        self._conn_robot.connect_clicked.connect(self._do_connect_robot)
        self._conn_robot.disconnect_clicked.connect(self._devices.robot.disconnect_port)

        self._temp = TemperaturePanel()
        self._temp.set_hotend.connect(self._cmd_hotend)
        self._temp.set_bed.connect(self._cmd_bed)
        self._temp.fan_on.connect(self._cmd_fan_on)
        self._temp.fan_off.connect(lambda: self._send_raw("M107"))

        self._jog = JogPanel()
        self._jog.jog.connect(self._cmd_jog)
        self._jog.home.connect(self._cmd_home)
        self._jog.motors_off.connect(lambda: self._send_raw("M84"))

        self._extr = ExtruderPanel()
        self._extr.extrude.connect(self._cmd_extrude)
        self._extr.retract.connect(self._cmd_retract)

        self._job = PrintJobPanel()
        self._job.open_file.connect(self._load_gcode_path)
        self._job.request_external_slice.connect(self._pick_stl_and_slice)
        self._job.start_print.connect(self._print_start)
        self._job.pause_print.connect(self._print_pause)
        self._job.resume_print.connect(self._print_resume)
        self._job.cancel_print.connect(self._print_cancel)
        self._job.emergency_stop.connect(lambda: self._send_raw("M112"))

        self._console = GcodeConsole()
        self._console.send_line.connect(self._send_raw)

        self._preview = GcodeXyPreview()
        self._twin_preview = DigitalTwinPreview()
        self._twin_preview_job = DigitalTwinPreview()
        self._twin_preview_job.set_compact_mode(True)
        self._dashboard = DashboardPage()
        self._diagnostics = DiagnosticsPanel()
        self._machine_profile_panel = MachineProfilePanel()
        self._machine_profile_panel.profiles_saved.connect(self._save_machine_tool_profiles)
        self._process_profile_panel = ProcessProfilePanel()
        self._process_profile_panel.profiles_saved.connect(self._save_process_profiles)
        self._process_profile_panel.slicer_settings_requested.connect(self._open_slicer_settings)

        self._runtime_status_box = self._build_runtime_status_box()

        self._gcode_lines: list[str] = []
        self._gcode_index = 0
        self._printing = False
        self._paused = False
        self._offline_print = False
        self._demo_assets_dir = Path(__file__).resolve().parent.parent / "demo_assets"
        self._slice_output_path: Path | None = None

        self._slice_proc = QProcess(self)
        self._slice_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._slice_proc.readyReadStandardOutput.connect(self._on_slice_process_output)
        self._slice_proc.finished.connect(self._on_slice_process_finished)

        self._poll = QTimer(self)
        self._poll.setInterval(2000)
        self._poll.timeout.connect(lambda: self._send_raw("M105"))

        self._print_timer = QTimer(self)
        self._print_timer.setInterval(80)
        self._print_timer.timeout.connect(self._print_tick)

        self._build_ui()
        self._build_menu()
        self._apply_profile_bundle()
        self._append_event("工作副本已载入，可直接进行离线演示、轨迹预览和数字孪生联动。")
        self.statusBar().showMessage("就绪")
        self._refresh_live_panels()

    def _apply_responsive_window_geometry(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 800)
            self.setMinimumSize(980, 680)
            return

        available = screen.availableGeometry()
        width = min(1320, max(960, available.width() - 80))
        height = min(860, max(700, available.height() - 90))
        width = min(width, available.width())
        height = min(height, available.height())
        self.resize(width, height)
        self.setMinimumSize(min(980, width), min(680, height))

    def _wrap_scroll_page(self, widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setWidget(widget)
        return area

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(True)
        tabs.addTab(self._wrap_scroll_page(self._build_dashboard_page()), "总览")
        tabs.addTab(self._build_job_page(), "任务与预览")
        tabs.addTab(self._wrap_scroll_page(self._build_twin_page()), "数字孪生")
        tabs.addTab(self._wrap_scroll_page(self._build_machine_page()), "机器与调试")
        tabs.addTab(self._wrap_scroll_page(self._process_profile_panel), "材料与工艺")
        tabs.addTab(self._wrap_scroll_page(self._diagnostics), "诊断")

        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)
        sidebar_layout.addWidget(self._conn_marlin)
        sidebar_layout.addWidget(self._conn_robot)
        sidebar_layout.addWidget(self._temp)
        sidebar_layout.addWidget(self._runtime_status_box)
        sidebar_layout.addStretch(1)
        sidebar_scroll = self._wrap_scroll_page(sidebar)
        sidebar_scroll.setMinimumWidth(340)
        sidebar_scroll.setMaximumWidth(412)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.addWidget(tabs)
        splitter.addWidget(sidebar_scroll)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([max(700, self.width() - 388), 388])

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(splitter)
        self.setCentralWidget(root)

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(self._build_dashboard_actions_box())
        layout.addWidget(self._dashboard, 1)
        return page

    def _build_dashboard_actions_box(self) -> QGroupBox:
        box = QGroupBox("快速操作")
        layout = QHBoxLayout(box)
        layout.setSpacing(8)

        btn_open = QPushButton("打开 G-code")
        btn_open.setProperty("role", "secondary")
        btn_open.clicked.connect(self._pick_gcode_from_dialog)

        btn_demo = QPushButton("载入空间桁架桥")
        btn_demo.setProperty("role", "secondary")
        btn_demo.clicked.connect(
            lambda: self._load_demo_gcode("空间桁架桥", "demo_spatial_truss_bridge.gcode")
        )

        btn_start = QPushButton("开始离线回放")
        btn_start.setProperty("role", "primary")
        btn_start.clicked.connect(self._print_start)

        btn_preset = QPushButton("同步当前工艺预设")
        btn_preset.setProperty("role", "secondary")
        btn_preset.clicked.connect(self._apply_process_presets)

        for button in (btn_open, btn_demo, btn_start, btn_preset):
            layout.addWidget(button)
        layout.addStretch(1)
        return box

    def _build_job_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(self._job)

        preview_tabs = QTabWidget()
        preview_tabs.setDocumentMode(True)
        preview_tabs.addTab(self._preview, "G-code XY 预览")
        preview_tabs.addTab(self._twin_preview_job, "数字孪生预览")

        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)
        split.addWidget(preview_tabs)
        split.addWidget(self._console)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 2)
        split.setSizes([520, 240])
        layout.addWidget(split, 1)
        return page

    def _build_twin_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        hint = QLabel("左键旋转，滚轮缩放，右键或中键平移，双击可复位视角。")
        hint.setProperty("muted", True)
        layout.addWidget(hint)
        layout.addWidget(self._twin_preview, 1)
        return page

    def _build_machine_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(self._jog)
        left_layout.addWidget(self._extr)
        left_layout.addWidget(self._build_machine_macros_box())
        left_layout.addStretch(1)

        layout.addWidget(left, 2)
        layout.addWidget(self._machine_profile_panel, 3)
        return page

    def _build_machine_macros_box(self) -> QGroupBox:
        box = QGroupBox("常用宏")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        btn_sync = QPushButton("同步材料工艺到温控面板")
        btn_sync.setProperty("role", "primary")
        btn_sync.clicked.connect(self._apply_process_presets)

        btn_query_pos = QPushButton("查询当前位置 M114")
        btn_query_pos.setProperty("role", "secondary")
        btn_query_pos.clicked.connect(lambda: self._send_raw("M114"))

        btn_query_fw = QPushButton("查询固件信息 M115")
        btn_query_fw.setProperty("role", "secondary")
        btn_query_fw.clicked.connect(lambda: self._send_raw("M115"))

        btn_save_eeprom = QPushButton("保存 EEPROM M500")
        btn_save_eeprom.setProperty("role", "secondary")
        btn_save_eeprom.clicked.connect(lambda: self._send_raw("M500"))

        btn_cooldown = QPushButton("全部降温")
        btn_cooldown.setProperty("role", "secondary")
        btn_cooldown.clicked.connect(self._cooldown_all)

        for button in (btn_sync, btn_query_pos, btn_query_fw, btn_save_eeprom, btn_cooldown):
            layout.addWidget(button)
        return box

    def _build_runtime_status_box(self) -> QGroupBox:
        box = QGroupBox("实时状态")
        self._runtime_labels = {
            "任务": QLabel("-"),
            "模式": QLabel("待机"),
            "轨迹段": QLabel("-"),
            "TCP": QLabel("-"),
            "预检": QLabel("-"),
        }
        for label in self._runtime_labels.values():
            label.setWordWrap(True)
            label.setProperty("chip", True)

        self._runtime_progress = QProgressBar()
        self._runtime_progress.setRange(0, 100)
        self._runtime_progress.setValue(0)

        form = QFormLayout(box)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        for key, label in self._runtime_labels.items():
            form.addRow(key, label)
        form.addRow("总进度", self._runtime_progress)
        return box

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        open_action = QAction("打开 G-code...", self)
        open_action.triggered.connect(self._pick_gcode_from_dialog)
        file_menu.addAction(open_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        machine_menu = self.menuBar().addMenu("机器")
        for text, cmd in [
            ("固件信息 M115", "M115"),
            ("当前位置 M114", "M114"),
            ("保存 EEPROM M500", "M500"),
            ("回零 XYZ", "G28 XYZ"),
        ]:
            action = QAction(text, self)
            action.triggered.connect(lambda _, c=cmd: self._send_raw(c))
            machine_menu.addAction(action)

        slicer_menu = self.menuBar().addMenu("切片器")
        slicer_action = QAction("路径与配置设置...", self)
        slicer_action.triggered.connect(self._open_slicer_settings)
        slicer_menu.addAction(slicer_action)

        demo_menu = self.menuBar().addMenu("演示轨迹")
        for title, filename in _DEMO_GCODES:
            action = QAction(title, self)
            action.triggered.connect(lambda _, t=title, f=filename: self._load_demo_gcode(t, f))
            demo_menu.addAction(action)

    def _pick_gcode_from_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 G-code",
            str(Path.home()),
            "G-code (*.gcode *.gco *.nc *.txt);;所有文件 (*.*)",
        )
        if path:
            self._job.set_gcode_path(path)
            self._load_gcode_path(path)

    def _apply_profile_bundle(self) -> None:
        self._machine_profile_panel.set_profiles(self._profile_bundle.machine, self._profile_bundle.tool)
        self._process_profile_panel.set_profiles(self._profile_bundle.material, self._profile_bundle.process)
        self._set_twin_nominal_profiles(self._profile_bundle.machine, self._profile_bundle.tool)
        self._apply_process_presets()

    def _all_twin_previews(self) -> tuple[DigitalTwinPreview, DigitalTwinPreview]:
        return (self._twin_preview, self._twin_preview_job)

    def _set_twin_nominal_profiles(self, machine: MachineProfile, tool: ToolProfile) -> None:
        for twin in self._all_twin_previews():
            twin.set_nominal_profiles(machine, tool)

    def _load_twin_gcode_lines(self, lines: list[str]) -> None:
        for twin in self._all_twin_previews():
            twin.load_gcode_lines(lines)

    def _clear_twin_previews(self) -> None:
        for twin in self._all_twin_previews():
            twin.clear()

    def _set_twin_exec_line_index(self, idx: int | None) -> None:
        for twin in self._all_twin_previews():
            twin.set_exec_line_index(idx)

    def _show_twin_completed_result(self) -> None:
        for twin in self._all_twin_previews():
            twin.show_completed_result()

    def _set_twin_robot_state_from_line(self, line: str) -> None:
        for twin in self._all_twin_previews():
            twin.set_robot_state_from_line(line)

    def _set_simulated_twin_state(
        self,
        idx: int | None,
        *,
        status: str,
        source: str,
    ):
        state = self._twin_preview.set_simulated_robot_state(idx, status=status, source=source)
        self._twin_preview_job.set_simulated_robot_state(idx, status=status, source=source)
        return state

    def _apply_process_presets(self) -> None:
        material = self._profile_bundle.material
        self._temp.set_presets(
            hotend=material.nozzle_temp_c,
            bed=material.bed_temp_c,
            fan=material.fan_pwm,
        )
        self._extr.set_presets(
            length_mm=material.retract_len_mm,
            speed_mm_min=material.retract_speed_mm_min,
        )
        self._append_event("已将材料 / 工艺预设同步到温控与挤出面板。")
        self._refresh_live_panels()

    def _save_machine_tool_profiles(self, machine: MachineProfile, tool: ToolProfile) -> None:
        self._profile_bundle.machine = machine
        self._profile_bundle.tool = tool
        self._profile_bundle.save()
        self._set_twin_nominal_profiles(machine, tool)
        self.statusBar().showMessage("机器与工具参数已保存", 3000)
        self._append_event("机器参数、关节限位和 TCP 名义值已更新。")
        self._refresh_live_panels()

    def _save_process_profiles(self, material: MaterialProfile, process: ProcessProfile) -> None:
        self._profile_bundle.material = material
        self._profile_bundle.process = process
        self._profile_bundle.save()
        self._apply_process_presets()
        self.statusBar().showMessage("材料与工艺参数已保存", 3000)
        self._append_event("材料、温度、速度和流量工艺参数已更新。")
        self._refresh_live_panels()

    def _append_event(self, text: str) -> None:
        self._recent_events.append(text)
        self._recent_events = self._recent_events[-60:]
        self._dashboard.set_recent_events(self._recent_events)
        self._diagnostics.add_log(text)

    def _nominal_home_joints(self) -> list[float]:
        return [axis.home_deg for axis in self._profile_bundle.machine.axes]

    def _do_connect_marlin(self) -> None:
        port = self._conn_marlin.selected_port()
        if not port:
            QMessageBox.warning(self, "连接", "请先选择 Marlin 串口。")
            return
        ok = self._devices.marlin.connect_port(port, self._conn_marlin.baudrate())
        if ok:
            self.statusBar().showMessage(f"Marlin 已连接: {port}")
            self._append_event(f"Marlin 已连接到 {port}。")
            self._poll.start()
        else:
            self.statusBar().showMessage("Marlin 连接失败")
            self._append_event("Marlin 连接失败。")
        self._refresh_live_panels()

    def _do_connect_robot(self) -> None:
        port = self._conn_robot.selected_port()
        if not port:
            QMessageBox.warning(self, "连接", "请先选择机械臂控制器串口。")
            return
        ok = self._devices.robot.connect_port(port, self._conn_robot.baudrate())
        if ok:
            self.statusBar().showMessage(f"机械臂控制器已连接: {port}")
            self._append_event(f"机械臂控制器已连接到 {port}。")
        else:
            self.statusBar().showMessage("机械臂控制器连接失败")
            self._append_event("机械臂控制器连接失败。")
        self._refresh_live_panels()

    def _on_marlin_connected(self, ok: bool) -> None:
        self._conn_marlin.set_connected(ok)
        if not ok:
            self._poll.stop()
        self._diagnostics.set_connection_states(self._devices.marlin.is_open, self._devices.robot.is_open)
        self._refresh_live_panels()

    def _on_robot_connected(self, ok: bool) -> None:
        self._conn_robot.set_connected(ok)
        self._diagnostics.set_connection_states(self._devices.marlin.is_open, self._devices.robot.is_open)
        self._refresh_live_panels()

    def _on_marlin_error(self, msg: str) -> None:
        self._console.append_line(f"[Marlin][错误] {msg}")
        self._append_event(f"[Marlin][错误] {msg}")
        self.statusBar().showMessage(msg, 5000)

    def _on_robot_error(self, msg: str) -> None:
        self._console.append_line(f"[机械臂][错误] {msg}")
        self._append_event(f"[机械臂][错误] {msg}")
        self.statusBar().showMessage(msg, 5000)

    def _on_marlin_line(self, line: str) -> None:
        self._console.append_line(line)
        hot_cur, hot_tgt, bed_cur, bed_tgt = parse_temperature_line(line)
        if hot_cur is not None or bed_cur is not None:
            self._hotend_current, self._hotend_target = hot_cur, hot_tgt
            self._bed_current, self._bed_target = bed_cur, bed_tgt
            self._temp.update_display(hot_cur, hot_tgt, bed_cur, bed_tgt)
            self._diagnostics.append_temperature(hot_cur, bed_cur)
            self._refresh_live_panels()

    def _on_robot_line(self, line: str) -> None:
        self._console.append_line(f"[机械臂] {line}")
        self._set_twin_robot_state_from_line(line)
        self._refresh_live_panels()

    def _send_raw(self, cmd: str) -> None:
        if not self._devices.marlin.is_open:
            self._console.append_line("[Marlin 未连接] 指令未发送")
            return
        self._devices.marlin.write_line(cmd)

    def _print_control(self, cmd: str, offline_note: str) -> None:
        if self._devices.marlin.is_open:
            self._send_raw(cmd)
        else:
            self._console.append_line(f"[离线演示] {offline_note}")

    def _cmd_hotend(self, target: int) -> None:
        self._send_raw(f"M104 S{target}")
        self._append_event(f"喷嘴目标温度设为 {target} °C。")

    def _cmd_bed(self, target: int) -> None:
        self._send_raw(f"M140 S{target}")
        self._append_event(f"热床目标温度设为 {target} °C。")

    def _cmd_fan_on(self, pwm: int) -> None:
        self._send_raw(f"M106 S{pwm}")
        self._append_event(f"风扇 PWM 设为 {pwm}。")

    def _cooldown_all(self) -> None:
        for command in ("M104 S0", "M140 S0", "M107"):
            self._send_raw(command)
        self._append_event("已发送全部降温与关闭风扇命令。")

    def _cmd_jog(self, axis: str, delta_mm: float) -> None:
        self._send_raw("G91")
        self._send_raw(f"G0 {axis}{delta_mm:+.3f} F3000")
        self._send_raw("G90")
        self._append_event(f"点动 {axis} 轴 {delta_mm:+.3f} mm。")

    def _cmd_home(self, axes: str) -> None:
        self._send_raw(f"G28 {axes}")
        self._append_event(f"发送回零命令: {axes}。")

    def _cmd_extrude(self, mm: float, speed: int) -> None:
        self._send_raw("M83")
        self._send_raw(f"G1 E{mm:.3f} F{speed}")
        self._append_event(f"正向挤出 {mm:.2f} mm，速度 {speed} mm/min。")

    def _cmd_retract(self, mm: float, speed: int) -> None:
        self._send_raw("M83")
        self._send_raw(f"G1 E{-mm:.3f} F{speed}")
        self._append_event(f"回抽 {mm:.2f} mm，速度 {speed} mm/min。")

    def _open_slicer_settings(self) -> None:
        cfg = SlicerHostConfig.load()
        dialog = SlicerSettingsDialog(cfg, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.result_config().save()
            self.statusBar().showMessage("切片器路径配置已保存", 3000)
            self._append_event("外部切片器路径与配置已更新。")

    def _pick_stl_and_slice(self) -> None:
        if self._slice_proc.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "切片", "已有切片任务正在运行，请稍候。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模型文件（交给外部切片器）",
            str(Path.home()),
            "模型 (*.stl *.STL *.3mf *.STEP *.step *.stp);;所有文件 (*.*)",
        )
        if path:
            self._run_external_slice(Path(path))

    def _run_external_slice(self, model_path: Path) -> None:
        cfg = SlicerHostConfig.load()
        if not validate_console_exe(cfg.console_exe):
            QMessageBox.warning(
                self,
                "切片器",
                "请先在菜单“切片器 -> 路径与配置设置...”中指定 prusa-slicer-console.exe "
                "或 orca-slicer-console.exe。",
            )
            return
        out_gcode = model_path.with_suffix(".gcode")
        self._slice_output_path = out_gcode
        cmd = build_slice_command(cfg, model_path, out_gcode)
        self._console.append_line("[切片] 命令: " + " ".join(cmd))
        self._job.set_slice_busy(True)
        self.statusBar().showMessage("正在调用外部切片器...")
        self._append_event(f"开始外部切片: {model_path.name}")
        self._slice_proc.setWorkingDirectory(str(model_path.resolve().parent))
        self._slice_proc.setProgram(cmd[0])
        self._slice_proc.setArguments(cmd[1:])
        self._slice_proc.start()

    def _on_slice_process_output(self) -> None:
        data = bytes(self._slice_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._console.append_line(f"[切片] {line}")

    def _on_slice_process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._job.set_slice_busy(False)
        out = self._slice_output_path
        self._slice_output_path = None
        if exit_code != 0:
            QMessageBox.warning(
                self,
                "切片失败",
                f"外部进程退出码 {exit_code}。请查看终端里以 [切片] 开头的日志。",
            )
            self.statusBar().showMessage("切片失败")
            self._append_event(f"外部切片失败，退出码 {exit_code}。")
            return
        if out is not None and out.is_file():
            self._job.set_gcode_path(str(out))
            self._load_gcode_path(str(out))
            self.statusBar().showMessage(f"已生成并载入 {out.name}")
            self._append_event(f"外部切片完成并已载入 {out.name}。")
            return
        QMessageBox.warning(
            self,
            "切片",
            f"未找到输出文件：\n{out}\n如果切片器将 G-code 输出到了其他路径，请手动打开。",
        )
        self.statusBar().showMessage("未找到切片输出文件")
        self._append_event("切片进程完成，但未找到输出 G-code 文件。")

    def _load_demo_gcode(self, title: str, filename: str) -> None:
        path = self._demo_assets_dir / filename
        if not path.is_file():
            QMessageBox.warning(self, "演示轨迹", f"未找到演示文件：\n{path}")
            return
        self._job.set_gcode_path(str(path))
        self._load_gcode_path(str(path))
        self._console.append_line(f"[演示] 已载入 {title}: {path.name}")
        self.statusBar().showMessage(f"已载入演示轨迹: {title}")

    def _load_gcode_path(self, path: str) -> None:
        self._gcode_lines = []
        self._gcode_index = 0
        self._sim_joint_angles = None
        self._loaded_gcode_path = Path(path)
        try:
            text = self._loaded_gcode_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "文件", str(exc))
            return

        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith(";"):
                continue
            if ";" in stripped:
                stripped = stripped.split(";", 1)[0].strip()
            if stripped:
                self._gcode_lines.append(stripped)

        self._set_job_progress(0)
        if self._gcode_lines:
            self._preview.load_gcode_lines(self._gcode_lines)
            self._load_twin_gcode_lines(self._gcode_lines)
            self._append_event(
                f"已载入 G-code: {self._loaded_gcode_path.name}，有效指令 {len(self._gcode_lines)} 行。"
            )
        else:
            self._preview.clear()
            self._clear_twin_previews()
            self._append_event(f"{self._loaded_gcode_path.name} 中未发现有效 G-code 运动指令。")
        self.statusBar().showMessage(f"已载入 {len(self._gcode_lines)} 行有效 G-code")
        self._refresh_live_panels()

    def _set_job_progress(self, pct: int) -> None:
        self._job_progress = max(0, min(100, pct))
        self._job.set_progress(self._job_progress)
        self._runtime_progress.setValue(self._job_progress)

    def _print_start(self) -> None:
        if not self._gcode_lines:
            QMessageBox.warning(self, "打印", "请先打开 G-code 文件。")
            return
        self._offline_print = not self._devices.marlin.is_open
        self._gcode_index = 0
        self._paused = False
        self._printing = True
        self._sim_joint_angles = self._nominal_home_joints()
        self._set_job_progress(0)
        self._preview.set_exec_line_index(None)
        self._set_twin_exec_line_index(None)
        self._print_timer.start()
        if self._offline_print:
            self._console.append_line("[离线演示] 当前未连接 Marlin，将以软件回放模式执行 G-code。")
            self.statusBar().showMessage("离线演示运行中")
            self._append_event("开始离线 G-code 回放与数字孪生联动。")
        else:
            self.statusBar().showMessage("打印运行中")
            self._append_event("开始联机打印。")
        self._refresh_live_panels()

    def _print_pause(self) -> None:
        self._paused = True
        self._print_timer.stop()
        self._print_control("M25", "暂停测试回放")
        self.statusBar().showMessage("已暂停")
        self._append_event("任务已暂停。")
        self._refresh_live_panels()

    def _print_resume(self) -> None:
        if not self._printing:
            return
        self._paused = False
        self._print_timer.start()
        self._print_control("M24", "继续测试回放")
        self.statusBar().showMessage("继续打印")
        self._append_event("任务继续运行。")
        self._refresh_live_panels()

    def _print_cancel(self) -> None:
        self._printing = False
        self._paused = False
        self._offline_print = False
        self._sim_joint_angles = None
        self._print_timer.stop()
        self._preview.set_exec_line_index(None)
        self._set_twin_exec_line_index(None)
        self._print_control("M410", "停止测试回放")
        self.statusBar().showMessage("已请求停止")
        self._append_event("任务已停止。")
        self._refresh_live_panels()

    def _sync_motion_preview(self, exec_idx: int) -> None:
        self._preview.set_exec_line_index(exec_idx)
        if self._devices.robot.is_open and not self._offline_print:
            self._set_twin_exec_line_index(exec_idx)
            self._refresh_live_panels()
            return

        state = self._set_simulated_twin_state(
            exec_idx,
            status="离线演示" if self._offline_print else "打印预览",
            source="离线仿真" if self._offline_print else "G-code 驱动",
        )
        if state is None:
            self._refresh_live_panels()
            return

        prev = self._sim_joint_angles or self._nominal_home_joints()
        current = list(state.joints_deg)
        self._sim_joint_angles = current
        self._current_segment_type = "挤出段" if state.extrusion else "空运行段"
        self._current_feed = state.feed

        motion_line = f"[机械臂名义状态] idx={exec_idx} {self._current_segment_type}"
        if state.feed is not None:
            motion_line += f" F={state.feed:.0f}"
        self._console.append_line(motion_line)

        tcp = state.tcp_mm
        self._console.append_line(f"[TCP] X={tcp[0]:.1f} Y={tcp[1]:.1f} Z={tcp[2]:.1f}")

        tick_s = max(0.001, self._print_timer.interval() / 1000.0)
        motor_parts: list[str] = []
        for axis_index, (cur, old, axis) in enumerate(
            zip(current, prev, self._profile_bundle.machine.axes),
            start=1,
        ):
            delta = cur - old
            if abs(delta) < 0.05:
                motor_parts.append(f"J{axis_index} 保持")
                continue
            motor_dir = axis.positive_dir if delta >= 0 else ("CW" if axis.positive_dir == "CCW" else "CCW")
            steps = int(round(abs(delta) * axis.steps_per_deg))
            motor_rpm = abs(delta) / tick_s * axis.reduction_ratio / 6.0
            motor_parts.append(f"J{axis_index} {delta:+.1f}° {motor_dir} {steps}步 {motor_rpm:.1f}rpm")
        self._console.append_line("[电机名义输出] " + " | ".join(motor_parts))
        self._refresh_live_panels()

    def _print_tick(self) -> None:
        if not self._printing or self._paused:
            return
        total = len(self._gcode_lines)
        if total == 0:
            self._print_timer.stop()
            return
        if self._gcode_index >= total:
            self._printing = False
            was_offline = self._offline_print
            self._offline_print = False
            self._print_timer.stop()
            self._set_job_progress(100)
            self._preview.set_exec_line_index(None)
            self._show_twin_completed_result()
            if was_offline:
                self._console.append_line(
                    "[离线演示] 回放完成，可在数字孪生窗口中旋转、缩放并观察打印结果。"
                )
                self._append_event("离线打印回放完成，结果已保留在数字孪生预览中。")
            else:
                self._append_event("联机打印流程执行完成。")
            self.statusBar().showMessage("打印完成")
            self._refresh_live_panels()
            return

        line = self._gcode_lines[self._gcode_index]
        self._gcode_index += 1
        if self._devices.marlin.is_open:
            self._devices.marlin.write_line(line)
        else:
            self._console.append_line(f"[离线 G-code] {line}")
        self._set_job_progress(int(100 * self._gcode_index / total))
        self._sync_motion_preview(self._gcode_index - 1)

    def _refresh_live_panels(self) -> None:
        twin_snapshot = self._twin_preview.runtime_snapshot()
        joints = twin_snapshot.get("joints_deg")
        self._machine_profile_panel.set_joint_angles(joints if isinstance(joints, list) else None)

        if twin_snapshot.get("segment_type"):
            self._current_segment_type = str(twin_snapshot["segment_type"])
        if twin_snapshot.get("feed") is not None:
            self._current_feed = float(twin_snapshot["feed"])

        marlin_status = "已连接" if self._devices.marlin.is_open else "未连接"
        robot_status = "已连接" if self._devices.robot.is_open else "未连接"
        if self._paused:
            mode = "已暂停"
        elif self._printing and self._offline_print:
            mode = "离线演示"
        elif self._printing:
            mode = "联机打印"
        else:
            mode = "待机"

        job_name = self._loaded_gcode_path.name if self._loaded_gcode_path else "未加载任务"
        feed_text = "-" if self._current_feed is None else f"{self._current_feed:.0f} mm/min"
        tcp = twin_snapshot.get("tcp_mm")
        tcp_text = "-" if not tcp else f"X{tcp[0]:.1f} Y{tcp[1]:.1f} Z{tcp[2]:.1f} mm"
        joint_values = joints if isinstance(joints, list) else []
        joints_a = (
            "-"
            if len(joint_values) < 3
            else f"J1 {joint_values[0]:.1f}°  J2 {joint_values[1]:.1f}°  J3 {joint_values[2]:.1f}°"
        )
        joints_b = (
            "-"
            if len(joint_values) < 6
            else f"J4 {joint_values[3]:.1f}°  J5 {joint_values[4]:.1f}°  J6 {joint_values[5]:.1f}°"
        )

        material = self._profile_bundle.material
        process = self._profile_bundle.process
        machine = self._profile_bundle.machine

        snapshot = {
            "marlin_status": marlin_status,
            "robot_status": robot_status,
            "mode": mode,
            "job_name": job_name,
            "progress": f"{self._job_progress}%",
            "precheck": twin_snapshot.get("precheck_text", "待载入 G-code"),
            "precheck_level": twin_snapshot.get("precheck_level", "neutral"),
            "material_name": material.name,
            "process_name": process.name,
            "temperature_targets": f"{material.nozzle_temp_c} / {material.bed_temp_c} °C",
            "fan": f"{material.fan_pwm} PWM",
            "speed_pair": f"{process.print_speed_mm_s:.1f} / {process.travel_speed_mm_s:.1f} mm/s",
            "override_pair": f"{process.flow_override_pct}% / {process.speed_override_pct}%",
            "segment_type": self._current_segment_type,
            "line_index": twin_snapshot.get("line_index", "-"),
            "feed": feed_text,
            "tcp": tcp_text,
            "joints_a": joints_a,
            "joints_b": joints_b,
            "limit_summary": twin_snapshot.get("limit_text", "名义限位：暂未触发"),
            "limit_level": twin_snapshot.get("limit_level", "neutral"),
            "source": twin_snapshot.get("source", "预览"),
            "build_plate": (
                f"{machine.build_plate_mm[0]:.0f} x {machine.build_plate_mm[1]:.0f} x "
                f"{machine.build_plate_mm[2]:.0f} mm"
            ),
            "base_origin": (
                f"X{machine.base_origin_mm[0]:.1f} "
                f"Y{machine.base_origin_mm[1]:.1f} "
                f"Z{machine.base_origin_mm[2]:.1f} mm"
            ),
            "calibration_todo": "真实限位角、关节零位、平台坐标系、喷嘴偏置",
            "next_action": "先离线验证，再根据实物更新限位角与 TCP。",
        }
        self._dashboard.update_snapshot(snapshot)

        self._runtime_labels["任务"].setText(job_name)
        self._runtime_labels["模式"].setText(mode)
        self._runtime_labels["轨迹段"].setText(self._current_segment_type)
        self._runtime_labels["TCP"].setText(tcp_text)
        self._runtime_labels["预检"].setText(str(snapshot["precheck"]))

        self._diagnostics.set_connection_states(self._devices.marlin.is_open, self._devices.robot.is_open)
        self._diagnostics.append_motion(
            progress_pct=float(self._job_progress),
            feed=self._current_feed,
            segment_type=self._current_segment_type,
            tcp_text=tcp_text,
            joints_text=f"{joints_a} | {joints_b}",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._print_timer.stop()
        self._poll.stop()
        if self._slice_proc.state() != QProcess.ProcessState.NotRunning:
            self._slice_proc.kill()
            self._slice_proc.waitForFinished(5000)
        self._devices.disconnect_all()
        super().closeEvent(event)
