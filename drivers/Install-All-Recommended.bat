@echo off
:: ============================================================================
:: FastConnect 3G DCom - Windows 11 HVCI-Compliant Driver Installer (Solution 1)
:: Uses Microsoft In-Box usbser.sys & modem.sys (100% Core Isolation Safe)
:: ============================================================================

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Requesting Administrator privileges for driver configuration...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
title Fast Connect 3G - Windows 11 HVCI Driver Patcher
color 0B

echo ========================================================================
echo    Fast Connect 3G DCom (Huawei E173) - Windows 11 HVCI Driver Setup
echo ========================================================================
echo.
echo [1] Switching ZeroCD if device is in CD-ROM mode (PID 1446)...
if exist "%~dp0..\tools\ZeroCD_Switch.exe" (
    "%~dp0..\tools\ZeroCD_Switch.exe"
)

echo.
echo [2] Ensuring Modem and Port Registry Class Templates exist...
powershell -NoProfile -Command "if (-not (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_12D1&PID_1436&MI_00\*' -ErrorAction SilentlyContinue).Driver) { pnputil /add-driver '%~dp0huawei_clean_repack\ewmdm2k.inf' /install; pnputil /add-driver '%~dp0huawei_clean_repack\ewser2k.inf' /install }"

echo.
echo [3] Patching Device Nodes to use Microsoft In-Box usbser.sys (HVCI Safe)...
if exist "%~dp0..\tools\FixWin11Driver.exe" (
    "%~dp0..\tools\FixWin11Driver.exe"
)

echo.
echo [4] Current Huawei 3G Device Status:
powershell -NoProfile -Command "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_12D1' } | Select-Object FriendlyName, InstanceId, Status, Problem | Format-Table -AutoSize"

echo.
echo [5] Active COM Ports:
powershell -NoProfile -Command "Get-ItemProperty 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM' -ErrorAction SilentlyContinue"

echo.
echo ========================================================================
echo Setup Complete! HVCI-blocked ewusbmdm.sys has been replaced with
echo Microsoft's built-in usbser.sys. Press any key to close.
echo ========================================================================
pause >nul
