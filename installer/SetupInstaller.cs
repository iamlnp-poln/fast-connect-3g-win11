using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

public class SetupInstaller : Form
{
    private ProgressBar progressBar;
    private Label lblStatus;
    private Label lblTitle;
    private Label lblSub;
    private Button btnInstall;
    private Button btnCancel;
    private CheckBox chkDesktop;
    private CheckBox chkStartMenu;
    private CheckBox chkLaunch;
    private string installDir;

    public SetupInstaller()
    {
        this.Text = "Cài Đặt Fast Connect 3G — Windows 11 Edition";
        this.Size = new Size(520, 360);
        this.StartPosition = FormStartPosition.CenterScreen;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.BackColor = Color.FromArgb(32, 32, 32);
        this.ForeColor = Color.White;
        this.Font = new Font("Segoe UI", 9.5f);

        installDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs", "FastConnect3G"
        );

        // Header Title
        lblTitle = new Label();
        lblTitle.Text = "Fast Connect 3G Control Center";
        lblTitle.Font = new Font("Segoe UI", 14f, FontStyle.Bold);
        lblTitle.ForeColor = Color.FromArgb(76, 194, 255);
        lblTitle.Location = new Point(24, 20);
        lblTitle.AutoSize = true;
        this.Controls.Add(lblTitle);

        lblSub = new Label();
        lblSub.Text = "Bộ cài đặt Standalone hoàn chỉnh cho DCom Huawei E173 trên Windows 11";
        lblSub.ForeColor = Color.FromArgb(180, 180, 180);
        lblSub.Location = new Point(24, 52);
        lblSub.Size = new Size(460, 40);
        this.Controls.Add(lblSub);

        // Options
        chkDesktop = new CheckBox();
        chkDesktop.Text = "Tạo biểu tượng lối tắt ngoài Màn hình chính (Desktop Shortcut)";
        chkDesktop.Checked = true;
        chkDesktop.Location = new Point(28, 100);
        chkDesktop.AutoSize = true;
        this.Controls.Add(chkDesktop);

        chkStartMenu = new CheckBox();
        chkStartMenu.Text = "Tạo lối tắt trong Start Menu (Windows Search)";
        chkStartMenu.Checked = true;
        chkStartMenu.Location = new Point(28, 130);
        chkStartMenu.AutoSize = true;
        this.Controls.Add(chkStartMenu);

        chkLaunch = new CheckBox();
        chkLaunch.Text = "Khởi chạy Fast Connect 3G ngay sau khi cài đặt xong";
        chkLaunch.Checked = true;
        chkLaunch.Location = new Point(28, 160);
        chkLaunch.AutoSize = true;
        this.Controls.Add(chkLaunch);

        // Progress & Status
        progressBar = new ProgressBar();
        progressBar.Location = new Point(28, 200);
        progressBar.Size = new Size(450, 18);
        progressBar.Visible = false;
        this.Controls.Add(progressBar);

        lblStatus = new Label();
        lblStatus.Text = "Sẵn sàng cài đặt vào: " + installDir;
        lblStatus.ForeColor = Color.FromArgb(160, 160, 160);
        lblStatus.Location = new Point(28, 226);
        lblStatus.Size = new Size(450, 40);
        this.Controls.Add(lblStatus);

        // Buttons
        btnInstall = new Button();
        btnInstall.Text = "Cài Đặt Ngay";
        btnInstall.Size = new Size(130, 38);
        btnInstall.Location = new Point(220, 268);
        btnInstall.BackColor = Color.FromArgb(0, 120, 212);
        btnInstall.ForeColor = Color.White;
        btnInstall.FlatStyle = FlatStyle.Flat;
        btnInstall.FlatAppearance.BorderSize = 0;
        btnInstall.Cursor = Cursors.Hand;
        btnInstall.Click += BtnInstall_Click;
        this.Controls.Add(btnInstall);

        btnCancel = new Button();
        btnCancel.Text = "Hủy Bỏ";
        btnCancel.Size = new Size(110, 38);
        btnCancel.Location = new Point(368, 268);
        btnCancel.BackColor = Color.FromArgb(50, 50, 50);
        btnCancel.ForeColor = Color.White;
        btnCancel.FlatStyle = FlatStyle.Flat;
        btnCancel.FlatAppearance.BorderSize = 0;
        btnCancel.Cursor = Cursors.Hand;
        btnCancel.Click += (s, e) => this.Close();
        this.Controls.Add(btnCancel);
    }

    private void BtnInstall_Click(object sender, EventArgs e)
    {
        btnInstall.Enabled = false;
        btnCancel.Enabled = false;
        chkDesktop.Enabled = false;
        chkStartMenu.Enabled = false;
        chkLaunch.Enabled = false;
        progressBar.Visible = true;
        progressBar.Style = ProgressBarStyle.Marquee;

        Thread t = new Thread(DoInstallation);
        t.IsBackground = true;
        t.Start();
    }

    private void DoInstallation()
    {
        try
        {
            UpdateStatus("Đang giải nén tập tin ứng dụng...");

            // 1. Prepare Target Directory
            if (!Directory.Exists(installDir))
            {
                Directory.CreateDirectory(installDir);
            }

            // 2. Extract Embedded Archive
            Assembly asm = Assembly.GetExecutingAssembly();
            string resourceName = null;
            foreach (string name in asm.GetManifestResourceNames())
            {
                if (name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
                {
                    resourceName = name;
                    break;
                }
            }

            if (resourceName != null)
            {
                using (Stream stream = asm.GetManifestResourceStream(resourceName))
                using (ZipArchive archive = new ZipArchive(stream))
                {
                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        string destPath = Path.Combine(installDir, entry.FullName);
                        if (string.IsNullOrEmpty(entry.Name))
                        {
                            Directory.CreateDirectory(destPath);
                        }
                        else
                        {
                            string parent = Path.GetDirectoryName(destPath);
                            if (!Directory.Exists(parent))
                            {
                                Directory.CreateDirectory(parent);
                            }
                            entry.ExtractToFile(destPath, true);
                        }
                    }
                }
            }
            else
            {
                // Fallback: copy from adjacent folder if testing unpack
                string adjacent = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "FastConnect3G");
                if (Directory.Exists(adjacent))
                {
                    CopyDirectory(adjacent, installDir);
                }
            }

            UpdateStatus("Đang tạo lối tắt trên Windows...");

            string exePath = Path.Combine(installDir, "FastConnect3G.exe");
            string icoPath = Path.Combine(installDir, "assets", "icon.ico");

            // 3. Create Shortcuts via WScript.Shell
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType != null)
            {
                dynamic shell = Activator.CreateInstance(shellType);

                if (chkDesktop.Checked)
                {
                    string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    string lnkDesktop = Path.Combine(desktop, "Fast Connect 3G.lnk");
                    dynamic s1 = shell.CreateShortcut(lnkDesktop);
                    s1.TargetPath = exePath;
                    s1.WorkingDirectory = installDir;
                    if (File.Exists(icoPath)) s1.IconLocation = icoPath;
                    s1.Description = "Fast Connect 3G - Windows 11 Control Center";
                    s1.Save();
                }

                if (chkStartMenu.Checked)
                {
                    string startMenu = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),
                        "Programs"
                    );
                    string lnkStart = Path.Combine(startMenu, "Fast Connect 3G.lnk");
                    dynamic s2 = shell.CreateShortcut(lnkStart);
                    s2.TargetPath = exePath;
                    s2.WorkingDirectory = installDir;
                    if (File.Exists(icoPath)) s2.IconLocation = icoPath;
                    s2.Description = "Fast Connect 3G - Windows 11 Control Center";
                    s2.Save();
                }
            }

            // 4. Create Uninstaller Script
            string uninstBat = Path.Combine(installDir, "Uninstall.bat");
            File.WriteAllText(uninstBat, 
                "@echo off\r\n" +
                "title Uninstalling Fast Connect 3G...\r\n" +
                "taskkill /f /im FastConnect3G.exe >nul 2>&1\r\n" +
                "del /q \"%userprofile%\\Desktop\\Fast Connect 3G.lnk\" >nul 2>&1\r\n" +
                "del /q \"%appdata%\\Microsoft\\Windows\\Start Menu\\Programs\\Fast Connect 3G.lnk\" >nul 2>&1\r\n" +
                "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FastConnect3G\" /f >nul 2>&1\r\n" +
                "cd ..\r\n" +
                "rmdir /s /q \"%~dp0\"\r\n" +
                "echo Fast Connect 3G uninstalled successfully.\r\n" +
                "timeout /t 2 >nul\r\n"
            );

            // 5. Register in Windows Programs & Features
            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\FastConnect3G"))
                {
                    if (key != null)
                    {
                        key.SetValue("DisplayName", "Fast Connect 3G Control Center");
                        key.SetValue("DisplayIcon", icoPath);
                        key.SetValue("DisplayVersion", "2.0.0");
                        key.SetValue("Publisher", "Reverse Engineer Anything");
                        key.SetValue("InstallLocation", installDir);
                        key.SetValue("UninstallString", uninstBat);
                    }
                }
            }
            catch { }

            UpdateStatus("Cài đặt thành công!");

            this.Invoke((MethodInvoker)delegate
            {
                progressBar.Visible = false;
                MessageBox.Show(
                    "Chúc mừng! Fast Connect 3G đã được cài đặt thành công vào máy tính.",
                    "Cài Đặt Thành Công",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information
                );

                if (chkLaunch.Checked && File.Exists(exePath))
                {
                    Process.Start(new ProcessStartInfo(exePath)
                    {
                        WorkingDirectory = installDir
                    });
                }

                this.Close();
            });
        }
        catch (Exception ex)
        {
            this.Invoke((MethodInvoker)delegate
            {
                progressBar.Visible = false;
                btnInstall.Enabled = true;
                btnCancel.Enabled = true;
                MessageBox.Show(
                    "Lỗi trong quá trình cài đặt: " + ex.Message,
                    "Lỗi Cài Đặt",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            });
        }
    }

    private void UpdateStatus(string txt)
    {
        if (this.InvokeRequired)
        {
            this.Invoke((MethodInvoker)delegate { lblStatus.Text = txt; });
        }
        else
        {
            lblStatus.Text = txt;
        }
    }

    private static void CopyDirectory(string sourceDir, string targetDir)
    {
        foreach (string dir in Directory.GetDirectories(sourceDir, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(dir.Replace(sourceDir, targetDir));
        }
        foreach (string file in Directory.GetFiles(sourceDir, "*.*", SearchOption.AllDirectories))
        {
            File.Copy(file, file.Replace(sourceDir, targetDir), true);
        }
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new SetupInstaller());
    }
}
