"""
Windows 11 RAS Dial-Up Connection Manager for 3G Mobile Broadband
Uses Official Windows 11 RasSetEntryPropertiesW (PBVersion=8) + Registry Modem Lookup
Eliminates Remote Access Error 623 & Configures Carrier APN (AT+CGDCONT)
"""

import os
import re
import subprocess
import time
import ctypes
from ctypes import wintypes
import winreg
import psutil
import serial

CARRIER_APNS = {
    "MobiFone": {"apn": "m-wap", "user": "mms", "pass": "mms", "number": "*99#"},
    "Viettel": {"apn": "v-internet", "user": "", "pass": "", "number": "*99#"},
    "Vinaphone": {"apn": "m3-world", "user": "mms", "pass": "mms", "number": "*99#"},
    "Vietnamobile": {"apn": "internet", "user": "", "pass": "", "number": "*99#"},
    "Default": {"apn": "m-wap", "user": "mms", "pass": "mms", "number": "*99#"}
}

ENTRY_NAME = "FastConnect3G"

class RASENTRYW_Win11(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('dwfOptions', wintypes.DWORD),
        ('dwCountryID', wintypes.DWORD),
        ('dwCountryCode', wintypes.DWORD),
        ('szAreaCode', ctypes.c_wchar * 11),
        ('szLocalPhoneNumber', ctypes.c_wchar * 129),
        ('dwAlternateOffset', wintypes.DWORD),
        ('ipaddr', wintypes.DWORD),
        ('ipaddrDns', wintypes.DWORD),
        ('ipaddrDnsAlt', wintypes.DWORD),
        ('ipaddrWins', wintypes.DWORD),
        ('ipaddrWinsAlt', wintypes.DWORD),
        ('dwFrameSize', wintypes.DWORD),
        ('dwfNetProtocols', wintypes.DWORD),
        ('dwFramingProtocol', wintypes.DWORD),
        ('szScript', ctypes.c_wchar * 260),
        ('szAutodialDll', ctypes.c_wchar * 260),
        ('szAutodialFunc', ctypes.c_wchar * 260),
        ('szDeviceType', ctypes.c_wchar * 17),
        ('szDeviceName', ctypes.c_wchar * 129),
        ('szX25PadType', ctypes.c_wchar * 33),
        ('szX25Address', ctypes.c_wchar * 201),
        ('szX25Facilities', ctypes.c_wchar * 201),
        ('szX25UserData', ctypes.c_wchar * 201),
        ('dwChannels', wintypes.DWORD),
        ('dwReserved1', wintypes.DWORD),
        ('dwReserved2', wintypes.DWORD),
    ]

class WindowsRASDialer:
    def __init__(self, entry_name=ENTRY_NAME):
        self.entry_name = entry_name
        self.is_connected = False
        self.connect_start_time = None
        self.initial_bytes_sent = 0
        self.initial_bytes_recv = 0

    @staticmethod
    def get_pbk_path():
        """Returns the user phonebook path."""
        appdata = os.environ.get("APPDATA", "")
        pbk_dir = os.path.join(appdata, "Microsoft", "Network", "Connections", "Pbk")
        os.makedirs(pbk_dir, exist_ok=True)
        return os.path.join(pbk_dir, "rasphone.pbk")

    @staticmethod
    def get_huawei_modem_info():
        """Reads the installed Huawei 3G Modem name and AttachedTo COM port from Registry."""
        modem_name = "HUAWEI Mobile Connect - 3G Modem"
        modem_port = "COM13"
        try:
            key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e96d-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base_key:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(base_key, i)
                        i += 1
                        if len(sub_name) != 4:
                            continue
                        with winreg.OpenKey(base_key, sub_name) as sub_key:
                            match_id, _ = winreg.QueryValueEx(sub_key, "MatchingDeviceId")
                            if "vid_12d1" in match_id.lower():
                                friendly, _ = winreg.QueryValueEx(sub_key, "FriendlyName")
                                attached, _ = winreg.QueryValueEx(sub_key, "AttachedTo")
                                if friendly:
                                    modem_name = friendly
                                if attached:
                                    modem_port = attached
                                break
                    except OSError:
                        break
        except Exception:
            pass
        return modem_name, modem_port

    def configure_modem_apn(self, carrier="MobiFone", modem_port=None):
        """Sends AT+CGDCONT=1,"IP","<apn>" to the modem before dialing."""
        cfg = CARRIER_APNS.get(carrier, CARRIER_APNS["Default"])
        apn = cfg["apn"]
        if not modem_port:
            _, modem_port = self.get_huawei_modem_info()
        try:
            with serial.Serial(modem_port, 115200, timeout=1.0) as s:
                cmd = f'AT+CGDCONT=1,"IP","{apn}"\r\n'.encode("ascii")
                s.write(cmd)
                time.sleep(0.2)
                s.read_all()
        except Exception:
            pass

    def ensure_phonebook_entry(self, carrier="MobiFone"):
        """Creates a valid Windows 11 PBVersion=8 RAS entry with Default Gateway (IpPrioritizeRemote=1)."""
        cfg = CARRIER_APNS.get(carrier, CARRIER_APNS["Default"])
        modem_name, modem_port = self.get_huawei_modem_info()
        pbk_path = self.get_pbk_path()

        # If not currently connected, recreate cleanly so RasSetEntryPropertiesW writes a fresh PBVersion=8 block
        if not self.check_status() and os.path.exists(pbk_path):
            try:
                os.remove(pbk_path)
            except Exception:
                pass

        entry = RASENTRYW_Win11()
        entry.dwSize = ctypes.sizeof(RASENTRYW_Win11)  # 3468 bytes
        # 0x00000001 = RASEO_RemoteDefaultGateway (sets Default Gateway 0.0.0.0 so Windows routes Mobile Data!)
        # 0x00000200 = RASEO_ModemLights
        # 0x04000000 = RASEO_PreviewUserPw
        entry.dwfOptions = 0x04000000 | 0x00000200 | 0x00000001
        entry.szLocalPhoneNumber = cfg["number"]
        entry.dwfNetProtocols = 4  # RASNP_Ip
        entry.dwFramingProtocol = 1  # RASFP_Ppp
        entry.szDeviceType = "modem"
        entry.szDeviceName = modem_name

        ctypes.windll.rasapi32.RasSetEntryPropertiesW(
            None,
            self.entry_name,
            ctypes.byref(entry),
            entry.dwSize,
            None,
            0
        )

        # Ensure the MEDIA/DEVICE block & Default Gateway metric in rasphone.pbk bind to Huawei Modem & route traffic
        if os.path.exists(pbk_path):
            with open(pbk_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            text = re.sub(r"IpPrioritizeRemote=\d+", "IpPrioritizeRemote=1", text)
            text = re.sub(r"IpInterfaceMetric=\d+", "IpInterfaceMetric=0", text)
            text = re.sub(r"PreferredPort=.*", "PreferredPort=", text)
            text = re.sub(r"PreferredDevice=.*", "PreferredDevice=", text)

            new_tail = (
                f"MEDIA=serial\nPort={modem_port}\nConnectBPS=921600\n\n"
                f"DEVICE=modem\nPhoneNumber={cfg['number']}\nAreaCode=\n"
                f"CountryCode=84\nCountryID=84\nUseDialingRules=0\nComment=\n"
                f"FriendlyName={modem_name}\nLastSelectedPhone=0\n"
                f"PromoteAlternates=0\nTryNextAlternateOnFail=1\n"
                f"HwFlowControl=1\nProtocol=1\nCompression=1\nSpeaker=0\nMdmProtocol=0\n"
            )
            text = re.sub(r"MEDIA=serial[\s\S]*", new_tail, text)
            for _ in range(5):
                try:
                    with open(pbk_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    break
                except PermissionError:
                    time.sleep(0.15)
        return True

    def connect(self, carrier="MobiFone", user="", password=""):
        """Connects via Windows rasdial."""
        self.ensure_phonebook_entry(carrier)
        self.configure_modem_apn(carrier)

        cfg = CARRIER_APNS.get(carrier, CARRIER_APNS["Default"])
        u = user if user else cfg["user"]
        p = password if password else cfg["pass"]

        cmd = f'rasdial "{self.entry_name}" {u} {p}'.strip()
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = (res.stdout + "\n" + res.stderr).strip()
            if "Successfully connected" in output or "Command completed successfully" in output or res.returncode == 0:
                self.is_connected = True
                if not self.connect_start_time:
                    self.connect_start_time = time.time()
                    net_io = psutil.net_io_counters()
                    self.initial_bytes_sent = net_io.bytes_sent
                    self.initial_bytes_recv = net_io.bytes_recv
                ip = self.get_ppp_ip()
                ip_suffix = f" (IP: {ip})" if ip else ""
                return True, f"Đã kết nối Internet 3G thành công!{ip_suffix}"
            else:
                if os.path.exists(r"C:\Windows\System32\drivers\ewusbmdm.sys") and ("797" in output or "692" in output):
                    return False, (
                        "Không thể mở cổng Modem 3G (Driver ewusbmdm.sys cũ đang bị Windows 11 HVCI chặn).\n"
                        "Hãy bấm nút 'Sửa lỗi Driver HVCI (1-Click)' ở thanh thông báo phía trên!"
                    )
                return False, f"Kết nối thất bại:\n{output}"
        except Exception as e:
            return False, f"Lỗi RAS Dial: {e}"

    @staticmethod
    def get_ppp_ip():
        """Returns the IPv4 address of the active FastConnect3G PPP interface, if any."""
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                if ENTRY_NAME.lower() in iface.lower() or "ppp" in iface.lower():
                    for a in addrs:
                        if a.family == 2 and a.address and not a.address.startswith("127."):
                            return a.address
        except Exception:
            pass
        return ""

    def disconnect(self):
        """Disconnects the active 3G connection."""
        cmd = f'rasdial "{self.entry_name}" /DISCONNECT'
        try:
            subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            self.is_connected = False
            self.connect_start_time = None
            return True, "Đã ngắt kết nối."
        except Exception as e:
            return False, f"Lỗi khi ngắt kết nối: {e}"

    def check_status(self):
        """Checks if FastConnect3G is actively connected."""
        try:
            res = subprocess.run("rasdial", shell=True, capture_output=True, text=True, timeout=5)
            if self.entry_name.lower() in res.stdout.lower():
                if not self.is_connected or not self.connect_start_time:
                    self.connect_start_time = time.time()
                    net_io = psutil.net_io_counters()
                    self.initial_bytes_sent = net_io.bytes_sent
                    self.initial_bytes_recv = net_io.bytes_recv
                self.is_connected = True
                return True
            self.is_connected = False
            return False
        except Exception:
            return False

    def get_traffic_stats(self):
        """Returns (uptime_str, upload_mb, download_mb) for the 3G PPP interface."""
        if not self.is_connected or not self.connect_start_time:
            return ("00:00:00", 0.0, 0.0)

        elapsed = int(time.time() - self.connect_start_time)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        uptime_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        try:
            per_nic = psutil.net_io_counters(pernic=True)
            ppp_io = per_nic.get(self.entry_name)
            if ppp_io:
                up_mb = max(0.0, ppp_io.bytes_sent / (1024 * 1024))
                down_mb = max(0.0, ppp_io.bytes_recv / (1024 * 1024))
                return (uptime_str, round(up_mb, 2), round(down_mb, 2))
            net_io = psutil.net_io_counters()
            up_mb = max(0.0, (net_io.bytes_sent - self.initial_bytes_sent) / (1024 * 1024))
            down_mb = max(0.0, (net_io.bytes_recv - self.initial_bytes_recv) / (1024 * 1024))
            return (uptime_str, round(up_mb, 2), round(down_mb, 2))
        except Exception:
            return (uptime_str, 0.0, 0.0)
