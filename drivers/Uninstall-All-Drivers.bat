@echo off
:: ============================================================================
:: FastConnect 3G DCom - Driver Uninstaller
:: ============================================================================

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

title Fast Connect 3G Driver Cleanup
color 0C
echo ========================================================================
echo        Cleaning up Huawei DCom OEM Drivers from Driver Store
echo ========================================================================
echo.

powershell -NoProfile -Command "Get-WindowsDriver -Online -All | Where-Object { $_.ProviderName -match 'Huawei' -or $_.OriginalFileName -match 'ewmdm|ewser|ewnet|huawei' } | ForEach-Object { Write-Host 'Removing: ' $_.DriverName ' (' $_.OriginalFileName ')'; pnputil /delete-driver $_.DriverName /uninstall /force }"

echo.
echo Scan complete. Press any key to exit.
pause >nul
