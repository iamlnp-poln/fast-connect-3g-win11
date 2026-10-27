"""
Fast Connect 3G - Main Application Launcher
Official WinUI 3 Fluent Design Edition for Windows 11
"""

import sys
import os
from PyQt6.QtWidgets import QApplication

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

base_dir = get_base_dir()
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.modeswitch import auto_detect_and_switch, get_connected_huawei_pids
from src.winui3_app import WinUI3MainWindow

def main():
    print("=" * 65)
    print("  Fast Connect 3G - Windows 11 Official WinUI 3 Controller")
    print("  Reverse Engineered & Packaged for Huawei E173 / MobiFone DCom")
    print("=" * 65)

    # 1. Check if device is in ZeroCD storage mode (1446) and switch it
    pids = get_connected_huawei_pids()
    print(f"[*] Detected Huawei USB PIDs: {pids}")
    if "1446" in pids:
        print("[*] Device is in ZeroCD Mass Storage mode. Triggering user-mode switch...")
        ok, msg = auto_detect_and_switch()
        print(f"[*] ModeSwitch Result: {msg}")

    # 2. Launch Official WinUI 3 Fluent Interface
    print("[*] Starting WinUI 3 Control Center...")
    app = QApplication(sys.argv)
    window = WinUI3MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
