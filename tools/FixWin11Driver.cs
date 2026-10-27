using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32;

public class FixWin11Driver
{
    private const uint DIGCF_PRESENT = 0x00000002;
    private const uint DIGCF_ALLCLASSES = 0x00000004;

    private const uint SPDRP_SERVICE = 0x00000004;
    private const uint SPDRP_CONFIGFLAGS = 0x0000000A;
    private const uint SPDRP_LOWERFILTERS = 0x00000012;

    [StructLayout(LayoutKind.Sequential)]
    private struct SP_DEVINFO_DATA
    {
        public uint cbSize;
        public Guid ClassGuid;
        public uint DevInst;
        public IntPtr Reserved;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr SetupDiGetClassDevsW(
        IntPtr ClassGuid,
        string Enumerator,
        IntPtr hwndParent,
        uint Flags);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiEnumDeviceInfo(
        IntPtr DeviceInfoSet,
        uint MemberIndex,
        ref SP_DEVINFO_DATA DeviceInfoData);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetupDiGetDeviceInstanceIdW(
        IntPtr DeviceInfoSet,
        ref SP_DEVINFO_DATA DeviceInfoData,
        StringBuilder DeviceInstanceId,
        uint DeviceInstanceIdSize,
        out uint RequiredSize);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetupDiSetDeviceRegistryPropertyW(
        IntPtr DeviceInfoSet,
        ref SP_DEVINFO_DATA DeviceInfoData,
        uint Property,
        byte[] PropertyBuffer,
        uint PropertyBufferSize);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);

    private static void RunCmd(string file, string args)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(file, args)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            using (Process p = Process.Start(psi))
            {
                string output = p.StandardOutput.ReadToEnd();
                p.WaitForExit(15000);
                if (!string.IsNullOrWhiteSpace(output))
                    Console.WriteLine(output.Trim());
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("[!] Cmd error: " + ex.Message);
        }
    }

    public static void Main(string[] args)
    {
        Console.WriteLine("==================================================================");
        Console.WriteLine("  Fast Connect 3G - Windows 11 HVCI Driver Patcher (usbser.sys)");
        Console.WriteLine("==================================================================");

        // 1. Remove blocked W+X .sys binaries from System32\drivers so HVCI never pops up warnings
        string sysDrivers = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "drivers");
        string[] blockedSys = new string[] { "ewusbmdm.sys", "ewusbnet.sys", "ew_hwusbdev.sys", "ew_usbenumfilter.sys", "ewusbwwan.sys" };
        foreach (string sysFile in blockedSys)
        {
            string fullPath = Path.Combine(sysDrivers, sysFile);
            if (File.Exists(fullPath))
            {
                try
                {
                    File.Delete(fullPath);
                    Console.WriteLine("[+] Deleted HVCI-blocked driver binary: " + fullPath);
                }
                catch (Exception ex)
                {
                    Console.WriteLine("[!] Could not delete " + fullPath + ": " + ex.Message);
                }
            }
        }

        // 2. Clean up Ports Class Registry keys ({4d36e978-e325-11ce-bfc1-08002be10318})
        try
        {
            using (RegistryKey portsClass = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Class\{4d36e978-e325-11ce-bfc1-08002be10318}", true))
            {
                if (portsClass != null)
                {
                    foreach (string subName in portsClass.GetSubKeyNames())
                    {
                        if (subName.Length != 4) continue;
                        try
                        {
                            using (RegistryKey subKey = portsClass.OpenSubKey(subName, true))
                            {
                                if (subKey == null) continue;
                                string ntmp = subKey.GetValue("NTMPDriver") as string;
                                string matchId = (subKey.GetValue("MatchingDeviceId") as string ?? "").ToLowerInvariant();
                                if (ntmp == "ewusbmdm.sys" || matchId.Contains("vid_12d1"))
                                {
                                    subKey.DeleteValue("NTMPDriver", false);
                                    subKey.SetValue("PortSubClass", new byte[] { 2 }, RegistryValueKind.Binary);
                                    Console.WriteLine("[+] Patched Ports Class key " + subName + " (" + matchId + ") -> usbser.sys");
                                }
                            }
                        }
                        catch { }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("[!] Ports class registry patch error: " + ex.Message);
        }

        // 3. Patch Services\hwdatacard to point to in-box usbser.sys with KMDF Wdf parameters
        try
        {
            using (RegistryKey hwSvc = Registry.LocalMachine.CreateSubKey(@"SYSTEM\CurrentControlSet\Services\hwdatacard"))
            {
                if (hwSvc != null)
                {
                    hwSvc.SetValue("ImagePath", @"\SystemRoot\System32\drivers\usbser.sys", RegistryValueKind.ExpandString);
                    hwSvc.SetValue("DisplayName", "Huawei USB Serial (Microsoft In-Box usbser.sys)", RegistryValueKind.String);
                    hwSvc.SetValue("Start", 3, RegistryValueKind.DWord);
                    hwSvc.SetValue("Type", 1, RegistryValueKind.DWord);
                    using (RegistryKey wdfKey = hwSvc.CreateSubKey(@"Parameters\Wdf"))
                    {
                        wdfKey.SetValue("WdfMajorVersion", 1, RegistryValueKind.DWord);
                        wdfKey.SetValue("WdfMinorVersion", 15, RegistryValueKind.DWord);
                    }
                    Console.WriteLine("[+] Redirected service 'hwdatacard' -> \\SystemRoot\\System32\\drivers\\usbser.sys");
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("[!] Service registry patch error: " + ex.Message);
        }

        // 4. Use SetupAPI to rebind USB\VID_12D1&PID_1436 interfaces to Microsoft's in-box usbser & Modem
        IntPtr devInfo = SetupDiGetClassDevsW(IntPtr.Zero, "USB", IntPtr.Zero, DIGCF_PRESENT | DIGCF_ALLCLASSES);
        if (devInfo != new IntPtr(-1))
        {
            try
            {
                uint index = 0;
                SP_DEVINFO_DATA devData = new SP_DEVINFO_DATA();
                devData.cbSize = (uint)Marshal.SizeOf(typeof(SP_DEVINFO_DATA));

                while (SetupDiEnumDeviceInfo(devInfo, index, ref devData))
                {
                    index++;
                    StringBuilder sbId = new StringBuilder(512);
                    uint reqSize;
                    if (SetupDiGetDeviceInstanceIdW(devInfo, ref devData, sbId, (uint)sbId.Capacity, out reqSize))
                    {
                        string instanceId = sbId.ToString().ToUpperInvariant();
                        if (!instanceId.Contains("VID_12D1&PID_1436") && !instanceId.Contains("VID_12D1&PID_1003")) continue;

                        if (instanceId.Contains("&MI_00"))
                        {
                            // Modem interface: Service = "Modem", LowerFilters = "usbser\0\0"
                            byte[] svcBytes = Encoding.Unicode.GetBytes("Modem\0");
                            SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_SERVICE, svcBytes, (uint)svcBytes.Length);

                            byte[] filterBytes = Encoding.Unicode.GetBytes("usbser\0\0");
                            bool ok = SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_LOWERFILTERS, filterBytes, (uint)filterBytes.Length);

                            byte[] cfgFlags = BitConverter.GetBytes((uint)0);
                            SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_CONFIGFLAGS, cfgFlags, 4);

                            Console.WriteLine("[+] Bound MI_00 (3G Modem) LowerFilters -> usbser (OK=" + ok + ")");
                            RunCmd("pnputil.exe", "/restart-device \"" + sbId.ToString() + "\"");
                        }
                        else if (instanceId.Contains("&MI_03") || (instanceId.Contains("PID_1003") && instanceId.Contains("&MI_01")))
                        {
                            // Serial/PCUI interface: Service = "usbser", no LowerFilters
                            byte[] svcBytes = Encoding.Unicode.GetBytes("usbser\0");
                            bool ok = SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_SERVICE, svcBytes, (uint)svcBytes.Length);

                            SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_LOWERFILTERS, null, 0);

                            byte[] cfgFlags = BitConverter.GetBytes((uint)0);
                            SetupDiSetDeviceRegistryPropertyW(devInfo, ref devData, SPDRP_CONFIGFLAGS, cfgFlags, 4);

                            Console.WriteLine("[+] Bound " + sbId.ToString() + " Service -> usbser (OK=" + ok + ")");
                            RunCmd("pnputil.exe", "/restart-device \"" + sbId.ToString() + "\"");
                        }
                        else if (instanceId.Contains("PID_1436") && (instanceId.Contains("&MI_01") || instanceId.Contains("&MI_04")))
                        {
                            // Disable unused legacy NDIS/Diag interfaces so Device Manager has 0 errors
                            Console.WriteLine("[*] Disabling unused interface " + sbId.ToString());
                            RunCmd("pnputil.exe", "/disable-device \"" + sbId.ToString() + "\"");
                        }
                    }
                }
            }
            finally
            {
                SetupDiDestroyDeviceInfoList(devInfo);
            }
        }

        Console.WriteLine("[+] HVCI-Compliant In-Box Driver Binding Complete!");
    }
}
