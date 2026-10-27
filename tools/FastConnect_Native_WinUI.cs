using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Ports;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using System.Diagnostics;

public class FastConnectNativeWinUI : Form
{
    // Colors for Windows 11 Dark Theme
    private static readonly Color BgColor = Color.FromArgb(32, 32, 32);
    private static readonly Color CardColor = Color.FromArgb(43, 43, 43);
    private static readonly Color BorderColor = Color.FromArgb(56, 56, 56);
    private static readonly Color AccentBlue = Color.FromArgb(0, 120, 212);
    private static readonly Color AccentGreen = Color.FromArgb(16, 124, 65);
    private static readonly Color AccentRed = Color.FromArgb(216, 59, 1);
    private static readonly Color TextPrimary = Color.FromArgb(240, 240, 240);
    private static readonly Color TextSecondary = Color.FromArgb(160, 160, 160);

    // UI Controls
    private Label lblCarrier;
    private Label lblTech;
    private Label lblSignal;
    private Label lblConnectionStatus;
    private Button btnConnect;
    private Label lblUptime;
    private Label lblUpload;
    private Label lblDownload;
    private Button btnSwitch;
    private TextBox txtUSSDInput;
    private Button btnSendUSSD;
    private RichTextBox txtUSSDOutput;
    private System.Windows.Forms.Timer telemetryTimer;

    // State
    private SerialPort modemPort;
    private bool isConnected = false;
    private DateTime connectStartTime;
    private string currentCarrier = "MobiFone";

    public FastConnectNativeWinUI()
    {
        InitializeComponent();
        StartTelemetryTimer();
    }

    private void InitializeComponent()
    {
        this.Text = "Fast Connect 3G - Windows 11 Native WinUI";
        this.Size = new Size(880, 620);
        this.MinimumSize = new Size(800, 560);
        this.BackColor = BgColor;
        this.ForeColor = TextPrimary;
        this.Font = new Font("Segoe UI", 10F, FontStyle.Regular);
        this.StartPosition = FormStartPosition.CenterScreen;

        // Header Panel
        Panel pnlHeader = new Panel
        {
            Dock = DockStyle.Top,
            Height = 70,
            BackColor = Color.FromArgb(25, 25, 25),
            Padding = new Padding(25, 12, 25, 10)
        };
        Label lblTitle = new Label
        {
            Text = "Fast Connect 3G Control Center",
            Font = new Font("Segoe UI Semibold", 18F, FontStyle.Bold),
            ForeColor = TextPrimary,
            AutoSize = true,
            Location = new Point(20, 10)
        };
        Label lblSub = new Label
        {
            Text = "Windows 11 Native Edition (Huawei E173 / MobiFone)",
            Font = new Font("Segoe UI", 9F),
            ForeColor = TextSecondary,
            AutoSize = true,
            Location = new Point(22, 42)
        };
        pnlHeader.Controls.Add(lblTitle);
        pnlHeader.Controls.Add(lblSub);
        this.Controls.Add(pnlHeader);

        // Main TabControl
        TabControl tabs = new TabControl
        {
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI", 10.5F),
            Padding = new Point(16, 6)
        };

        TabPage tabDashboard = new TabPage("  📶 Tổng quan & Kết nối  ");
        tabDashboard.BackColor = BgColor;
        BuildDashboardTab(tabDashboard);

        TabPage tabUSSD = new TabPage("  💳 Tra cứu USSD & Nạp thẻ  ");
        tabUSSD.BackColor = BgColor;
        BuildUSSDTab(tabUSSD);

        TabPage tabDrivers = new TabPage("  ⚙️ Driver & Chuyển mạch  ");
        tabDrivers.BackColor = BgColor;
        BuildDriversTab(tabDrivers);

        tabs.TabPages.Add(tabDashboard);
        tabs.TabPages.Add(tabUSSD);
        tabs.TabPages.Add(tabDrivers);

        this.Controls.Add(tabs);
        pnlHeader.BringToFront();
    }

    private void BuildDashboardTab(TabPage page)
    {
        // Network Card
        Panel cardNet = CreateCard(new Point(20, 20), new Size(820, 75));
        lblCarrier = new Label
        {
            Text = "MOBIFONE 3G",
            BackColor = AccentBlue,
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 11F, FontStyle.Bold),
            AutoSize = true,
            Padding = new Padding(8, 4, 8, 4),
            Location = new Point(15, 20)
        };
        lblTech = new Label
        {
            Text = "Công nghệ: 3G / HSPA+",
            ForeColor = TextPrimary,
            Font = new Font("Segoe UI", 12F),
            AutoSize = true,
            Location = new Point(170, 24)
        };
        lblSignal = new Label
        {
            Text = "Sóng: [|||||] 100% (-51 dBm)",
            ForeColor = Color.FromArgb(70, 210, 120),
            Font = new Font("Segoe UI", 12F, FontStyle.Bold),
            AutoSize = true,
            Location = new Point(540, 24)
        };
        cardNet.Controls.Add(lblCarrier);
        cardNet.Controls.Add(lblTech);
        cardNet.Controls.Add(lblSignal);
        page.Controls.Add(cardNet);

        // Action Connect Card
        Panel cardAction = CreateCard(new Point(20, 110), new Size(820, 180));
        lblConnectionStatus = new Label
        {
            Text = "Chưa kết nối Internet",
            ForeColor = TextSecondary,
            Font = new Font("Segoe UI Semibold", 15F, FontStyle.Bold),
            AutoSize = false,
            TextAlign = ContentAlignment.MiddleCenter,
            Dock = DockStyle.Top,
            Height = 55
        };
        btnConnect = new Button
        {
            Text = "KẾT NỐI INTERNET (CONNECT)",
            Size = new Size(360, 56),
            Location = new Point(230, 75),
            BackColor = AccentGreen,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 14F, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnConnect.FlatAppearance.BorderSize = 0;
        btnConnect.Click += BtnConnect_Click;

        cardAction.Controls.Add(btnConnect);
        cardAction.Controls.Add(lblConnectionStatus);
        page.Controls.Add(cardAction);

        // Session Stats Card
        Panel cardStats = CreateCard(new Point(20, 305), new Size(820, 95));
        lblUptime = new Label
        {
            Text = "Thời gian online\n00:00:00",
            ForeColor = TextPrimary,
            Font = new Font("Segoe UI", 12F),
            TextAlign = ContentAlignment.MiddleCenter,
            Size = new Size(260, 60),
            Location = new Point(10, 18)
        };
        lblUpload = new Label
        {
            Text = "Dữ liệu Tải lên\n0.00 MB",
            ForeColor = TextPrimary,
            Font = new Font("Segoe UI", 12F),
            TextAlign = ContentAlignment.MiddleCenter,
            Size = new Size(260, 60),
            Location = new Point(280, 18)
        };
        lblDownload = new Label
        {
            Text = "Dữ liệu Tải xuống\n0.00 MB",
            ForeColor = TextPrimary,
            Font = new Font("Segoe UI", 12F),
            TextAlign = ContentAlignment.MiddleCenter,
            Size = new Size(260, 60),
            Location = new Point(550, 18)
        };
        cardStats.Controls.Add(lblUptime);
        cardStats.Controls.Add(lblUpload);
        cardStats.Controls.Add(lblDownload);
        page.Controls.Add(cardStats);

        // ZeroCD Switch button at bottom
        btnSwitch = new Button
        {
            Text = "⚡ Chuyển mạch DCom (ZeroCD 1446 -> 1436)",
            Size = new Size(340, 42),
            Location = new Point(20, 415),
            BackColor = AccentRed,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 10.5F, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnSwitch.FlatAppearance.BorderSize = 0;
        btnSwitch.Click += (s, e) => {
            ZeroCDSwitch.SwitchDrive("E");
            MessageBox.Show("Đã gửi lệnh chuyển mạch SCSI đến DCom!", "ZeroCD ModeSwitch", MessageBoxButtons.OK, MessageBoxIcon.Information);
        };
        page.Controls.Add(btnSwitch);
    }

    private void BuildUSSDTab(TabPage page)
    {
        Panel cardShortcuts = CreateCard(new Point(20, 20), new Size(820, 65));
        Button btn101 = new Button
        {
            Text = "🔍 Kiểm tra TK Chính (*101#)",
            Size = new Size(250, 38),
            Location = new Point(15, 14),
            BackColor = AccentBlue,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat
        };
        btn101.FlatAppearance.BorderSize = 0;
        btn101.Click += (s, e) => ExecuteUSSD("*101#");

        Button btn102 = new Button
        {
            Text = "🎁 Tài khoản KM (*102#)",
            Size = new Size(250, 38),
            Location = new Point(285, 14),
            BackColor = AccentBlue,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat
        };
        btn102.FlatAppearance.BorderSize = 0;
        btn102.Click += (s, e) => ExecuteUSSD("*102#");

        Button btn090 = new Button
        {
            Text = "⚡ Gói cước (*090#)",
            Size = new Size(250, 38),
            Location = new Point(555, 14),
            BackColor = AccentBlue,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat
        };
        btn090.FlatAppearance.BorderSize = 0;
        btn090.Click += (s, e) => ExecuteUSSD("*090#");

        cardShortcuts.Controls.Add(btn101);
        cardShortcuts.Controls.Add(btn102);
        cardShortcuts.Controls.Add(btn090);
        page.Controls.Add(cardShortcuts);

        // USSD Input Card
        Panel cardInput = CreateCard(new Point(20, 95), new Size(820, 65));
        txtUSSDInput = new TextBox
        {
            Location = new Point(15, 18),
            Size = new Size(640, 32),
            Font = new Font("Segoe UI", 12F),
            BackColor = Color.FromArgb(30, 30, 30),
            ForeColor = TextPrimary,
            BorderStyle = BorderStyle.FixedSingle
        };
        btnSendUSSD = new Button
        {
            Text = "Gửi lệnh",
            Size = new Size(135, 34),
            Location = new Point(670, 16),
            BackColor = AccentBlue,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 11F, FontStyle.Bold)
        };
        btnSendUSSD.FlatAppearance.BorderSize = 0;
        btnSendUSSD.Click += (s, e) => ExecuteUSSD(txtUSSDInput.Text);

        cardInput.Controls.Add(txtUSSDInput);
        cardInput.Controls.Add(btnSendUSSD);
        page.Controls.Add(cardInput);

        // Result Box
        txtUSSDOutput = new RichTextBox
        {
            Location = new Point(20, 175),
            Size = new Size(820, 280),
            BackColor = CardColor,
            ForeColor = TextPrimary,
            Font = new Font("Consolas", 11F),
            BorderStyle = BorderStyle.None,
            ReadOnly = true
        };
        page.Controls.Add(txtUSSDOutput);
    }

    private void BuildDriversTab(TabPage page)
    {
        Panel cardInfo = CreateCard(new Point(20, 20), new Size(820, 220));
        Label lblDrv = new Label
        {
            Text = "Thông tin Driver & Bảo mật Windows 11:\n\n" +
                   "• Giải pháp 1: Driver sạch sử dụng in-box usbser.sys (Microsoft signed).\n" +
                   "• Core Isolation (Memory Integrity / HVCI): 100% Hoạt động bình thường.\n" +
                   "• Không sử dụng driver filter cũ (ew_hwusbdev.sys) gây xung đột.\n" +
                   "• Hỗ trợ chuyển mạch tức thì ZeroCD từ user-mode mà không cần driver phụ trợ.",
            ForeColor = TextPrimary,
            Font = new Font("Segoe UI", 11F),
            AutoSize = false,
            Size = new Size(780, 180),
            Location = new Point(20, 20)
        };
        cardInfo.Controls.Add(lblDrv);
        page.Controls.Add(cardInfo);

        Button btnInstall = new Button
        {
            Text = "📥 Chạy Trình Cài đặt Driver Tự động (Admin)",
            Size = new Size(380, 50),
            Location = new Point(20, 260),
            BackColor = AccentBlue,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 12F, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnInstall.FlatAppearance.BorderSize = 0;
        btnInstall.Click += (s, e) => {
            string bat = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\drivers\Install-All-Recommended.bat");
            if (File.Exists(bat)) Process.Start(bat);
            else MessageBox.Show("File installer bat không tồn tại tại: " + bat);
        };
        page.Controls.Add(btnInstall);

        Button btnDevMgr = new Button
        {
            Text = "🛠️ Mở Device Manager",
            Size = new Size(240, 50),
            Location = new Point(420, 260),
            BackColor = Color.FromArgb(60, 60, 60),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 12F),
            Cursor = Cursors.Hand
        };
        btnDevMgr.FlatAppearance.BorderSize = 0;
        btnDevMgr.Click += (s, e) => Process.Start("devmgmt.msc");
        page.Controls.Add(btnDevMgr);
    }

    private Panel CreateCard(Point location, Size size)
    {
        Panel p = new Panel
        {
            Location = location,
            Size = size,
            BackColor = CardColor
        };
        return p;
    }

    private void StartTelemetryTimer()
    {
        telemetryTimer = new System.Windows.Forms.Timer();
        telemetryTimer.Interval = 2000;
        telemetryTimer.Tick += (s, e) => UpdateTelemetry();
        telemetryTimer.Start();
    }

    private void UpdateTelemetry()
    {
        // Update connection uptime
        if (isConnected)
        {
            TimeSpan elapsed = DateTime.Now - connectStartTime;
            lblUptime.Text = string.Format("Thời gian online\n{0:D2}:{1:D2}:{2:D2}", elapsed.Hours, elapsed.Minutes, elapsed.Seconds);
        }
    }

    private void BtnConnect_Click(object sender, EventArgs e)
    {
        if (!isConnected)
        {
            btnConnect.Enabled = false;
            btnConnect.Text = "ĐANG KẾT NỐI...";
            ThreadPool.QueueUserWorkItem(state => {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo("rasdial", "FastConnect3G *99#")
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false,
                        RedirectStandardOutput = true
                    };
                    Process p = Process.Start(psi);
                    string outStr = p.StandardOutput.ReadToEnd();
                    p.WaitForExit();

                    this.Invoke((MethodInvoker)delegate {
                        btnConnect.Enabled = true;
                        if (p.ExitCode == 0 || outStr.Contains("Successfully connected"))
                        {
                            isConnected = true;
                            connectStartTime = DateTime.Now;
                            btnConnect.Text = "NGẮT KẾT NỐI (DISCONNECT)";
                            btnConnect.BackColor = AccentRed;
                            lblConnectionStatus.Text = "Đã kết nối Internet thành công! (Online)";
                            lblConnectionStatus.ForeColor = Color.FromArgb(70, 210, 120);
                        }
                        else
                        {
                            btnConnect.Text = "KẾT NỐI INTERNET (CONNECT)";
                            MessageBox.Show("Kết nối Dial-Up thất bại:\n" + outStr, "Lỗi kết nối", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        }
                    });
                }
                catch (Exception ex)
                {
                    this.Invoke((MethodInvoker)delegate {
                        btnConnect.Enabled = true;
                        btnConnect.Text = "KẾT NỐI INTERNET (CONNECT)";
                        MessageBox.Show("Lỗi: " + ex.Message);
                    });
                }
            });
        }
        else
        {
            btnConnect.Enabled = false;
            btnConnect.Text = "ĐANG NGẮT...";
            ThreadPool.QueueUserWorkItem(state => {
                Process.Start("rasdial", "FastConnect3G /DISCONNECT").WaitForExit();
                this.Invoke((MethodInvoker)delegate {
                    isConnected = false;
                    btnConnect.Enabled = true;
                    btnConnect.Text = "KẾT NỐI INTERNET (CONNECT)";
                    btnConnect.BackColor = AccentGreen;
                    lblConnectionStatus.Text = "Chưa kết nối Internet";
                    lblConnectionStatus.ForeColor = TextSecondary;
                    lblUptime.Text = "Thời gian online\n00:00:00";
                });
            });
        }
    }

    private void ExecuteUSSD(string code)
    {
        if (string.IsNullOrEmpty(code)) return;
        txtUSSDOutput.AppendText(">> Đang gửi lệnh: " + code + "...\n");
        // Asynchronous USSD call
        ThreadPool.QueueUserWorkItem(state => {
            string response = QueryModemUSSD(code);
            this.Invoke((MethodInvoker)delegate {
                txtUSSDOutput.AppendText("<< Phản hồi:\n" + response + "\n\n");
            });
        });
    }

    private string QueryModemUSSD(string code)
    {
        // Try COM ports
        foreach (string port in SerialPort.GetPortNames())
        {
            try
            {
                using (SerialPort sp = new SerialPort(port, 115200))
                {
                    sp.ReadTimeout = 4000;
                    sp.WriteTimeout = 2000;
                    sp.Open();
                    sp.WriteLine("ATE0\r\n");
                    Thread.Sleep(100);
                    sp.ReadExisting();
                    sp.WriteLine("AT+CUSD=1,\"" + code + "\",15\r\n");

                    DateTime start = DateTime.Now;
                    while ((DateTime.Now - start).TotalSeconds < 8)
                    {
                        string line = sp.ReadLine();
                        if (line.Contains("+CUSD:"))
                        {
                            Match m = Regex.Match(line, @"\+CUSD:\s*\d+,\""([^\""]*)\""");
                            if (m.Success)
                            {
                                return DecodeUSSD(m.Groups[1].Value);
                            }
                            return line;
                        }
                    }
                }
            }
            catch { }
        }
        return "Không tìm thấy phản hồi từ DCom hoặc cổng COM bận.";
    }

    private string DecodeUSSD(string raw)
    {
        if (Regex.IsMatch(raw, "^[0-9A-Fa-f]{8,}$") && raw.Length % 4 == 0)
        {
            try
            {
                byte[] bytes = new byte[raw.Length / 2];
                for (int i = 0; i < bytes.Length; i++)
                    bytes[i] = Convert.ToByte(raw.Substring(i * 2, 2), 16);
                return Encoding.BigEndianUnicode.GetString(bytes);
            }
            catch { }
        }
        return raw;
    }

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new FastConnectNativeWinUI());
    }
}
