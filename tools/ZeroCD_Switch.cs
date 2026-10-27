using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

public class ZeroCDSwitch
{
    private const uint GENERIC_READ = 0x80000000;
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint FILE_SHARE_READ = 1;
    private const uint FILE_SHARE_WRITE = 2;
    private const uint OPEN_EXISTING = 3;
    private const uint IOCTL_SCSI_PASS_THROUGH = 0x04D004;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential)]
    private struct SCSI_PASS_THROUGH
    {
        public ushort Length;
        public byte ScsiStatus;
        public byte PathId;
        public byte TargetId;
        public byte Lun;
        public byte CdbLength;
        public byte SenseInfoLength;
        public byte DataIn;
        public uint DataTransferLength;
        public uint TimeOutValue;
        public IntPtr DataBufferOffset;
        public uint SenseInfoOffset;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 16)]
        public byte[] Cdb;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    private static extern IntPtr CreateFile(
        string lpFileName,
        uint dwDesiredAccess,
        uint dwShareMode,
        IntPtr lpSecurityAttributes,
        uint dwCreationDisposition,
        uint dwFlagsAndAttributes,
        IntPtr hTemplateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool DeviceIoControl(
        IntPtr hDevice,
        uint dwIoControlCode,
        IntPtr lpInBuffer,
        uint nInBufferSize,
        IntPtr lpOutBuffer,
        uint nOutBufferSize,
        out uint lpBytesReturned,
        IntPtr lpOverlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    public static bool SwitchDrive(string driveLetter)
    {
        string devicePath = @"\\.\" + driveLetter.TrimEnd('\\', ':') + ":";
        IntPtr handle = CreateFile(
            devicePath,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            IntPtr.Zero,
            OPEN_EXISTING,
            0,
            IntPtr.Zero);

        if (handle == INVALID_HANDLE_VALUE)
        {
            Console.WriteLine("[!] Could not open handle to " + devicePath + " (Error: " + Marshal.GetLastWin32Error() + ")");
            return false;
        }

        try
        {
            // Huawei ZeroCD switch command: 11 06 20 00 00 01 00 00 00 00 00 00 00 00 00 00
            byte[] cdb = new byte[16] { 0x11, 0x06, 0x20, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
            
            SCSI_PASS_THROUGH spt = new SCSI_PASS_THROUGH();
            spt.Length = (ushort)Marshal.SizeOf(typeof(SCSI_PASS_THROUGH));
            spt.CdbLength = 16;
            spt.SenseInfoLength = 32;
            spt.DataIn = 2; // SCSI_IOCTL_DATA_UNSPECIFIED
            spt.DataTransferLength = 0;
            spt.TimeOutValue = 5;
            spt.SenseInfoOffset = spt.Length;
            spt.Cdb = cdb;

            int totalSize = spt.Length + 32;
            IntPtr buffer = Marshal.AllocHGlobal(totalSize);
            try
            {
                for (int i = 0; i < totalSize; i++) Marshal.WriteByte(buffer, i, 0);
                Marshal.StructureToPtr(spt, buffer, false);

                uint bytesReturned;
                bool success = DeviceIoControl(
                    handle,
                    IOCTL_SCSI_PASS_THROUGH,
                    buffer,
                    (uint)totalSize,
                    buffer,
                    (uint)totalSize,
                    out bytesReturned,
                    IntPtr.Zero);

                int err = Marshal.GetLastWin32Error();
                // Error 121 (ERROR_SEM_TIMEOUT) is normal because device disconnects immediately upon switching!
                if (success || err == 121 || err == 0)
                {
                    Console.WriteLine("[+] Switch command sent successfully to " + devicePath);
                    return true;
                }
                else
                {
                    Console.WriteLine("[-] DeviceIoControl returned: " + success + ", Win32Error: " + err);
                    return false;
                }
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        finally
        {
            CloseHandle(handle);
        }
    }

    public static void Main(string[] args)
    {
        Console.WriteLine("=== FastConnect ZeroCD ModeSwitcher for Huawei 3G (Win11) ===");
        if (args.Length > 0)
        {
            SwitchDrive(args[0]);
            return;
        }

        bool found = false;
        foreach (DriveInfo drive in DriveInfo.GetDrives())
        {
            if (drive.DriveType == DriveType.CDRom || drive.DriveType == DriveType.Removable)
            {
                Console.WriteLine("[*] Probing drive " + drive.Name + "...");
                if (SwitchDrive(drive.Name))
                {
                    found = true;
                }
            }
        }

        if (!found)
        {
            Console.WriteLine("[*] Probing default drive E:...");
            SwitchDrive("E");
        }
    }
}
