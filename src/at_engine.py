"""
AT Command & Telemetry Engine for Huawei 3G Modems (Fast Connect / E173)
Handles COM port detection, signal monitoring (CSQ), operator detection (COPS),
USSD commands (*101#) with UCS2 decoding, and SMS sending/receiving.
"""

import time
import re
import threading
import serial
import serial.tools.list_ports

class HuaweiATEngine:
    def __init__(self, port=None, baudrate=115200, timeout=2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.lock = threading.Lock()
        self.is_connected = False
        self.device_info = {}

    @staticmethod
    def list_candidate_ports():
        """Lists potential Huawei COM ports using hardware IDs or device description."""
        ports = serial.tools.list_ports.comports()
        candidates = []
        for p in ports:
            hwid = (p.hwid or "").upper()
            desc = (p.description or "").upper()
            # Huawei VID: 12D1, PID: 1436 or 140C or generic Huawei/Mobile
            if "12D1" in hwid or "HUAWEI" in desc or "MOBILE" in desc:
                candidates.append((p.device, p.description, hwid))
            elif "USB SERIAL" in desc:
                candidates.append((p.device, p.description, hwid))
        return candidates

    def auto_connect(self):
        """Scans candidate ports and connects to the active PC UI / AT port."""
        candidates = self.list_candidate_ports()
        if not candidates:
            # Fallback to all COM ports
            candidates = [(p.device, p.description, p.hwid) for p in serial.tools.list_ports.comports()]

        for dev, desc, hwid in candidates:
            try:
                s = serial.Serial(dev, self.baudrate, timeout=1.0)
                # Test with ATE0 and ATI
                s.write(b"ATE0\r\n")
                time.sleep(0.15)
                s.read_all()
                s.write(b"ATI\r\n")
                time.sleep(0.3)
                resp = s.read_all().decode("ascii", errors="ignore")
                s.close()
                if "HUAWEI" in resp.upper() or "OK" in resp.upper():
                    self.port = dev
                    self.connect(dev)
                    self.fetch_device_info()
                    return True, f"Connected to {dev} ({desc})"
            except Exception:
                continue

        return False, "No responsive Huawei AT port found."

    def connect(self, port=None):
        if port:
            self.port = port
        if not self.port:
            raise ValueError("Port not specified.")

        with self.lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.ser.write(b"ATE0\r\n")
            time.sleep(0.1)
            self.ser.read_all()
            self.is_connected = True

    def disconnect(self):
        with self.lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.is_connected = False

    def send_cmd(self, cmd, wait_time=0.3, max_timeout=3.0):
        """Sends an AT command and returns cleaned response lines."""
        if not self.ser or not self.ser.is_open:
            return []

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                full_cmd = (cmd.strip() + "\r\n").encode("ascii")
                self.ser.write(full_cmd)
                
                lines = []
                start = time.time()
                while time.time() - start < max_timeout:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        lines.append(line)
                        if line in ("OK", "ERROR", "COMMAND NOT SUPPORT") or "CME ERROR" in line or "CMS ERROR" in line:
                            break
                    time.sleep(0.05)
                return lines
            except Exception as e:
                return [f"ERROR: {e}"]

    def fetch_device_info(self):
        """Queries ATI, Model, IMEI, Firmware."""
        lines = self.send_cmd("ATI")
        info = {"Raw": "\n".join(lines)}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        # Query IMSI
        cimi = self.send_cmd("AT+CIMI")
        for line in cimi:
            if line.isdigit() and len(line) >= 14:
                info["IMSI"] = line
        self.device_info = info
        return info

    def get_signal_quality(self):
        """
        Queries AT+CSQ
        Returns (rssi_raw, ber, rssi_dbm, percentage, bars)
        """
        lines = self.send_cmd("AT+CSQ")
        for line in lines:
            m = re.search(r"\+CSQ:\s*(\d+),(\d+)", line)
            if m:
                rssi = int(m.group(1))
                ber = int(m.group(2))
                if rssi == 99:
                    return (99, ber, -113, 0, 0)
                # Formula: dBm = -113 + (rssi * 2)
                dbm = -113 + (rssi * 2)
                percentage = min(100, int((rssi / 31.0) * 100))
                if rssi >= 20: bars = 5
                elif rssi >= 15: bars = 4
                elif rssi >= 10: bars = 3
                elif rssi >= 5: bars = 2
                elif rssi >= 1: bars = 1
                else: bars = 0
                return (rssi, ber, dbm, percentage, bars)
        return (99, 99, -113, 0, 0)

    PLMN_MAP = {
        "45201": "MobiFone",
        "45202": "VinaPhone",
        "45204": "Viettel",
        "45205": "Vietnamobile",
        "45207": "Gmobile",
        "45208": "Itelecom",
        "45209": "Reddi",
    }

    def get_network_operator(self):
        """Queries AT+COPS? returns (operator_name, act_tech_str)"""
        lines = self.send_cmd("AT+COPS?")
        for line in lines:
            m = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)"(?:,(\d+))?', line)
            if m:
                oper = m.group(1).strip()
                oper = self.PLMN_MAP.get(oper, oper)
                act = m.group(2)
                tech = "3G / UMTS"
                if act == "0": tech = "2G / GSM"
                elif act == "2": tech = "3G / UMTS"
                elif act == "4": tech = "3G / HSDPA"
                elif act == "5": tech = "3G / HSUPA"
                elif act == "6": tech = "3G / HSPA+"
                elif act == "7": tech = "4G / LTE"
                return oper, tech
        return "Unknown", "No Service"

    def get_network_registration(self):
        """Queries AT+CREG? returns status string."""
        lines = self.send_cmd("AT+CREG?")
        for line in lines:
            m = re.search(r"\+CREG:\s*\d+,(\d+)", line)
            if m:
                code = int(m.group(1))
                stat_map = {
                    0: "Not registered",
                    1: "Registered, home network",
                    2: "Searching...",
                    3: "Registration denied",
                    4: "Unknown",
                    5: "Registered, roaming"
                }
                return stat_map.get(code, "Unknown")
        return "Unknown"

    @staticmethod
    def decode_ussd_response(raw_text):
        """Decodes raw USSD response (ASCII text or UCS-2 Hex encoded)."""
        # Check if text is all hexadecimal and length is multiple of 4
        clean = raw_text.strip().replace('"', '')
        if re.fullmatch(r"[0-9A-Fa-f]{8,}", clean) and len(clean) % 4 == 0:
            try:
                decoded_bytes = bytes.fromhex(clean)
                return decoded_bytes.decode("utf-16-be", errors="ignore")
            except Exception:
                pass
        return clean

    def send_ussd(self, ussd_code="*101#", timeout=10.0):
        """Sends USSD code (e.g. *101# or *100*code#) and decodes response."""
        if not self.ser or not self.ser.is_open:
            return False, "Modem not connected."

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                cmd = f'AT+CUSD=1,"{ussd_code}",15\r\n'.encode("ascii")
                self.ser.write(cmd)

                start = time.time()
                while time.time() - start < timeout:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if "+CUSD:" in line:
                        # Extract the message inside quotes
                        m = re.search(r'\+CUSD:\s*\d+,"([^"]*)"', line)
                        if m:
                            raw_msg = m.group(1)
                            decoded = self.decode_ussd_response(raw_msg)
                            return True, decoded
                        else:
                            return True, line
                    elif "ERROR" in line:
                        return False, f"USSD Error: {line}"
                    time.sleep(0.1)
                return False, "USSD timed out waiting for network response."
            except Exception as e:
                return False, f"USSD Exception: {e}"

    def list_sms(self):
        """Lists incoming SMS from SIM storage."""
        self.send_cmd("AT+CMGF=1") # Text mode
        self.send_cmd('AT+CPMS="SM","SM","SM"')
        lines = self.send_cmd('AT+CMGL="ALL"', max_timeout=5.0)
        messages = []
        cur_msg = None
        for line in lines:
            if line.startswith("+CMGL:"):
                # +CMGL: index,"status","sender",,"date time"
                parts = line.split(",")
                idx = parts[0].replace("+CMGL:", "").strip()
                status = parts[1].replace('"', '').strip() if len(parts) > 1 else ""
                sender = parts[2].replace('"', '').strip() if len(parts) > 2 else ""
                datetime_str = parts[4].replace('"', '').strip() if len(parts) > 4 else ""
                cur_msg = {
                    "index": idx,
                    "status": status,
                    "sender": sender,
                    "date": datetime_str,
                    "body": ""
                }
                messages.append(cur_msg)
            elif cur_msg is not None and line not in ("OK", "ERROR"):
                if cur_msg["body"]:
                    cur_msg["body"] += "\n" + line
                else:
                    cur_msg["body"] = line
        return messages

    def send_sms(self, phone_number, message_text):
        """Sends an SMS message in Text mode."""
        if not self.ser or not self.ser.is_open:
            return False, "Modem not connected."

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(b"AT+CMGF=1\r\n")
                time.sleep(0.2)
                self.ser.read_all()

                cmd = f'AT+CMGS="{phone_number}"\r\n'.encode("ascii")
                self.ser.write(cmd)
                
                # Wait for prompt '>'
                time.sleep(0.3)
                prompt = self.ser.read_all().decode("ascii", errors="ignore")
                if ">" not in prompt:
                    return False, f"No SMS prompt returned: {prompt}"

                # Send message text terminated with Ctrl+Z (0x1A)
                payload = message_text.encode("utf-8") + b"\x1a"
                self.ser.write(payload)

                # Wait for response
                start = time.time()
                while time.time() - start < 10.0:
                    line = self.ser.readline().decode("ascii", errors="ignore").strip()
                    if "+CMGS:" in line or "OK" in line:
                        return True, "SMS sent successfully!"
                    elif "ERROR" in line:
                        return False, f"Failed to send SMS: {line}"
                    time.sleep(0.1)

                return False, "SMS send timed out."
            except Exception as e:
                return False, f"SMS Exception: {e}"

    def dial_voice_call(self, phone_number):
        """Initiates an outgoing voice call via ATD<number>;"""
        clean_num = re.sub(r"[^\d+*#]", "", str(phone_number).strip())
        if not clean_num:
            return False, "Số điện thoại không hợp lệ."
        if not self.ser or not self.ser.is_open:
            return False, "Modem chưa kết nối."

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                cmd = f"ATD{clean_num};\r\n".encode("ascii")
                self.ser.write(cmd)
                time.sleep(0.3)
                resp = self.ser.read_all().decode("ascii", errors="ignore")
                if "ERROR" in resp:
                    return False, f"Lỗi quay số: {resp.strip()}"
                return True, f"Đang gọi đến {clean_num}..."
            except Exception as e:
                return False, f"Lỗi ngoại lệ cuộc gọi: {e}"

    def hangup_call(self):
        """Hangs up any active or outgoing call via AT+CHUP / ATH."""
        if not self.ser or not self.ser.is_open:
            return False, "Modem chưa kết nối."

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(b"AT+CHUP\r\nATH\r\n")
                time.sleep(0.2)
                resp = self.ser.read_all().decode("ascii", errors="ignore")
                return True, "Đã kết thúc cuộc gọi."
            except Exception as e:
                return False, f"Lỗi ngắt cuộc gọi: {e}"

    def answer_call(self):
        """Answers an incoming call via ATA."""
        if not self.ser or not self.ser.is_open:
            return False, "Modem chưa kết nối."

        with self.lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(b"ATA\r\n")
                time.sleep(0.3)
                resp = self.ser.read_all().decode("ascii", errors="ignore")
                return True, "Đã nhận cuộc gọi."
            except Exception as e:
                return False, f"Lỗi nhận cuộc gọi: {e}"

    def get_call_status(self):
        """
        Queries AT+CLCC for active/incoming/alerting calls.
        Returns list of dict: [{'id': 1, 'dir': 0/1, 'stat': 'active'/'dialing'/'alerting', 'number': '...'}]
        """
        if not self.ser or not self.ser.is_open:
            return []

        lines = self.send_cmd("AT+CLCC", wait_time=0.2, max_timeout=1.0)
        calls = []
        stat_map = {
            "0": "Active",
            "1": "Held",
            "2": "Dialing",
            "3": "Alerting (Đang đổ chuông)",
            "4": "Incoming (Cuộc gọi đến)",
            "5": "Waiting",
            "6": "Disconnect"
        }
        for line in lines:
            if line.startswith("+CLCC:"):
                # +CLCC: <id>,<dir>,<stat>,<mode>,<mpty>[,<number>,<type>]
                parts = line.split(",")
                if len(parts) >= 3:
                    cid = parts[0].replace("+CLCC:", "").strip()
                    direction = "Outgoing" if parts[1].strip() == "0" else "Incoming"
                    st_code = parts[2].strip()
                    st_name = stat_map.get(st_code, f"Status {st_code}")
                    num = parts[5].replace('"', '').strip() if len(parts) > 5 else "Unknown"
                    calls.append({
                        "id": cid,
                        "dir": direction,
                        "stat_code": st_code,
                        "status": st_name,
                        "number": num
                    })
        return calls

    def set_radio_mode(self, mode="3g_only"):
        """
        Locks radio band:
        '3g_only': AT^SYSCFG=14,2,3FFFFFFF,1,2 (WCDMA only)
        'auto': AT^SYSCFG=2,1,3FFFFFFF,1,2 (Auto 2G/3G)
        """
        if mode == "3g_only":
            cmd = "AT^SYSCFG=14,2,3FFFFFFF,1,2"
        else:
            cmd = "AT^SYSCFG=2,1,3FFFFFFF,1,2"
        lines = self.send_cmd(cmd, wait_time=0.4, max_timeout=2.0)
        ok = any("OK" in l for l in lines)
        return ok, "\n".join(lines)

if __name__ == "__main__":
    print("Testing HuaweiATEngine...")
    engine = HuaweiATEngine()
    ok, msg = engine.auto_connect()
    print("Auto connect:", ok, "-", msg)
    if ok:
        print("Device Info:", engine.device_info)
        print("Signal Quality:", engine.get_signal_quality())
        print("Network Operator:", engine.get_network_operator())
        engine.disconnect()
