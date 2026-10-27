"""
Modern WinUI 3 / Windows 11 Fluent UI Controller for 3G DCom
(Fast Connect / Huawei E173)
Features:
- Windows 11 Dark/Light theme with Fluent design controls
- Real-time Signal (RSSI / CSQ) & Carrier Monitoring
- ZeroCD User-Mode ModeSwitcher
- One-Click 3G Internet Connect / Disconnect (Windows RAS)
- Interactive USSD Manager (*101#, Top-up, Packages)
- SMS Manager (Inbox list & Compose)
"""

import os
import sys
import time
import threading
import customtkinter as ctk
from tkinter import messagebox

from src.at_engine import HuaweiATEngine
from src.dialer import WindowsRASDialer, CARRIER_APNS
from src.modeswitch import auto_detect_and_switch, get_connected_huawei_pids

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class WinUIFastConnectApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Fast Connect 3G - Windows 11 Control Center")
        self.geometry("960x650")
        self.minsize(880, 580)

        # Initialize engines
        self.at_engine = HuaweiATEngine()
        self.dialer = WindowsRASDialer()

        # Telemetry state
        self.carrier_name = "MobiFone"
        self.network_tech = "Đang quét..."
        self.signal_bars = 0
        self.signal_dbm = -113
        self.signal_pct = 0
        self.selected_port = ""
        self.is_monitoring = True

        # Layout: Sidebar on Left, Content on Right
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.create_sidebar()
        self.create_content_frames()

        # Select default tab
        self.select_tab("dashboard")

        # Start background monitor thread
        self.monitor_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.monitor_thread.start()

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        # App Brand Header
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Fast Connect 3G",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 5), sticky="w")

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Windows 11 Edition",
            text_color="#888888",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 25), sticky="w")

        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "📶  Tổng quan & Kết nối"),
            ("ussd", "💳  Tra cứu USSD & Nạp thẻ"),
            ("sms", "💬  Tin nhắn SMS"),
            ("settings", "⚙️  Cấu hình APN & Driver"),
        ]

        for idx, (tab_key, label_text) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label_text,
                height=42,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray25"),
                anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=14),
                command=lambda k=tab_key: self.select_tab(k)
            )
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[tab_key] = btn

        # Theme Selector at bottom
        self.theme_label = ctk.CTkLabel(self.sidebar_frame, text="Chế độ giao diện:", font=ctk.CTkFont(size=11))
        self.theme_label.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Tối (Dark)", "Sáng (Light)"],
            command=self._change_theme,
            height=30,
            corner_radius=6
        )
        self.theme_menu.grid(row=7, column=0, padx=15, pady=(5, 20), sticky="ew")

    def _change_theme(self, choice):
        if "Tối" in choice:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def create_content_frames(self):
        # Container for content
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {
            "dashboard": self._build_dashboard_frame(),
            "ussd": self._build_ussd_frame(),
            "sms": self._build_sms_frame(),
            "settings": self._build_settings_frame()
        }

    def select_tab(self, tab_key):
        for k, frame in self.frames.items():
            if k == tab_key:
                frame.grid(row=0, column=0, sticky="nsew")
                self.nav_buttons[k].configure(fg_color=("gray75", "gray30"))
            else:
                frame.grid_forget()
                self.nav_buttons[k].configure(fg_color="transparent")

    # =========================================================================
    # TAB 1: DASHBOARD & CONNECTION
    # =========================================================================
    def _build_dashboard_frame(self):
        f = ctk.CTkFrame(self.container, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        # Header Title
        title = ctk.CTkLabel(
            f, text="Bảng Điều Khiển Kết Nối",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=24, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        # Card 1: Network & Carrier Status Card
        card_status = ctk.CTkFrame(f, corner_radius=12)
        card_status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15), padx=2)
        card_status.grid_columnconfigure(1, weight=1)

        self.carrier_badge = ctk.CTkLabel(
            card_status, text="MOBIFONE 3G",
            fg_color="#0078D4", text_color="white", corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            padx=12, pady=4
        )
        self.carrier_badge.grid(row=0, column=0, padx=20, pady=20, sticky="w")

        self.tech_label = ctk.CTkLabel(
            card_status, text="Công nghệ: HSPA+ (3.75G)",
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        self.tech_label.grid(row=0, column=1, padx=10, pady=20, sticky="w")

        # Signal bars & dBm
        self.signal_label = ctk.CTkLabel(
            card_status, text="Sóng: [|||||] 100% (-51 dBm)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#107C41"
        )
        self.signal_label.grid(row=0, column=2, padx=20, pady=20, sticky="e")

        # Card 2: Main Connect/Disconnect Action Card
        card_action = ctk.CTkFrame(f, corner_radius=12)
        card_action.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 15), padx=2)
        card_action.grid_columnconfigure(0, weight=1)

        self.connect_status_label = ctk.CTkLabel(
            card_action, text="Chưa kết nối Internet",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="gray"
        )
        self.connect_status_label.grid(row=0, column=0, pady=(25, 10))

        self.connect_btn = ctk.CTkButton(
            card_action,
            text="KẾT NỐI INTERNET (CONNECT)",
            height=52,
            width=320,
            corner_radius=26,
            fg_color="#107C41",
            hover_color="#0E6B37",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            command=self._toggle_connection
        )
        self.connect_btn.grid(row=1, column=0, pady=(0, 25))

        # Card 3: Session Stats
        card_stats = ctk.CTkFrame(f, corner_radius=12)
        card_stats.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15), padx=2)
        card_stats.grid_columnconfigure((0, 1, 2), weight=1)

        self.uptime_box = ctk.CTkLabel(
            card_stats, text="Thời gian online\n00:00:00",
            font=ctk.CTkFont(family="Segoe UI", size=15)
        )
        self.uptime_box.grid(row=0, column=0, pady=20)

        self.upload_box = ctk.CTkLabel(
            card_stats, text="Dữ liệu Tải lên\n0.00 MB",
            font=ctk.CTkFont(family="Segoe UI", size=15)
        )
        self.upload_box.grid(row=0, column=1, pady=20)

        self.download_box = ctk.CTkLabel(
            card_stats, text="Dữ liệu Tải xuống\n0.00 MB",
            font=ctk.CTkFont(family="Segoe UI", size=15)
        )
        self.download_box.grid(row=0, column=2, pady=20)

        # Bottom Bar: ZeroCD Quick Switcher
        bar_bottom = ctk.CTkFrame(f, fg_color="transparent")
        bar_bottom.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        bar_bottom.grid_columnconfigure(0, weight=1)

        self.device_info_label = ctk.CTkLabel(
            bar_bottom, text="Thiết bị: Đang quét...", text_color="gray",
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.device_info_label.grid(row=0, column=0, sticky="w")

        self.switch_btn = ctk.CTkButton(
            bar_bottom, text="⚡ Chuyển mạch DCom (ZeroCD)",
            width=200, height=32, corner_radius=8,
            fg_color="#D83B01", hover_color="#C23401",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._manual_switch
        )
        self.switch_btn.grid(row=0, column=1, sticky="e")

        return f

    # =========================================================================
    # TAB 2: USSD & RECHARGE
    # =========================================================================
    def _build_ussd_frame(self):
        f = ctk.CTkFrame(self.container, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            f, text="Tra cứu Tài khoản & Nạp tiền (USSD)",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=24, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 15))

        # Quick USSD Shortcuts
        quick_frame = ctk.CTkFrame(f, corner_radius=12)
        quick_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        quick_frame.grid_columnconfigure((0, 1, 2), weight=1)

        btn101 = ctk.CTkButton(
            quick_frame, text="🔍 Kiểm tra TK Chính (*101#)",
            height=40, corner_radius=8,
            command=lambda: self._execute_ussd("*101#")
        )
        btn101.grid(row=0, column=0, padx=10, pady=15, sticky="ew")

        btn102 = ctk.CTkButton(
            quick_frame, text="🎁 Tài khoản Khuyến mãi (*102#)",
            height=40, corner_radius=8,
            command=lambda: self._execute_ussd("*102#")
        )
        btn102.grid(row=0, column=1, padx=10, pady=15, sticky="ew")

        btn090 = ctk.CTkButton(
            quick_frame, text="⚡ Gói cước Dữ liệu (*090#)",
            height=40, corner_radius=8,
            command=lambda: self._execute_ussd("*090#")
        )
        btn090.grid(row=0, column=2, padx=10, pady=15, sticky="ew")

        # Custom USSD / Recharge Input
        input_frame = ctk.CTkFrame(f, corner_radius=12)
        input_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        input_frame.grid_columnconfigure(0, weight=1)

        self.ussd_input = ctk.CTkEntry(
            input_frame, placeholder_text="Nhập mã USSD (vd: *101# hoặc *100*MÃ_THẺ_CÀO#)...",
            height=42, corner_radius=8
        )
        self.ussd_input.grid(row=0, column=0, padx=(15, 10), pady=15, sticky="ew")

        self.send_ussd_btn = ctk.CTkButton(
            input_frame, text="Gửi lệnh", width=120, height=42, corner_radius=8,
            command=lambda: self._execute_ussd(self.ussd_input.get())
        )
        self.send_ussd_btn.grid(row=0, column=1, padx=(0, 15), pady=15)

        # USSD Result Display Box
        result_label = ctk.CTkLabel(f, text="Phản hồi từ Nhà mạng:", font=ctk.CTkFont(size=14, weight="bold"))
        result_label.grid(row=3, column=0, sticky="w", pady=(0, 5))

        self.ussd_result_box = ctk.CTkTextbox(
            f, height=220, corner_radius=12,
            font=ctk.CTkFont(family="Consolas", size=13)
        )
        self.ussd_result_box.grid(row=4, column=0, sticky="nsew")

        return f

    # =========================================================================
    # TAB 3: SMS MANAGER
    # =========================================================================
    def _build_sms_frame(self):
        f = ctk.CTkFrame(self.container, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)
        f.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            f, text="Quản lý Tin nhắn SMS",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=24, weight="bold")
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        # Top Bar for SMS: Refresh inbox
        sms_top = ctk.CTkFrame(f, fg_color="transparent")
        sms_top.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        sms_top.grid_columnconfigure(0, weight=1)

        self.refresh_sms_btn = ctk.CTkButton(
            sms_top, text="🔄 Tải lại Hộp thư", width=140, height=36, corner_radius=8,
            command=self._load_sms_inbox
        )
        self.refresh_sms_btn.grid(row=0, column=1, sticky="e")

        # Left Column: SMS List
        list_card = ctk.CTkFrame(f, corner_radius=12)
        list_card.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        list_card.grid_rowconfigure(1, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_card, text="Hộp thư đến (Inbox)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.sms_list_box = ctk.CTkTextbox(list_card, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=12))
        self.sms_list_box.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

        # Right Column: Compose SMS
        compose_card = ctk.CTkFrame(f, corner_radius=12)
        compose_card.grid(row=2, column=1, sticky="nsew")
        compose_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(compose_card, text="Soạn tin nhắn mới", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.sms_phone_input = ctk.CTkEntry(compose_card, placeholder_text="Số điện thoại người nhận...", height=38, corner_radius=8)
        self.sms_phone_input.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")

        self.sms_body_input = ctk.CTkTextbox(compose_card, height=180, corner_radius=8)
        self.sms_body_input.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")

        self.send_sms_btn = ctk.CTkButton(
            compose_card, text="✉️ Gửi Tin nhắn", height=40, corner_radius=8,
            fg_color="#0078D4", hover_color="#0067C0",
            command=self._send_sms
        )
        self.send_sms_btn.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")

        return f

    # =========================================================================
    # TAB 4: SETTINGS & DRIVERS
    # =========================================================================
    def _build_settings_frame(self):
        f = ctk.CTkFrame(self.container, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            f, text="Cấu hình & Driver Windows 11",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=24, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 15))

        # Card 1: Carrier Profile Settings
        card_apn = ctk.CTkFrame(f, corner_radius=12)
        card_apn.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        card_apn.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_apn, text="Chọn Cấu hình Nhà mạng:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")
        self.carrier_select = ctk.CTkOptionMenu(
            card_apn, values=["MobiFone", "Viettel", "Vinaphone", "Vietnamobile"],
            command=self._change_carrier
        )
        self.carrier_select.set("MobiFone")
        self.carrier_select.grid(row=0, column=1, padx=20, pady=15, sticky="e")

        # Card 2: Driver Status Card
        card_drv = ctk.CTkFrame(f, corner_radius=12)
        card_drv.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        card_drv.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_drv, text="Trạng thái Driver Windows 11 (Memory Integrity Safe):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        
        info_text = (
            "• Chế độ Driver: Giải pháp 1 (In-Box Microsoft usbser.sys / Modem standard)\n"
            "• Core Isolation (HVCI): 100% Tương thích, không bị chặn bởi Windows Defender\n"
            "• Switch Engine: ZeroCD User-Mode SCSI Ejector (Không dùng filter driver kernel)\n"
        )
        ctk.CTkLabel(card_drv, text=info_text, justify="left", text_color="gray").grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Driver Actions
        btn_box = ctk.CTkFrame(f, fg_color="transparent")
        btn_box.grid(row=3, column=0, sticky="ew", pady=10)
        btn_box.grid_columnconfigure((0, 1), weight=1)

        install_btn = ctk.CTkButton(
            btn_box, text="📥 Cài đặt Driver Tự động (Admin)",
            height=42, corner_radius=8,
            command=self._run_driver_installer
        )
        install_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        devmgr_btn = ctk.CTkButton(
            btn_box, text="🛠️ Mở Device Manager",
            height=42, corner_radius=8, fg_color="gray30", hover_color="gray20",
            command=lambda: os.system("start devmgmt.msc")
        )
        devmgr_btn.grid(row=0, column=1, padx=(10, 0), sticky="ew")

        return f

    # =========================================================================
    # ACTIONS & LOGIC
    # =========================================================================
    def _manual_switch(self):
        def _task():
            self.switch_btn.configure(state="disabled", text="Đang chuyển mạch...")
            ok, msg = auto_detect_and_switch()
            messagebox.showinfo("ZeroCD Switcher", msg)
            self.switch_btn.configure(state="normal", text="⚡ Chuyển mạch DCom (ZeroCD)")
        threading.Thread(target=_task, daemon=True).start()

    def _toggle_connection(self):
        if not self.dialer.is_connected:
            self.connect_btn.configure(state="disabled", text="ĐANG KẾT NỐI...")
            def _connect_task():
                ok, msg = self.dialer.connect(carrier=self.carrier_name)
                if ok:
                    self.connect_btn.configure(
                        state="normal", text="NGẮT KẾT NỐI (DISCONNECT)",
                        fg_color="#D83B01", hover_color="#C23401"
                    )
                    self.connect_status_label.configure(
                        text="Đã kết nối Internet thành công! (Online)",
                        text_color="#107C41"
                    )
                else:
                    self.connect_btn.configure(state="normal", text="KẾT NỐI INTERNET (CONNECT)")
                    messagebox.showerror("Lỗi Kết nối", msg)
            threading.Thread(target=_connect_task, daemon=True).start()
        else:
            self.connect_btn.configure(state="disabled", text="ĐANG NGẮT...")
            def _disconnect_task():
                self.dialer.disconnect()
                self.connect_btn.configure(
                    state="normal", text="KẾT NỐI INTERNET (CONNECT)",
                    fg_color="#107C41", hover_color="#0E6B37"
                )
                self.connect_status_label.configure(text="Chưa kết nối Internet", text_color="gray")
            threading.Thread(target=_disconnect_task, daemon=True).start()

    def _execute_ussd(self, code):
        code = code.strip()
        if not code:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập mã USSD!")
            return

        def _task():
            self.send_ussd_btn.configure(state="disabled")
            self.ussd_result_box.delete("1.0", "end")
            self.ussd_result_box.insert("end", f"Đang gửi lệnh USSD '{code}' đến nhà mạng...\n")
            
            ok, resp = self.at_engine.send_ussd(code)
            self.ussd_result_box.delete("1.0", "end")
            if ok:
                self.ussd_result_box.insert("end", f"=== KẾT QUẢ TỪ NHÀ MẠNG ===\n\n{resp}\n")
            else:
                self.ussd_result_box.insert("end", f"Lỗi USSD:\n{resp}\n")
            self.send_ussd_btn.configure(state="normal")

        threading.Thread(target=_task, daemon=True).start()

    def _load_sms_inbox(self):
        def _task():
            self.refresh_sms_btn.configure(state="disabled", text="Đang tải...")
            messages = self.at_engine.list_sms()
            self.sms_list_box.delete("1.0", "end")
            if not messages:
                self.sms_list_box.insert("end", "Không có tin nhắn nào trong SIM.")
            else:
                for m in messages:
                    self.sms_list_box.insert(
                        "end",
                        f"[{m['index']}] Từ: {m['sender']} ({m['date']})\n{m['body']}\n{'-'*35}\n"
                    )
            self.refresh_sms_btn.configure(state="normal", text="🔄 Tải lại Hộp thư")

        threading.Thread(target=_task, daemon=True).start()

    def _send_sms(self):
        phone = self.sms_phone_input.get().strip()
        body = self.sms_body_input.get("1.0", "end").strip()
        if not phone or not body:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đủ số điện thoại và nội dung tin nhắn!")
            return

        def _task():
            self.send_sms_btn.configure(state="disabled", text="Đang gửi...")
            ok, msg = self.at_engine.send_sms(phone, body)
            if ok:
                messagebox.showinfo("SMS", "Đã gửi tin nhắn thành công!")
                self.sms_body_input.delete("1.0", "end")
            else:
                messagebox.showerror("SMS Thất bại", msg)
            self.send_sms_btn.configure(state="normal", text="✉️ Gửi Tin nhắn")

        threading.Thread(target=_task, daemon=True).start()

    def _change_carrier(self, carrier):
        self.carrier_name = carrier
        self.carrier_badge.configure(text=f"{carrier.upper()} 3G")

    def _run_driver_installer(self):
        bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "drivers", "Install-All-Recommended.bat"))
        os.system(f'start "" "{bat_path}"')

    # =========================================================================
    # BACKGROUND TELEMETRY LOOP
    # =========================================================================
    def _telemetry_loop(self):
        while self.is_monitoring:
            try:
                # Check DCom connection
                if not self.at_engine.is_connected:
                    ok, _ = self.at_engine.auto_connect()
                    if ok:
                        dev = self.at_engine.device_info.get("Model", "Huawei E173")
                        self.device_info_label.configure(text=f"Thiết bị: {dev} (Cổng: {self.at_engine.port})")

                if self.at_engine.is_connected:
                    # Update Signal
                    rssi, ber, dbm, pct, bars = self.at_engine.get_signal_quality()
                    bar_str = "[" + "|" * bars + " " * (5 - bars) + "]"
                    self.signal_label.configure(text=f"Sóng: {bar_str} {pct}% ({dbm} dBm)")

                    # Update Operator & Tech
                    oper, tech = self.at_engine.get_network_operator()
                    if oper and oper != "Unknown":
                        self.carrier_badge.configure(text=f"{oper.upper()}")
                    self.tech_label.configure(text=f"Công nghệ: {tech}")

                # Update Traffic & Uptime
                if self.dialer.is_connected:
                    uptime, up_mb, down_mb = self.dialer.get_traffic_stats()
                    self.uptime_box.configure(text=f"Thời gian online\n{uptime}")
                    self.upload_box.configure(text=f"Dữ liệu Tải lên\n{up_mb} MB")
                    self.download_box.configure(text=f"Dữ liệu Tải xuống\n{down_mb} MB")

            except Exception:
                pass
            time.sleep(2.0)

if __name__ == "__main__":
    app = WinUIFastConnectApp()
    app.mainloop()
