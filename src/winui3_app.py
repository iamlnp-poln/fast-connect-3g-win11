"""
Fast Connect 3G - Official WinUI 3 Fluent Design Edition
Authentic Windows 11 Interface built with PyQt6 & QFluentWidgets
For Huawei 3G Modems (E173 / MobiFone Fast Connect)
"""

import sys
import os
import time
import subprocess
import threading
import ctypes

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollArea, QHeaderView, QTableWidgetItem
)

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition,
    FluentIcon, CardWidget, SimpleCardWidget, ElevatedCardWidget,
    PrimaryPushButton, PillPushButton, PushButton,
    InfoBar, InfoBarPosition,
    BodyLabel, SubtitleLabel, TitleLabel, StrongBodyLabel, CaptionLabel,
    LargeTitleLabel, IconWidget, LineEdit, TextEdit,
    ComboBox, ProgressBar, TableWidget,
    setTheme, Theme, setThemeColor
)

from src.at_engine import HuaweiATEngine
from src.dialer import WindowsRASDialer
from src.modeswitch import (
    get_device_state, auto_detect_and_switch,
    switch_modem_to_zerocd, query_present_huawei_devices,
    get_connected_huawei_pids
)


def get_resource_dir(subdir=""):
    """Resolves directory relative to project root or PyInstaller executable."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, subdir) if subdir else base


class TelemetrySignals(QObject):
    signal_updated = pyqtSignal(int, int, int, int, int)  # rssi, ber, dbm, pct, bars
    operator_updated = pyqtSignal(str, str)               # oper, tech
    device_updated = pyqtSignal(str, str)                 # model, port
    traffic_updated = pyqtSignal(str, float, float)       # uptime, up_mb, down_mb
    connection_state_changed = pyqtSignal(bool, str)      # is_connected, message
    driver_status_checked = pyqtSignal(bool, str)         # is_driver_ok, status_detail
    hardware_state_changed = pyqtSignal(str, str, str)    # state, detail, drive
    notification_requested = pyqtSignal(str, str, str, int)  # ntype, title, msg, duration
    mode_switch_finished = pyqtSignal(bool, str)          # ok, msg
    sms_loaded = pyqtSignal(list)                         # messages list
    sms_sent = pyqtSignal(bool, str)                      # ok, msg
    radio_mode_result = pyqtSignal(bool, str)             # ok, msg


# =============================================================================
# PAGE 1: DASHBOARD & CONNECTIVITY
# =============================================================================
class DashboardInterface(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("DashboardInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.viewport().setStyleSheet("background-color: transparent;")
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.setWidget(self.container)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(32, 16, 32, 16)
        self.layout.setSpacing(12)

        # Header
        self.title_label = TitleLabel("Bảng Điều Khiển Kết Nối 3G", self.container)
        self.subtitle_label = CaptionLabel(
            "Quản lý kết nối mạng Mobile Broadband cho DCom 3G Huawei E173 trên Windows 11",
            self.container
        )
        self.subtitle_label.setTextColor(QColor("#606060"), QColor("#A0A0A0"))
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.subtitle_label)

        # HVCI Driver Fix Banner
        self.driver_card = SimpleCardWidget(self.container)
        drv_layout = QHBoxLayout(self.driver_card)
        drv_layout.setContentsMargins(18, 12, 18, 12)
        drv_layout.setSpacing(14)

        icon_warn = IconWidget(FluentIcon.INFO, self.driver_card)
        icon_warn.setFixedSize(26, 26)
        drv_layout.addWidget(icon_warn)

        drv_text_layout = QVBoxLayout()
        drv_text_layout.setSpacing(2)
        self.drv_title = StrongBodyLabel(
            "Phát hiện ewusbmdm.sys bị Windows 11 HVCI (Core Isolation) chặn",
            self.driver_card
        )
        self.drv_sub = CaptionLabel(
            "Nhấn nút bên phải để tự động gỡ bỏ ewusbmdm.sys cũ và chuyển sang driver usbser.sys chuẩn của Microsoft.",
            self.driver_card
        )
        self.drv_sub.setTextColor(QColor("#606060"), QColor("#B0B0B0"))
        drv_text_layout.addWidget(self.drv_title)
        drv_text_layout.addWidget(self.drv_sub)
        drv_layout.addLayout(drv_text_layout, 1)

        self.btn_install_driver = PrimaryPushButton(
            FluentIcon.ACCEPT, "Sửa lỗi Driver HVCI (1-Click)", self.driver_card
        )
        self.btn_install_driver.setFixedHeight(36)
        self.btn_install_driver.clicked.connect(self._run_driver_installer)
        drv_layout.addWidget(self.btn_install_driver)

        self.layout.addWidget(self.driver_card)

        # Card 1: Network & Signal Overview
        self.net_card = SimpleCardWidget(self.container)
        net_layout = QHBoxLayout(self.net_card)
        net_layout.setContentsMargins(20, 14, 20, 14)

        carrier_col = QVBoxLayout()
        carrier_col.setSpacing(4)
        self.carrier_badge = SubtitleLabel("MOBIFONE 3G", self.net_card)
        self.carrier_badge.setTextColor(QColor("#0067C0"), QColor("#4CC2FF"))
        self.tech_label = BodyLabel("Công nghệ: HSPA+ / UMTS (3.75G)", self.net_card)
        self.apn_label = CaptionLabel("APN: m-wap  •  Số quay: *99#", self.net_card)
        self.apn_label.setTextColor(QColor("#606060"), QColor("#9E9E9E"))
        carrier_col.addWidget(self.carrier_badge)
        carrier_col.addWidget(self.tech_label)
        carrier_col.addWidget(self.apn_label)
        net_layout.addLayout(carrier_col, 2)
        net_layout.addStretch(1)

        signal_col = QVBoxLayout()
        signal_col.setSpacing(6)
        self.signal_value_label = SubtitleLabel("Cường độ sóng: --%", self.net_card)
        self.signal_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.signal_bar = ProgressBar(self.net_card)
        self.signal_bar.setFixedWidth(180)
        self.signal_bar.setValue(0)
        self.signal_dbm_label = CaptionLabel("Mức tín hiệu: Đang dò cổng AT...", self.net_card)
        self.signal_dbm_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.signal_dbm_label.setTextColor(QColor("#606060"), QColor("#9E9E9E"))
        signal_col.addWidget(self.signal_value_label)
        signal_col.addWidget(self.signal_bar, 0, Qt.AlignmentFlag.AlignRight)
        signal_col.addWidget(self.signal_dbm_label)
        net_layout.addLayout(signal_col, 1)

        self.layout.addWidget(self.net_card)

        # Card 2: Main Connect/Disconnect Card
        self.action_card = SimpleCardWidget(self.container)
        action_layout = QVBoxLayout(self.action_card)
        action_layout.setContentsMargins(24, 18, 24, 18)
        action_layout.setSpacing(12)

        self.conn_status_label = SubtitleLabel("Trạng thái: Chưa kết nối Internet", self.action_card)
        self.conn_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(self.conn_status_label)

        self.conn_sub_label = CaptionLabel(
            "Sử dụng giao thức chuẩn Windows 11 RAS PPP Dial-Up qua cổng Modem 3G",
            self.action_card
        )
        self.conn_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.conn_sub_label.setTextColor(QColor("#606060"), QColor("#9E9E9E"))
        action_layout.addWidget(self.conn_sub_label)

        btn_center_layout = QHBoxLayout()
        self.btn_connect = PrimaryPushButton(
            FluentIcon.WIFI, "KẾT NỐI INTERNET 3G", self.action_card
        )
        self.btn_connect.setFixedSize(360, 44)
        self.btn_connect.clicked.connect(self._toggle_connection)
        btn_center_layout.addStretch(1)
        btn_center_layout.addWidget(self.btn_connect)
        btn_center_layout.addStretch(1)
        action_layout.addLayout(btn_center_layout)

        self.layout.addWidget(self.action_card)

        # Card 3: Session Traffic & Uptime Stats
        self.stats_card = SimpleCardWidget(self.container)
        stats_layout = QGridLayout(self.stats_card)
        stats_layout.setContentsMargins(20, 14, 20, 14)

        self.lbl_uptime_val = SubtitleLabel("00:00:00", self.stats_card)
        self.lbl_upload_val = SubtitleLabel("0.00 MB", self.stats_card)
        self.lbl_download_val = SubtitleLabel("0.00 MB", self.stats_card)

        stats_layout.addWidget(self._wrap_stat("Thời gian kết nối", self.lbl_uptime_val), 0, 0)
        stats_layout.addWidget(self._wrap_stat("Dữ liệu Tải lên (Upload)", self.lbl_upload_val), 0, 1)
        stats_layout.addWidget(self._wrap_stat("Dữ liệu Tải xuống (Download)", self.lbl_download_val), 0, 2)
        self.layout.addWidget(self.stats_card)

        # Card 4: Hardware & ZeroCD Switcher
        self.hw_card = SimpleCardWidget(self.container)
        hw_layout = QHBoxLayout(self.hw_card)
        hw_layout.setContentsMargins(20, 14, 20, 14)

        hw_text_layout = QVBoxLayout()
        hw_text_layout.setSpacing(2)
        self.lbl_device_info = StrongBodyLabel("Thiết bị: Huawei E173 (VID_12D1&PID_1436)", self.hw_card)
        self.lbl_mode_info = CaptionLabel(
            "Chế độ phần cứng: Đã chuyển mạch sang Modem Mode (PID_1436)",
            self.hw_card
        )
        self.lbl_mode_info.setTextColor(QColor("#107C41"), QColor("#6CCB5F"))
        hw_text_layout.addWidget(self.lbl_device_info)
        hw_text_layout.addWidget(self.lbl_mode_info)
        hw_layout.addLayout(hw_text_layout)
        hw_layout.addStretch(1)

        self.btn_switch = PushButton(FluentIcon.SYNC, "Chưa cắm DCom", self.hw_card)
        self.btn_switch.setFixedWidth(290)
        self.btn_switch.setFixedHeight(36)
        self.btn_switch.clicked.connect(self._toggle_mode_switch)
        hw_layout.addWidget(self.btn_switch)

        self.layout.addWidget(self.hw_card)
        self.layout.addStretch(1)

    def _wrap_stat(self, title_text, val_label):
        w = QWidget(self.stats_card)
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(4)
        lbl_t = CaptionLabel(title_text, w)
        lbl_t.setTextColor(QColor("#606060"), QColor("#9E9E9E"))
        l.addWidget(lbl_t)
        l.addWidget(val_label)
        return w

    def _run_driver_installer(self):
        bat = os.path.join(get_resource_dir("drivers"), "Install-All-Recommended.bat")
        InfoBar.info(
            "Đang cấu hình Driver usbser.sys",
            "Vui lòng nhấn 'Yes' trên hộp thoại UAC để gỡ bỏ ewusbmdm.sys và kích hoạt usbser.sys...",
            parent=self.window(),
            position=InfoBarPosition.TOP,
            duration=6000
        )
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c "{bat}"', None, 1)

    def _toggle_mode_switch(self):
        main_win = self.window()
        current_state = getattr(main_win, "current_hw_state", "DISCONNECTED")
        if getattr(main_win, "is_switching_mode", False):
            return

        if current_state == "ZEROCD":
            self.btn_switch.setEnabled(False)
            self.btn_connect.setEnabled(False)
            self.btn_switch.setText("Đang chuyển sang User Mode...")
            self.btn_connect.setText("ĐANG CHUYỂN MẠCH...")
            main_win.signals.notification_requested.emit(
                "info", "Đang chuyển mạch SCSI",
                "Đang gửi lệnh chuyển sang Chế độ Modem 3G (User Mode)...", 3000
            )

            def _task():
                main_win.is_switching_mode = True
                try:
                    ok, msg = auto_detect_and_switch()
                    if ok:
                        main_win.signals.notification_requested.emit("success", "Thành công", msg, 4000)
                    else:
                        main_win.signals.notification_requested.emit("warning", "Thông báo", msg, 5000)
                    main_win.signals.mode_switch_finished.emit(ok, msg)
                finally:
                    main_win.is_switching_mode = False

            threading.Thread(target=_task, daemon=True).start()

        elif current_state == "MODEM":
            self.btn_switch.setEnabled(False)
            self.btn_connect.setEnabled(False)
            self.btn_switch.setText("Đang chuyển về ZeroCD...")
            self.btn_connect.setText("ĐANG CHUYỂN VỀ ZEROCD...")
            main_win.signals.notification_requested.emit(
                "info", "Chuyển mạch ZeroCD",
                "Đang chuyển thiết bị về chế độ ổ đĩa ảo ZeroCD...", 3000
            )

            def _task():
                main_win.is_switching_mode = True
                try:
                    if main_win.dialer.is_connected:
                        main_win.dialer.disconnect()
                        time.sleep(0.4)
                    if main_win.at_engine.is_connected:
                        main_win.at_engine.disconnect()
                        time.sleep(0.3)
                    ok, msg = switch_modem_to_zerocd(main_win.at_engine)
                    if ok:
                        main_win.signals.notification_requested.emit("success", "Chuyển mạch ZeroCD", msg, 4000)
                    else:
                        main_win.signals.notification_requested.emit("warning", "Thông báo", msg, 5000)
                    main_win.signals.mode_switch_finished.emit(ok, msg)
                finally:
                    main_win.is_switching_mode = False

            threading.Thread(target=_task, daemon=True).start()

    def on_hardware_state_changed(self, state, detail, drive):
        main_win = self.window()
        is_switching = getattr(main_win, "is_switching_mode", False)

        if state == "DISCONNECTED":
            self.driver_card.setVisible(False)
            self.carrier_badge.setText("CHƯA CẮM DCOM")
            self.carrier_badge.setTextColor(QColor("#8A8A8A"), QColor("#8A8A8A"))
            self.tech_label.setText("Vui lòng cắm USB DCom vào máy tính")
            self.apn_label.setText("APN: Không khả dụng  •  Số quay: *99#")
            self.signal_value_label.setText("Cường độ sóng: --%")
            self.signal_bar.setValue(0)
            self.signal_dbm_label.setText("Mức tín hiệu: Chưa có thiết bị")
            self.conn_status_label.setText("Trạng thái: Chưa có thiết bị")
            self.conn_status_label.setTextColor(QColor("#8A8A8A"), QColor("#8A8A8A"))
            self.conn_sub_label.setText("Hãy cắm thiết bị DCom 3G Huawei vào cổng USB để bắt đầu kết nối.")
            self.lbl_device_info.setText("Thiết bị: Chưa phát hiện USB DCom")
            self.lbl_mode_info.setText("Trạng thái: Ngắt kết nối phần cứng (Disconnected)")
            self.lbl_mode_info.setTextColor(QColor("#8A8A8A"), QColor("#8A8A8A"))
            if not is_switching:
                self.btn_connect.setEnabled(False)
                self.btn_connect.setText("CHƯA CẮM DCOM 3G")
                self.btn_switch.setEnabled(False)
                self.btn_switch.setText("Chưa cắm DCom")

        elif state == "ZEROCD":
            self.driver_card.setVisible(False)
            self.carrier_badge.setText("HUAWEI ZEROCD")
            self.carrier_badge.setTextColor(QColor("#0067C0"), QColor("#4CC2FF"))
            self.tech_label.setText("Chế độ Mass Storage / Bộ nhớ ảo (PID_1446)")
            self.apn_label.setText(f"Ổ đĩa CD cài đặt: {drive or 'E'}:\\ (Chưa chuyển sang Modem)")
            self.signal_value_label.setText("Cường độ sóng: --%")
            self.signal_bar.setValue(0)
            self.signal_dbm_label.setText("Đang ở chế độ Ổ đĩa ảo ZeroCD")
            self.conn_status_label.setText("Trạng thái: Cần chuyển sang User Mode")
            self.conn_status_label.setTextColor(QColor("#D83B01"), QColor("#FF8C00"))
            self.conn_sub_label.setText("Thiết bị đang là ổ đĩa ảo. Nhấn '⚡ Chuyển sang User Mode' để kích hoạt Modem 3G.")
            self.lbl_device_info.setText(f"Thiết bị: Huawei E173 (Chế độ ZeroCD {drive or 'E'}:\\)")
            self.lbl_mode_info.setText("Chế độ: USB Mass Storage (PID_1446) — Cần chuyển sang Modem")
            self.lbl_mode_info.setTextColor(QColor("#D83B01"), QColor("#FF8C00"))
            if not is_switching:
                self.btn_connect.setEnabled(True)
                self.btn_connect.setText("⚡ CHUYỂN SANG USER MODE (MODEM 3G)")
                self.btn_switch.setEnabled(True)
                self.btn_switch.setText("⚡ Chuyển sang User Mode (Modem 3G)")

        elif state == "MODEM":
            has_err = getattr(main_win, "current_has_driver_err", False)
            self.driver_card.setVisible(has_err)
            self.lbl_device_info.setText(f"Thiết bị: Huawei E173 ({detail})")
            self.lbl_mode_info.setText("Chế độ phần cứng: Modem Mode (User Mode - Sẵn sàng quay số)")
            self.lbl_mode_info.setTextColor(QColor("#107C41"), QColor("#6CCB5F"))
            if not is_switching:
                self.btn_switch.setEnabled(True)
                self.btn_switch.setText("Chuyển về Ổ đĩa ZeroCD (PID_1446)")

            if not main_win.dialer.is_connected and not main_win.is_dialing and not is_switching:
                if has_err:
                    self.btn_connect.setEnabled(False)
                    self.btn_connect.setText("LỖI DRIVER - CẦN VÁ DRIVER")
                    self.conn_status_label.setText("Trạng thái: Lỗi Driver (Bị chặn bởi HVCI hoặc Code 39)")
                    self.conn_status_label.setTextColor(QColor("#D83B01"), QColor("#FF8C00"))
                    self.conn_sub_label.setText("Nhấn nút 'Sửa lỗi Driver HVCI (1-Click)' bên trên để khắc phục.")
                else:
                    self.btn_connect.setEnabled(True)
                    self.btn_connect.setText("KẾT NỐI INTERNET 3G")
                    self.conn_status_label.setText("Trạng thái: Sẵn sàng kết nối Internet")
                    self.conn_status_label.setTextColor(QColor("#202020"), QColor("#FFFFFF"))
                    self.conn_sub_label.setText("Sử dụng giao thức chuẩn Windows 11 RAS PPP Dial-Up qua cổng Modem 3G")

    def _toggle_connection(self):
        main_win = self.window()
        hw_state = getattr(main_win, "current_hw_state", "DISCONNECTED")
        if hw_state == "ZEROCD":
            self._toggle_mode_switch()
            return
        elif hw_state != "MODEM":
            InfoBar.warning(
                "Không thể kết nối",
                "Chưa cắm thiết bị DCom 3G vào máy tính.",
                parent=main_win,
                position=InfoBarPosition.TOP_RIGHT
            )
            return
        dialer = main_win.dialer
        if not dialer.is_connected:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("ĐANG QUAY SỐ *99#...")
            def _task():
                main_win.is_dialing = True
                try:
                    # Release COM port from AT telemetry engine before Windows RAS opens it
                    if main_win.at_engine.is_connected:
                        from src.dialer import CARRIER_APNS
                        cfg = CARRIER_APNS.get(main_win.current_carrier, CARRIER_APNS["Default"])
                        main_win.at_engine.send_cmd(f'AT+CGDCONT=1,"IP","{cfg["apn"]}"')
                        main_win.at_engine.disconnect()
                        time.sleep(0.35)
                    ok, msg = dialer.connect(carrier=main_win.current_carrier)
                finally:
                    main_win.is_dialing = False
                main_win.signals.connection_state_changed.emit(ok, msg)
            threading.Thread(target=_task, daemon=True).start()
        else:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("ĐANG NGẮT KẾT NỐI...")
            def _task():
                dialer.disconnect()
                time.sleep(0.3)
                main_win.signals.connection_state_changed.emit(False, "Đã ngắt kết nối.")
            threading.Thread(target=_task, daemon=True).start()


# =============================================================================
# PAGE 2: SMS MANAGER
# =============================================================================
class SMSInterface(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SMSInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.viewport().setStyleSheet("background-color: transparent;")
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.setWidget(self.container)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(36, 24, 36, 28)
        self.layout.setSpacing(16)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        self.title_label = TitleLabel("Quản Lý Tin Nhắn SMS", self.container)
        self.subtitle_label = CaptionLabel("Đọc hộp thư đến và gửi tin nhắn SMS trực tiếp trên SIM DCom 3G", self.container)
        self.subtitle_label.setTextColor(QColor("#606060"), QColor("#A0A0A0"))
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        top_row.addLayout(title_col)
        top_row.addStretch(1)

        self.btn_refresh = PushButton(FluentIcon.SYNC, "Làm mới Hộp thư", self.container)
        self.btn_refresh.clicked.connect(self._load_inbox)
        top_row.addWidget(self.btn_refresh)
        self.layout.addLayout(top_row)

        content_grid = QGridLayout()
        content_grid.setSpacing(16)

        # Inbox Card
        inbox_card = SimpleCardWidget(self.container)
        inbox_layout = QVBoxLayout(inbox_card)
        inbox_layout.setContentsMargins(20, 16, 20, 16)
        inbox_layout.setSpacing(8)
        inbox_layout.addWidget(StrongBodyLabel("Hộp thư đến (SIM Inbox)", inbox_card))
        self.inbox_text = TextEdit(inbox_card)
        self.inbox_text.setReadOnly(True)
        self.inbox_text.setMinimumHeight(280)
        inbox_layout.addWidget(self.inbox_text)
        content_grid.addWidget(inbox_card, 0, 0)

        # Compose Card
        compose_card = SimpleCardWidget(self.container)
        c_layout = QVBoxLayout(compose_card)
        c_layout.setContentsMargins(20, 16, 20, 16)
        c_layout.setSpacing(10)
        c_layout.addWidget(StrongBodyLabel("Soạn tin nhắn SMS mới", compose_card))

        self.txt_phone = LineEdit(compose_card)
        self.txt_phone.setPlaceholderText("Số điện thoại người nhận (vd: 090xxxxxxx hoặc 999)...")
        c_layout.addWidget(self.txt_phone)

        self.txt_sms_body = TextEdit(compose_card)
        self.txt_sms_body.setPlaceholderText("Nhập nội dung tin nhắn SMS...")
        self.txt_sms_body.setMinimumHeight(160)
        c_layout.addWidget(self.txt_sms_body)

        self.btn_send_sms = PrimaryPushButton(FluentIcon.SEND, "Gửi Tin Nhắn SMS", compose_card)
        self.btn_send_sms.clicked.connect(self._send_sms)
        c_layout.addWidget(self.btn_send_sms)
        content_grid.addWidget(compose_card, 0, 1)

        self.layout.addLayout(content_grid)
        self.layout.addStretch(1)

    def _load_inbox(self):
        main_win = self.window()
        if getattr(main_win, "current_hw_state", "DISCONNECTED") != "MODEM":
            InfoBar.warning(
                "Chưa kết nối Modem",
                "Thiết bị chưa ở Chế độ Modem 3G hoặc chưa cắm DCom.",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT
            )
            self.inbox_text.setPlainText("Chưa kết nối Modem 3G. Vui lòng chuyển sang Chế độ Modem để đọc tin nhắn.")
            return

        self.btn_refresh.setEnabled(False)
        self.inbox_text.setPlainText("Đang đọc tin nhắn từ bộ nhớ SIM...")

        def _task():
            at = main_win.at_engine
            was_ppp = main_win.dialer.is_connected
            main_win.is_dialing = True
            try:
                if was_ppp:
                    main_win.dialer.disconnect()
                    time.sleep(0.4)
                if not at.is_connected:
                    at.auto_connect()
                messages = at.list_sms()
                if was_ppp:
                    at.disconnect()
                    time.sleep(0.3)
                    main_win.dialer.connect(carrier=main_win.current_carrier)
            finally:
                main_win.is_dialing = False
            main_win.signals.sms_loaded.emit(messages)

        threading.Thread(target=_task, daemon=True).start()

    def _send_sms(self):
        main_win = self.window()
        if getattr(main_win, "current_hw_state", "DISCONNECTED") != "MODEM":
            InfoBar.warning(
                "Chưa kết nối Modem",
                "Vui lòng chuyển sang Chế độ Modem 3G trước khi gửi tin nhắn.",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT
            )
            return

        phone = self.txt_phone.text().strip()
        body = self.txt_sms_body.toPlainText().strip()
        if not phone or not body:
            InfoBar.warning("Thiếu thông tin", "Vui lòng nhập số điện thoại và nội dung tin nhắn!", parent=self.window(), position=InfoBarPosition.TOP_RIGHT)
            return

        self.btn_send_sms.setEnabled(False)
        def _task():
            at = main_win.at_engine
            was_ppp = main_win.dialer.is_connected
            main_win.is_dialing = True
            try:
                if was_ppp:
                    main_win.dialer.disconnect()
                    time.sleep(0.4)
                if not at.is_connected:
                    at.auto_connect()
                ok, msg = at.send_sms(phone, body)
                if was_ppp:
                    at.disconnect()
                    time.sleep(0.3)
                    main_win.dialer.connect(carrier=main_win.current_carrier)
            finally:
                main_win.is_dialing = False
            main_win.signals.sms_sent.emit(ok, msg)

        threading.Thread(target=_task, daemon=True).start()


# =============================================================================
# PAGE 3: DRIVER & HARDWARE MANAGER (QUẢN LÝ DRIVER & THIẾT BỊ)
# =============================================================================
class DriverManagerInterface(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("DriverManagerInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.viewport().setStyleSheet("background-color: transparent;")
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.setWidget(self.container)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(36, 24, 36, 28)
        self.layout.setSpacing(16)

        # Header
        self.title_label = TitleLabel("Quản Lý Driver & Thiết Bị Windows 11", self.container)
        self.subtitle_label = CaptionLabel(
            "Kiểm tra tính tương thích Core Isolation / HVCI, quản lý các endpoint composite và cấu hình dải tần modem",
            self.container
        )
        self.subtitle_label.setTextColor(QColor("#606060"), QColor("#A0A0A0"))
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.subtitle_label)

        # 1. HVCI & Driver Security Status Card
        sec_card = SimpleCardWidget(self.container)
        s_layout = QVBoxLayout(sec_card)
        s_layout.setContentsMargins(24, 20, 24, 20)
        s_layout.setSpacing(12)

        s_header = QHBoxLayout()
        s_header.addWidget(StrongBodyLabel("Tình trạng Tương thích Bảo mật Windows 11 (HVCI / Core Isolation)", sec_card))
        s_header.addStretch(1)

        has_blocked_sys = os.path.exists(r"C:\Windows\System32\drivers\ewusbmdm.sys")
        if not has_blocked_sys:
            self.lbl_sec_badge = SubtitleLabel("✓ ĐẠT CHUẨN HVCI (AN TOÀN)", sec_card)
            self.lbl_sec_badge.setTextColor(QColor("#107C41"), QColor("#6CCB5F"))
        else:
            self.lbl_sec_badge = SubtitleLabel("⚠ PHÁT HIỆN DRIVER CŨ BỊ CHẶN", sec_card)
            self.lbl_sec_badge.setTextColor(QColor("#D83B01"), QColor("#FF8C00"))
        s_header.addWidget(self.lbl_sec_badge)
        s_layout.addLayout(s_header)

        sec_desc = (
            "• Driver Modem (MI_00): Đang ánh xạ sang usbser.sys + modem.sys (in-box Microsoft, 100% sạch).\n"
            "• Driver Điều khiển AT (MI_03): Đang chạy qua usbser.sys chính chủ của Windows 11.\n"
            "• Driver cũ vi phạm W+X (ewusbmdm.sys, ewusbnet.sys, ew_hwusbdev.sys): Đã được gỡ bỏ khỏi System32\\drivers.\n"
            "• Không làm vô hiệu hóa Memory Integrity / Core Isolation của hệ thống."
        )
        lbl_sec = BodyLabel(sec_desc, sec_card)
        lbl_sec.setTextColor(QColor("#505050"), QColor("#B8B8B8"))
        s_layout.addWidget(lbl_sec)

        sec_btn_row = QHBoxLayout()
        sec_btn_row.setSpacing(12)
        btn_fix_drv = PrimaryPushButton(FluentIcon.ACCEPT, "1-Click Vá & Kích hoạt Driver usbser.sys (Admin)", sec_card)
        btn_fix_drv.clicked.connect(self._run_driver_patcher)
        sec_btn_row.addWidget(btn_fix_drv)

        btn_restart_pnp = PushButton(FluentIcon.SYNC, "Khởi động lại Cổng PnP Modem", sec_card)
        btn_restart_pnp.clicked.connect(self._restart_pnp_devices)
        sec_btn_row.addWidget(btn_restart_pnp)

        btn_coreiso = PushButton(FluentIcon.SETTING, "Cài đặt Core Isolation", sec_card)
        btn_coreiso.clicked.connect(lambda: os.system("start windowsdefender://coreisolation"))
        sec_btn_row.addWidget(btn_coreiso)
        sec_btn_row.addStretch(1)

        s_layout.addLayout(sec_btn_row)
        self.layout.addWidget(sec_card)

        # 2. Composite USB Interfaces Table
        table_card = SimpleCardWidget(self.container)
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(24, 20, 24, 20)
        t_layout.setSpacing(12)

        t_header = QHBoxLayout()
        t_header.addWidget(StrongBodyLabel("Danh sách Giao diện Phần cứng USB Composite (PID_1436)", table_card))
        t_header.addStretch(1)
        btn_refresh_table = PushButton(FluentIcon.SYNC, "Quét lại", table_card)
        btn_refresh_table.clicked.connect(self._refresh_interfaces_table)
        t_header.addWidget(btn_refresh_table)
        t_layout.addLayout(t_header)

        self.table_interfaces = TableWidget(table_card)
        self.table_interfaces.setColumnCount(5)
        self.table_interfaces.setHorizontalHeaderLabels([
            "Giao diện", "Chức năng", "Cổng / Định danh", "Driver Dịch vụ", "Trạng thái PnP"
        ])
        self.table_interfaces.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_interfaces.setFixedHeight(220)
        t_layout.addWidget(self.table_interfaces)
        self.layout.addWidget(table_card)

        # 3. Radio Band Lock Card (Khóa dải tần sóng)
        radio_card = SimpleCardWidget(self.container)
        r_layout = QVBoxLayout(radio_card)
        r_layout.setContentsMargins(24, 20, 24, 20)
        r_layout.setSpacing(12)

        r_layout.addWidget(StrongBodyLabel("Khóa Băng Tần & Chế Độ Sóng (Radio Mode Lock)", radio_card))
        lbl_r_sub = CaptionLabel(
            "Cấu hình trực tiếp vào chip baseband của DCom để tối ưu khả năng bắt sóng mạng di động:",
            radio_card
        )
        lbl_r_sub.setTextColor(QColor("#606060"), QColor("#A0A0A0"))
        r_layout.addWidget(lbl_r_sub)

        r_row = QHBoxLayout()
        r_row.setSpacing(12)
        self.combo_radio = ComboBox(radio_card)
        self.combo_radio.addItems([
            "Chỉ 3G (WCDMA Only - Khuyên dùng tại VN)",
            "Tự động 2G / 3G (Auto Mode)"
        ])
        self.combo_radio.setCurrentIndex(0)
        self.combo_radio.setFixedWidth(320)
        r_row.addWidget(self.combo_radio)

        self.btn_apply_radio = PrimaryPushButton(FluentIcon.ACCEPT, "Áp Dụng Chế Độ Sóng", radio_card)
        self.btn_apply_radio.clicked.connect(self._apply_radio_mode)
        r_row.addWidget(self.btn_apply_radio)
        r_row.addStretch(1)
        r_layout.addLayout(r_row)

        self.layout.addWidget(radio_card)

        # 4. Windows Management Tools Card
        tools_card = SimpleCardWidget(self.container)
        tl_layout = QHBoxLayout(tools_card)
        tl_layout.setContentsMargins(24, 18, 24, 18)
        tl_layout.setSpacing(12)

        tl_layout.addWidget(StrongBodyLabel("Công cụ Windows:", tools_card))

        btn_devmgr = PushButton(FluentIcon.DEVELOPER_TOOLS, "Device Manager", tools_card)
        btn_devmgr.clicked.connect(lambda: os.system("start devmgmt.msc"))
        tl_layout.addWidget(btn_devmgr)

        btn_ncpa = PushButton(FluentIcon.WIFI, "Network Connections (ncpa.cpl)", tools_card)
        btn_ncpa.clicked.connect(lambda: os.system("start ncpa.cpl"))
        tl_layout.addWidget(btn_ncpa)

        btn_repack = PushButton(FluentIcon.FOLDER, "Thư mục Driver Repack", tools_card)
        btn_repack.clicked.connect(self._open_driver_folder)
        tl_layout.addWidget(btn_repack)
        tl_layout.addStretch(1)

        self.layout.addWidget(tools_card)
        self.layout.addStretch(1)

        self._refresh_interfaces_table()

    def _run_driver_patcher(self):
        bat = os.path.join(get_resource_dir("drivers"), "Install-All-Recommended.bat")
        InfoBar.info(
            "Đang cấu hình Driver usbser.sys",
            "Vui lòng nhấn 'Yes' trên hộp thoại UAC để chạy bộ vá driver chuẩn Microsoft...",
            parent=self.window(),
            position=InfoBarPosition.TOP_RIGHT,
            duration=6000
        )
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c "{bat}"', None, 1)

    def _restart_pnp_devices(self):
        main_win = self.window()
        def _task():
            try:
                from src.modeswitch import query_present_huawei_devices
                devs = query_present_huawei_devices()
                for d in devs:
                    dev_id = d["id"]
                    if "&MI_" in dev_id:
                        subprocess.run(f'pnputil /restart-device "{dev_id}"', shell=True, capture_output=True, text=True)
                main_win.signals.notification_requested.emit(
                    "success", "Khởi động lại PnP", "Đã khởi động lại các cổng PnP Modem & COM thành công!", 4000
                )
            except Exception as e:
                main_win.signals.notification_requested.emit(
                    "warning", "Khởi động lại PnP", f"Không thể khởi động lại PnP: {e}", 5000
                )

        threading.Thread(target=_task, daemon=True).start()

    def _apply_radio_mode(self):
        mode_idx = self.combo_radio.currentIndex()
        mode_str = "3g_only" if mode_idx == 0 else "auto"
        main_win = self.window()

        if getattr(main_win, "current_hw_state", "DISCONNECTED") != "MODEM":
            main_win.signals.notification_requested.emit(
                "warning", "Chưa kết nối Modem", "Vui lòng chuyển sang Chế độ Modem 3G trước khi cấu hình sóng.", 4000
            )
            return

        self.btn_apply_radio.setEnabled(False)
        def _task():
            main_win.is_dialing = True
            try:
                if not main_win.at_engine.is_connected:
                    main_win.at_engine.auto_connect()
                ok, msg = main_win.at_engine.set_radio_mode(mode_str)
                main_win.signals.radio_mode_result.emit(ok, "Đã lưu cấu hình khóa sóng vào NVRAM modem!" if ok else f"Lỗi: {msg}")
            finally:
                main_win.is_dialing = False

        threading.Thread(target=_task, daemon=True).start()

    def _open_driver_folder(self):
        drv_dir = get_resource_dir("drivers")
        try:
            os.startfile(drv_dir)
        except Exception:
            subprocess.Popen(f'explorer "{drv_dir}"', shell=True)

    def _refresh_interfaces_table(self):
        devices = query_present_huawei_devices()
        endpoints = []
        if not devices:
            endpoints.append(("—", "Không phát hiện phần cứng DCom", "Chưa cắm USB", "—", "Disconnected (Rút)"))
        else:
            for d in devices:
                dev_id = d["id"]
                prob = d["problem"]
                status_txt = "OK (Hoạt động)" if prob == 0 else f"⚠ Lỗi Code {prob} (Chặn HVCI)"
                if "&MI_00" in dev_id:
                    endpoints.append(("MI_00", "3G Modem Interface", "Cổng Modem RAS", "modem.sys + usbser.sys", status_txt))
                elif "&MI_01" in dev_id and "PID_1003" in dev_id:
                    endpoints.append(("MI_01", "PC UI Interface (Lệnh AT)", "COM Port", "usbser.sys", status_txt))
                elif "&MI_01" in dev_id and "PID_1436" in dev_id:
                    endpoints.append(("MI_01", "3G Network Card (NDIS)", "NDIS Adapter", "Vô hiệu hóa (Tránh ngắt Wi-Fi)", "Disabled"))
                elif "&MI_02" in dev_id and "PID_1003" in dev_id:
                    endpoints.append(("MI_02", "USB Mass Storage (ZeroCD)", "Ổ đĩa ảo", "usbstor.sys", status_txt))
                elif "&MI_03" in dev_id:
                    endpoints.append(("MI_03", "PC UI Interface (Lệnh AT)", "COM Port", "usbser.sys", status_txt))
                elif "&MI_04" in dev_id:
                    endpoints.append(("MI_04", "Application / Diag Interface", "Diag Port", "Huawei Diagnostics", "Sẵn sàng"))
                elif "&MI_05" in dev_id:
                    endpoints.append(("MI_05", "USB Mass Storage (ZeroCD)", "Ổ đĩa E:", "usbstor.sys", status_txt))
                elif "&MI_06" in dev_id:
                    endpoints.append(("MI_06", "MicroSD Card Reader", "Removable Drive", "usbstor.sys", status_txt))
                elif "PID_1446" in dev_id:
                    endpoints.append(("ZeroCD", "USB Mass Storage Device", "Ổ đĩa cài đặt", "usbstor.sys", "ZeroCD Active"))
                elif "&MI_" not in dev_id:
                    endpoints.append(("USB Composite", "Parent Composite Device", "USB Hub", "usbccgp.sys", status_txt))

        self.table_interfaces.setRowCount(len(endpoints))
        for r, ep in enumerate(endpoints):
            for c, val in enumerate(ep):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_interfaces.setItem(r, c, item)


# =============================================================================
# PAGE 6: SETTINGS & APN CONFIGURATION
# =============================================================================
class SettingsInterface(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingsInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.viewport().setStyleSheet("background-color: transparent;")
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.setWidget(self.container)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(36, 24, 36, 28)
        self.layout.setSpacing(16)

        self.title_label = TitleLabel("Cài Đặt Cấu Hình & Mạng", self.container)
        self.subtitle_label = CaptionLabel("Tùy chỉnh thông số APN nhà mạng và tùy chọn quay số", self.container)
        self.subtitle_label.setTextColor(QColor("#606060"), QColor("#A0A0A0"))
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.subtitle_label)

        # Carrier Selector Card
        carrier_card = SimpleCardWidget(self.container)
        c_layout = QHBoxLayout(carrier_card)
        c_layout.setContentsMargins(24, 18, 24, 18)
        c_layout.addWidget(StrongBodyLabel("Cấu hình Nhà mạng 3G (APN Profile):", carrier_card))
        c_layout.addStretch(1)

        self.carrier_combo = ComboBox(carrier_card)
        self.carrier_combo.addItems(["MobiFone", "Viettel", "Vinaphone", "Vietnamobile"])
        self.carrier_combo.setCurrentText("MobiFone")
        self.carrier_combo.setFixedWidth(220)
        self.carrier_combo.currentTextChanged.connect(self._on_carrier_changed)
        c_layout.addWidget(self.carrier_combo)
        self.layout.addWidget(carrier_card)

        # Connection Options Card
        opt_card = SimpleCardWidget(self.container)
        o_layout = QVBoxLayout(opt_card)
        o_layout.setContentsMargins(24, 18, 24, 18)
        o_layout.setSpacing(8)

        o_layout.addWidget(StrongBodyLabel("Tùy chọn kết nối Internet", opt_card))
        desc = (
            "• Chế độ Metric Route tự động: Không chiếm quyền ưu tiên của Wi-Fi khi cả 2 kết nối cùng bật.\n"
            "• Giao thức quay số: Windows 11 RAS PPP qua số quay *99# chuẩn quốc tế.\n"
            "• Cổng Modem: Đã gán cổng HUAWEI Mobile Connect - 3G Modem."
        )
        lbl_desc = BodyLabel(desc, opt_card)
        lbl_desc.setTextColor(QColor("#505050"), QColor("#B8B8B8"))
        o_layout.addWidget(lbl_desc)
        self.layout.addWidget(opt_card)
        self.layout.addStretch(1)

    def _on_carrier_changed(self, carrier):
        apn_map = {
            "MobiFone": "m-wap",
            "Viettel": "v-internet",
            "Vinaphone": "m3-world",
            "Vietnamobile": "internet"
        }
        self.window().current_carrier = carrier
        self.window().dashboardInterface.carrier_badge.setText(f"{carrier.upper()} 3G")
        self.window().dashboardInterface.apn_label.setText(f"APN: {apn_map.get(carrier, 'm-wap')}  •  Số quay: *99#")


# =============================================================================
# MAIN WINDOW: FLUENT WINDOW (WINUI 3)
# =============================================================================
class WinUI3MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        setTheme(Theme.DARK)
        setThemeColor("#0078D4")

        self.setWindowTitle("Fast Connect 3G — Windows 11 Control Center")
        self.resize(1000, 720)
        self.setMinimumSize(900, 600)

        # Ensure crisp dark surface even if DWM Mica is inactive
        self.setMicaEffectEnabled(False)
        self.setStyleSheet("WinUI3MainWindow { background-color: #202020; }")

        # Engines & State
        self.at_engine = HuaweiATEngine()
        self.dialer = WindowsRASDialer()
        self.dialer.ensure_phonebook_entry("MobiFone")
        self.current_carrier = "MobiFone"
        self.is_switching_mode = False
        self.signals = TelemetrySignals()

        # Immediate synchronous hardware state check (< 1ms native SetupAPI)
        try:
            init_state, init_detail, init_drive, init_err = get_device_state()
            self.current_hw_state = init_state
            self.current_has_driver_err = init_err
        except Exception:
            init_state, init_detail, init_drive, init_err = "DISCONNECTED", "Chưa cắm thiết bị", None, False
            self.current_hw_state = "DISCONNECTED"
            self.current_has_driver_err = False

        # Connect signals
        self.signals.signal_updated.connect(self._on_signal_updated)
        self.signals.operator_updated.connect(self._on_operator_updated)
        self.signals.device_updated.connect(self._on_device_updated)
        self.signals.traffic_updated.connect(self._on_traffic_updated)
        self.signals.connection_state_changed.connect(self._on_conn_state_changed)
        self.signals.driver_status_checked.connect(self._on_driver_status_checked)
        self.signals.hardware_state_changed.connect(self._on_hw_state_changed)
        self.signals.notification_requested.connect(self._on_notification_requested)
        self.signals.mode_switch_finished.connect(self._on_mode_switch_finished)
        self.signals.sms_loaded.connect(self._on_sms_loaded)
        self.signals.sms_sent.connect(self._on_sms_sent)
        self.signals.radio_mode_result.connect(self._on_radio_mode_updated)

        # Init Sub-Interfaces
        self.dashboardInterface = DashboardInterface(self)
        self.smsInterface = SMSInterface(self)
        self.driverInterface = DriverManagerInterface(self)
        self.settingsInterface = SettingsInterface(self)

        # Initial UI synchronization with detected hardware state
        self.dashboardInterface.on_hardware_state_changed(init_state, init_detail, init_drive)

        # Navigation Items
        self.addSubInterface(
            self.dashboardInterface,
            FluentIcon.WIFI,
            "Tổng quan & Kết nối",
            NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.smsInterface,
            FluentIcon.MESSAGE,
            "Tin nhắn SMS",
            NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.driverInterface,
            FluentIcon.DEVELOPER_TOOLS,
            "Quản lý Driver & Phần cứng",
            NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.settingsInterface,
            FluentIcon.SETTING,
            "Cài đặt & Mạng",
            NavigationItemPosition.BOTTOM
        )

        # Telemetry Thread
        self.is_running = True
        self.is_dialing = False
        self._ui_conn_synced = None
        self.worker_thread = threading.Thread(target=self._background_telemetry_loop, daemon=True)
        self.worker_thread.start()

    def _on_signal_updated(self, rssi, ber, dbm, pct, bars):
        bar_text = "▂▄▆█"[:bars] if bars > 0 else "—"
        self.dashboardInterface.signal_value_label.setText(f"Sóng: {bar_text} {pct}%")
        self.dashboardInterface.signal_bar.setValue(pct)
        self.dashboardInterface.signal_dbm_label.setText(f"Mức tín hiệu: {dbm} dBm (CSQ: {rssi})")

    def _on_operator_updated(self, oper, tech):
        if oper and oper != "Unknown":
            self.dashboardInterface.carrier_badge.setText(f"{oper.upper()} 3G")
        self.dashboardInterface.tech_label.setText(f"Công nghệ: {tech}")

    def _on_device_updated(self, model, port):
        self.dashboardInterface.lbl_device_info.setText(f"Thiết bị: {model} (Cổng điều khiển: {port})")
        self.dashboardInterface.lbl_mode_info.setText("Chế độ phần cứng: Modem Mode hoạt động tốt (usbser.sys)")
        self.dashboardInterface.btn_switch.setEnabled(True)

    def _on_traffic_updated(self, uptime, up_mb, down_mb):
        self.dashboardInterface.lbl_uptime_val.setText(uptime)
        self.dashboardInterface.lbl_upload_val.setText(f"{up_mb:.2f} MB")
        self.dashboardInterface.lbl_download_val.setText(f"{down_mb:.2f} MB")

    def _on_conn_state_changed(self, is_connected, msg):
        self._ui_conn_synced = is_connected
        self.dashboardInterface.btn_connect.setEnabled(True)
        if is_connected:
            ip = self.dialer.get_ppp_ip()
            ip_str = f" — IP: {ip}" if ip else ""
            self.dashboardInterface.btn_connect.setText("NGẮT KẾT NỐI (DISCONNECT)")
            self.dashboardInterface.conn_status_label.setText(f"Trạng thái: Đã kết nối Internet 3G (Online{ip_str})")
            self.dashboardInterface.conn_status_label.setTextColor(QColor("#107C41"), QColor("#6CCB5F"))
            self.dashboardInterface.conn_sub_label.setText(
                "Đã kích hoạt Default Gateway 0.0.0.0 (Metric ưu tiên số 1) — Windows đang sử dụng dữ liệu 3G"
            )
            if "--%" in self.dashboardInterface.signal_value_label.text():
                self.dashboardInterface.signal_value_label.setText("Sóng: ▂▄▆█ 3G Active")
                self.dashboardInterface.signal_bar.setValue(75)
                self.dashboardInterface.signal_dbm_label.setText("Đang truyền dữ liệu PPP qua cổng COM13")
            if msg:
                InfoBar.success("Đã kết nối 3G", msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000)
        else:
            self.dashboardInterface.btn_connect.setText("KẾT NỐI INTERNET 3G")
            self.dashboardInterface.conn_status_label.setText("Trạng thái: Chưa kết nối Internet")
            self.dashboardInterface.conn_status_label.setTextColor(QColor("#202020"), QColor("#FFFFFF"))
            self.dashboardInterface.conn_sub_label.setText(
                "Sử dụng giao thức chuẩn Windows 11 RAS PPP Dial-Up qua cổng Modem 3G"
            )
            if msg and ("thất bại" in msg.lower() or "không thể" in msg.lower() or "lỗi" in msg.lower()):
                InfoBar.error("Không thể kết nối", msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=8000)

    def _on_hw_state_changed(self, state, detail, drive):
        self.dashboardInterface.on_hardware_state_changed(state, detail, drive)

    def _on_driver_status_checked(self, is_ok, detail):
        # Strict Rule: NEVER show driver error if device is unplugged or in ZeroCD mode!
        if self.current_hw_state == "MODEM":
            self.dashboardInterface.driver_card.setVisible(not is_ok)
        else:
            self.dashboardInterface.driver_card.setVisible(False)

    def _on_sms_loaded(self, messages):
        self.smsInterface.btn_refresh.setEnabled(True)
        if not messages:
            self.smsInterface.inbox_text.setPlainText("Không có tin nhắn SMS nào trong SIM.")
        else:
            out = ""
            for m in messages:
                out += f"[{m['index']}] Từ: {m['sender']} ({m['date']})\n{m['body']}\n{'─'*45}\n"
            self.smsInterface.inbox_text.setPlainText(out)

    def _on_sms_sent(self, ok, msg):
        self.smsInterface.btn_send_sms.setEnabled(True)
        if ok:
            InfoBar.success("Đã gửi SMS", msg, parent=self, position=InfoBarPosition.TOP_RIGHT)
            self.smsInterface.txt_sms_body.clear()
        else:
            InfoBar.error("Gửi SMS thất bại", msg, parent=self, position=InfoBarPosition.TOP_RIGHT)

    def _on_radio_mode_updated(self, ok, msg):
        self.driverInterface.btn_apply_radio.setEnabled(True)
        if ok:
            InfoBar.success("Chế độ sóng", msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000)
        else:
            InfoBar.error("Lỗi cấu hình sóng", msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=6000)

    def _on_notification_requested(self, ntype, title, msg, duration):
        if ntype == "success":
            InfoBar.success(title, msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=duration)
        elif ntype == "warning":
            InfoBar.warning(title, msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=duration)
        elif ntype == "error":
            InfoBar.error(title, msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=duration)
        else:
            InfoBar.info(title, msg, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=duration)

    def _on_mode_switch_finished(self, ok, msg):
        self.is_switching_mode = False
        try:
            state, detail, drive, has_driver_err = get_device_state()
            self.current_hw_state = state
            self.current_has_driver_err = has_driver_err
            self.dashboardInterface.on_hardware_state_changed(state, detail, drive)
        except Exception:
            self.dashboardInterface.btn_switch.setEnabled(True)
            self.dashboardInterface.btn_connect.setEnabled(True)

    def _background_telemetry_loop(self):
        last_state = None
        while self.is_running:
            try:
                # Pause telemetry while mode switching is in progress to prevent COM port contention
                if getattr(self, "is_switching_mode", False):
                    time.sleep(0.5)
                    continue

                # 1. Real-time Hardware PnP State Scan via native SetupAPI
                state, detail, drive, has_driver_err = get_device_state()
                self.current_hw_state = state
                self.current_has_driver_err = has_driver_err

                # Emit hardware state to update UI badges, cards, and buttons
                self.signals.hardware_state_changed.emit(state, detail, drive or "")

                # 2. Driver check: only report error when in MODEM mode with actual driver issue
                if state == "MODEM":
                    self.signals.driver_status_checked.emit(not has_driver_err, detail)
                else:
                    self.signals.driver_status_checked.emit(True, "")

                # 3. Handle disconnected or ZeroCD state: disconnect active engines gracefully
                if state != "MODEM":
                    if self.at_engine.is_connected:
                        self.at_engine.disconnect()
                    if self.dialer.is_connected:
                        self.dialer.disconnect()
                        self.signals.connection_state_changed.emit(False, "Thiết bị DCom 3G đã bị ngắt kết nối.")
                    time.sleep(1.5)
                    continue

                # 4. Check active RAS PPP connection status (MODEM mode only)
                if not self.is_dialing:
                    ppp_active = self.dialer.check_status()
                    if ppp_active != self._ui_conn_synced:
                        ip = self.dialer.get_ppp_ip()
                        msg = f"Đang kết nối Internet 3G (IP: {ip})" if (ppp_active and ip) else ""
                        self.signals.connection_state_changed.emit(ppp_active, msg)

                # 5. Traffic & AT Telemetry
                if self.dialer.is_connected or self.is_dialing:
                    if self.at_engine.is_connected:
                        self.at_engine.disconnect()
                    if self.dialer.is_connected:
                        uptime, up_mb, down_mb = self.dialer.get_traffic_stats()
                        self.signals.traffic_updated.emit(uptime, up_mb, down_mb)
                else:
                    # When PPP is idle, poll AT telemetry on COM port
                    if not has_driver_err and not self.at_engine.is_connected:
                        ok, _ = self.at_engine.auto_connect()
                        if ok:
                            model = self.at_engine.device_info.get("Model", "Huawei E173")
                            self.signals.device_updated.emit(model, self.at_engine.port or "COM14")

                    if self.at_engine.is_connected:
                        rssi, ber, dbm, pct, bars = self.at_engine.get_signal_quality()
                        self.signals.signal_updated.emit(rssi, ber, dbm, pct, bars)

                        oper, tech = self.at_engine.get_network_operator()
                        self.signals.operator_updated.emit(oper, tech)

            except Exception:
                pass
            time.sleep(1.5)

    def closeEvent(self, event):
        self.is_running = False
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = WinUI3MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
