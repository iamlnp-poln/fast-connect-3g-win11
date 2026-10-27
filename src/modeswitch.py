"""
ZeroCD User-Mode Switcher & PnP State Detector for Huawei 3G Modems (Windows 11)
Reverse Engineered for MobiFone Fast Connect (Huawei E173)
Translates USB\\VID_12D1&PID_1446 (ZeroCD storage) <-> USB\\VID_12D1&PID_1436 / PID_1003 (Modem)
without requiring any legacy kernel filter driver (ew_hwusbdev.sys).
"""

import ctypes
import ctypes.wintypes
import time
import os
import serial.tools.list_ports

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
IOCTL_SCSI_PASS_THROUGH = 0x04D004
INVALID_HANDLE_VALUE = -1

DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_ulong),
        ('Data2', ctypes.c_ushort),
        ('Data3', ctypes.c_ushort),
        ('Data4', ctypes.c_ubyte * 8)
    ]

class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.wintypes.DWORD),
        ('ClassGuid', GUID),
        ('DevInst', ctypes.wintypes.DWORD),
        ('Reserved', ctypes.c_size_t)
    ]

class SCSI_PASS_THROUGH(ctypes.Structure):
    _fields_ = [
        ('Length', ctypes.c_ushort),
        ('ScsiStatus', ctypes.c_ubyte),
        ('PathId', ctypes.c_ubyte),
        ('TargetId', ctypes.c_ubyte),
        ('Lun', ctypes.c_ubyte),
        ('CdbLength', ctypes.c_ubyte),
        ('SenseInfoLength', ctypes.c_ubyte),
        ('DataIn', ctypes.c_ubyte),
        ('DataTransferLength', ctypes.c_ulong),
        ('TimeOutValue', ctypes.c_ulong),
        ('DataBufferOffset', ctypes.c_size_t),
        ('SenseInfoOffset', ctypes.c_ulong),
        ('Cdb', ctypes.c_ubyte * 16),
    ]

# SetupAPI / CfgMgr32 binding
setupapi = ctypes.windll.setupapi
cfgmgr32 = ctypes.windll.cfgmgr32

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.wintypes.DWORD]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.c_wchar_p, ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD)
]
cfgmgr32.CM_Get_DevNode_Status.argtypes = [
    ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.wintypes.DWORD, ctypes.wintypes.ULONG
]


def query_present_huawei_devices():
    """
    Directly queries Windows PnP Manager via setupapi.dll for physically PRESENT Huawei USB devices.
    Runs in < 1ms, completely non-blocking, zero subprocesses.
    Returns: list of dicts [{'id': ..., 'pid': ..., 'status': ..., 'problem': ...}]
    """
    hdev = setupapi.SetupDiGetClassDevsW(None, "USB", None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if hdev == -1 or not hdev:
        return []

    devdata = SP_DEVINFO_DATA()
    devdata.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
    results = []
    idx = 0
    buf = ctypes.create_unicode_buffer(512)
    req = ctypes.wintypes.DWORD()
    status = ctypes.wintypes.DWORD()
    problem = ctypes.wintypes.DWORD()

    while setupapi.SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(devdata)):
        idx += 1
        if setupapi.SetupDiGetDeviceInstanceIdW(hdev, ctypes.byref(devdata), buf, 512, ctypes.byref(req)):
            val = buf.value.upper()
            if "12D1" in val:
                cfgmgr32.CM_Get_DevNode_Status(ctypes.byref(status), ctypes.byref(problem), devdata.DevInst, 0)
                pid = None
                for part in val.replace("&", " ").replace("\\", " ").split():
                    if part.startswith("PID_"):
                        pid = part[4:8]
                results.append({
                    "id": val,
                    "pid": pid,
                    "status": status.value,
                    "problem": problem.value
                })

    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return results


def find_zerocd_drive():
    """Finds the drive letter for the Huawei ZeroCD virtual CD-ROM."""
    kernel32 = ctypes.windll.kernel32
    for letter in ["E", "D", "F", "G", "H", "I", "J", "K"]:
        path = f"{letter}:\\"
        try:
            # DRIVE_CDROM = 5. Only check physical/virtual optical drives to avoid false positives on hard drives
            if kernel32.GetDriveTypeW(path) == 5:
                if (os.path.exists(os.path.join(path, "AutoRun.exe")) or
                    os.path.exists(os.path.join(path, "fast connect")) or
                    os.path.exists(os.path.join(path, "SysConfig.dat")) or
                    os.path.exists(os.path.join(path, "driver"))):
                    return letter
        except Exception:
            continue
    return None


def get_device_state():
    """
    Evaluates current real-time state of the DCom hardware.
    Returns: (state, detail, drive_letter, has_driver_error)
    state: 'DISCONNECTED', 'ZEROCD', 'MODEM'
    """
    present_devices = query_present_huawei_devices()
    cd_drive = find_zerocd_drive()

    # Check active serial ports for Huawei COM ports
    com_ports = []
    try:
        ports = serial.tools.list_ports.comports()
        for p in ports:
            hwid = (p.hwid or "").upper()
            desc = (p.description or "").upper()
            if ("12D1" in hwid or "HUAWEI" in desc) and "BTH" not in hwid:
                com_ports.append(p.device)
    except Exception:
        pass

    # 1. DISCONNECTED state:
    # No present Huawei USB devices, no Huawei COM ports, and no ZeroCD drive
    if len(present_devices) == 0 and len(com_ports) == 0 and cd_drive is None:
        return "DISCONNECTED", "Chưa cắm thiết bị DCom 3G", None, False

    # Extract present PIDs
    pids = {d["pid"] for d in present_devices if d["pid"]}

    # Check for hardware driver errors (Code 28 = Not installed, Code 39 = HVCI Blocked, Code 31 = Failed add)
    has_problem = any(
        d["problem"] in (28, 31, 39) or (d["problem"] != 0 and "&MI_" in d["id"])
        for d in present_devices
    )
    if ("1436" in pids or "1003" in pids) and len(com_ports) == 0:
        has_problem = True

    # 2. ZEROCD state:
    # Present device has PID 1446, OR CD drive exists while no working modem COM ports are open
    if "1446" in pids or (len(com_ports) == 0 and cd_drive is not None and "1436" not in pids and "1003" not in pids):
        return "ZEROCD", f"Chế độ Ổ đĩa ảo ZeroCD ({cd_drive or 'E'}:\\)", cd_drive or "E", False

    # 3. MODEM state (User Mode):
    # PID 1436 or PID 1003 or active COM ports
    if "1436" in pids or "1003" in pids or len(com_ports) > 0:
        driver_err = has_problem
        pid_label = "PID_1436" if "1436" in pids else ("PID_1003" if "1003" in pids else "Modem 3G")
        return "MODEM", f"Chế độ Modem 3G ({pid_label})", cd_drive, driver_err

    # Fallback to ZeroCD if drive exists
    if cd_drive:
        return "ZEROCD", f"Chế độ Ổ đĩa ảo ZeroCD ({cd_drive}:\\)", cd_drive, False

    return "DISCONNECTED", "Chưa cắm thiết bị DCom 3G", None, False


def send_huawei_switch_scsi(drive_letter="E"):
    """Sends Huawei SCSI mode-switch command to the virtual CD-ROM drive."""
    drive_clean = drive_letter.rstrip(":\\/")
    device_path = f"\\\\.\\{drive_clean}:"

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        device_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if handle == INVALID_HANDLE_VALUE:
        err = kernel32.GetLastError()
        return False, f"Không thể mở ổ đĩa {device_path} (Lỗi Win32: {err})"

    try:
        # Huawei ZeroCD mode-switch SCSI CDB:
        # 11 06 20 00 00 01 00 00 00 00 00 00 00 00 00 00
        cdb_bytes = [0x11, 0x06, 0x20, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        
        spt = SCSI_PASS_THROUGH()
        spt.Length = ctypes.sizeof(SCSI_PASS_THROUGH)
        spt.CdbLength = 16
        spt.SenseInfoLength = 32
        spt.DataIn = 2  # SCSI_IOCTL_DATA_UNSPECIFIED
        spt.DataTransferLength = 0
        spt.TimeOutValue = 5
        spt.SenseInfoOffset = spt.Length
        for i, b in enumerate(cdb_bytes):
            spt.Cdb[i] = b

        total_size = spt.Length + 32
        buf = (ctypes.c_ubyte * total_size)()
        ctypes.memmove(ctypes.byref(buf), ctypes.byref(spt), spt.Length)

        bytes_returned = ctypes.c_ulong(0)
        res = kernel32.DeviceIoControl(
            handle,
            IOCTL_SCSI_PASS_THROUGH,
            ctypes.byref(buf),
            total_size,
            ctypes.byref(buf),
            total_size,
            ctypes.byref(bytes_returned),
            None
        )
        err = kernel32.GetLastError()
        # Error 121 (ERROR_SEM_TIMEOUT) or 0 indicates the device acknowledged and bus reset
        if res != 0 or err in (0, 121):
            return True, "Lệnh chuyển mạch SCSI đã được tiếp nhận (Bus reset)."
        else:
            return False, f"DeviceIoControl thất bại với mã lỗi: {err}"
    finally:
        kernel32.CloseHandle(handle)


def auto_detect_and_switch():
    """Detects if ZeroCD is present, finds drive letter, and switches it to Modem User Mode."""
    state, detail, drive, _ = get_device_state()
    if state == "MODEM":
        return True, "Thiết bị đã ở chế độ Modem 3G (User Mode)."
    if state == "DISCONNECTED":
        return False, "Chưa cắm thiết bị DCom 3G vào máy tính."

    if not drive:
        drive = find_zerocd_drive() or "E"

    ok, msg = send_huawei_switch_scsi(drive)
    if not ok:
        return False, f"Không thể gửi lệnh SCSI đến ổ {drive}:\\: {msg}"

    # Poll up to 6 seconds for transition to MODEM
    for _ in range(6):
        time.sleep(1.0)
        new_state, _, _, _ = get_device_state()
        if new_state == "MODEM":
            return True, "Đã chuyển sang Chế độ Modem 3G (User Mode) thành công!"

    return True, "Đã gửi lệnh chuyển mạch SCSI, đang nạp cổng Modem..."


def switch_modem_to_zerocd(at_engine=None):
    """Switches modem from User Mode back to ZeroCD mode."""
    # 1. Try through existing or auto-connected at_engine
    if at_engine:
        if not at_engine.is_connected:
            at_engine.auto_connect()
        if at_engine.is_connected:
            try:
                at_engine.send_cmd("AT^U2DIAG=1", wait_time=0.2)
                time.sleep(0.15)
                at_engine.send_cmd("AT+CFUN=1,1", wait_time=0.2)
                at_engine.disconnect()
                return True, "Đã gửi lệnh chuyển về Ổ đĩa ZeroCD (Thiết bị đang khởi động lại...)"
            except Exception:
                pass

    # 2. Try direct serial on all Huawei candidate ports with short 0.5s timeout
    try:
        ports = serial.tools.list_ports.comports()
        for p in ports:
            hwid = (p.hwid or "").upper()
            desc = (p.description or "").upper()
            if any(b in hwid for b in ("BTH", "BLUETOOTH", "BTHENUM")) or "BLUETOOTH" in desc:
                continue
            if "12D1" in hwid or "HUAWEI" in desc or ("MOBILE" in desc and "USB" in hwid):
                try:
                    import serial as ser
                    with ser.Serial(p.device, 115200, timeout=0.5) as s:
                        s.write(b"AT^U2DIAG=1\r\n")
                        time.sleep(0.15)
                        s.write(b"AT+CFUN=1,1\r\n")
                        time.sleep(0.2)
                    return True, "Đã gửi lệnh chuyển về Ổ đĩa ZeroCD!"
                except Exception:
                    continue
    except Exception:
        pass

    # If the virtual CD-ROM drive already appeared, transition is done
    if find_zerocd_drive():
        return True, "Thiết bị đã ở chế độ Ổ đĩa ảo ZeroCD!"

    return False, "Không thể kết nối cổng AT để chuyển mạch (Vui lòng bấm 'Sửa lỗi Driver HVCI' trước)."


def restore_factory_modem_mode(at_engine=None):
    """Restores standard Huawei E173 User Mode (PID_1436: Modem + Mass Storage + Card Reader)."""
    if at_engine and at_engine.is_connected:
        try:
            at_engine.send_cmd("AT^U2DIAG=255")
            time.sleep(0.3)
            at_engine.send_cmd("AT+CFUN=1,1")
            at_engine.disconnect()
            return True, "Đã khôi phục chế độ chuẩn PID_1436 (Modem + Storage + MicroSD)!"
        except Exception as e:
            return False, f"Lỗi: {e}"
    return False, "Modem chưa kết nối cổng AT."


def get_connected_huawei_pids():
    """Returns list of currently connected Huawei PIDs."""
    present = query_present_huawei_devices()
    return list({d["pid"] for d in present if d["pid"]})


if __name__ == "__main__":
    print("Testing get_device_state():")
    st, det, drv, err = get_device_state()
    print(f"State: {st}, Detail: {det}, Drive: {drv}, Driver Error: {err}")
