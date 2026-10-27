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

from src.winui3_app import WinUI3MainWindow

def main():
    print("=" * 65)
    print("  Fast Connect 3G - Windows 11 Official WinUI 3 Controller")
    print("  Reverse Engineered & Packaged for Huawei E173 / MobiFone DCom")
    print("=" * 65)

    # Launch Official WinUI 3 Fluent Interface immediately (Non-blocking)
    app = QApplication(sys.argv)
    window = WinUI3MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
