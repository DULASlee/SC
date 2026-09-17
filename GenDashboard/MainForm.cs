using System;
using System.Collections.Generic;
using System.Data;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;
using HslCommunication.MQTT;
using Newtonsoft.Json.Linq;

namespace GenDashboard
{
    public partial class MainForm : Form
    {
        private TextBox txtHost, txtPort, txtTopic, txtStatus;
        private Button btnConnect, btnDisconnect, btnLoad, btnClear;
        private DataGridView dgv;
        private MqttClient _client;
        private readonly DataTable _dt = new DataTable();
        private readonly Timer _timer;
        private readonly object _lock = new object();
        private readonly Dictionary<string, string> _addrMap = LoadAddrMap();
        private readonly DashboardModel _model;

        public MainForm()
        {
            _model = new DashboardModel(_addrMap);
            Text = "GenCollector 看板";
            Width = 1024; Height = 640;
            Font = new Font("Microsoft YaHei", 9);

            // 连接面板
            var panel = new Panel { Dock = DockStyle.Top, Height = 64, BackColor = Color.FromArgb(245, 247, 250) };
            txtHost = new TextBox { Text = "127.0.0.1", Left = 12, Top = 14, Width = 120 };
            txtPort = new TextBox { Text = "1883", Left = 140, Top = 14, Width = 56 };
            txtTopic = new TextBox { Text = "/YLCY/CNC/#", Left = 204, Top = 14, Width = 220 };
            btnConnect = new Button { Text = "连接MQTT", Left = 436, Top = 12, Width = 96, Height = 24 };
            btnDisconnect = new Button { Text = "断开", Left = 540, Top = 12, Width = 72, Height = 24 };
            btnLoad = new Button { Text = "加载样本JSONL", Left = 620, Top = 12, Width = 110, Height = 24 };
            btnClear = new Button { Text = "清空", Left = 740, Top = 12, Width = 72, Height = 24 };
            txtStatus = new TextBox { Left = 12, Top = 40, Width = 980, Height = 20, ReadOnly = true, BorderStyle = BorderStyle.None, BackColor = panel.BackColor };
            panel.Controls.AddRange(new Control[] { MakeLabel("Broker", 12, -2), txtHost, MakeLabel("端口", 140, -2), txtPort,
                MakeLabel("主题", 204, -2), txtTopic, btnConnect, btnDisconnect, btnLoad, btnClear, txtStatus });
            Controls.Add(panel);

            dgv = new DataGridView
            {
                Dock = DockStyle.Fill,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                ReadOnly = true,
                RowHeadersVisible = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                BackgroundColor = Color.White,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect
            };
            _dt.Columns.Add("Device");
            _dt.Columns.Add("VarCode");
            _dt.Columns.Add("VarName");
            _dt.Columns.Add("AddrCode");
            _dt.Columns.Add("Value");
            _dt.Columns.Add("Time");
            dgv.DataSource = _dt;
            if (dgv.Columns["Device"] != null) dgv.Columns["Device"].HeaderText = "设备";
            if (dgv.Columns["VarCode"] != null) dgv.Columns["VarCode"].HeaderText = "变量编码";
            if (dgv.Columns["VarName"] != null) dgv.Columns["VarName"].HeaderText = "语义名";
            if (dgv.Columns["AddrCode"] != null) dgv.Columns["AddrCode"].HeaderText = "地址码(addrCode)";
            if (dgv.Columns["Value"] != null) dgv.Columns["Value"].HeaderText = "数值";
            if (dgv.Columns["Time"] != null) dgv.Columns["Time"].HeaderText = "时间";
            if (dgv.Columns["VarName"] != null) dgv.Columns["VarName"].FillWeight = 160;
            if (dgv.Columns["AddrCode"] != null) dgv.Columns["AddrCode"].FillWeight = 130;
            if (dgv.Columns["VarCode"] != null) dgv.Columns["VarCode"].FillWeight = 110;
            if (dgv.Columns["Device"] != null) dgv.Columns["Device"].FillWeight = 90;
            if (dgv.Columns["Value"] != null) dgv.Columns["Value"].FillWeight = 90;
            if (dgv.Columns["Time"] != null) dgv.Columns["Time"].FillWeight = 130;
            Controls.Add(dgv);

            btnConnect.Click += BtnConnect_Click;
            btnDisconnect.Click += (s, e) => Disconnect();
            btnLoad.Click += BtnLoad_Click;
            btnClear.Click += (s, e) => { lock (_lock) _dt.Rows.Clear(); };

            _timer = new Timer { Interval = 600 };
            _timer.Tick += (s, e) => RefreshGrid();
            _timer.Start();
        }

        private static Label MakeLabel(string t, int x, int y)
            => new Label { Text = t, Left = x, Top = y, Width = 44, TextAlign = ContentAlignment.BottomLeft };

        // 从内嵌资源 addrMap.csv 读取 语义变量→addrCode 对照（同一变量多品牌时合并显示）
        private static Dictionary<string, string> LoadAddrMap()
        {
            var map = new Dictionary<string, string>();
            try
            {
                var asm = typeof(MainForm).Assembly;
                using var s = asm.GetManifestResourceStream("GenDashboard.addrMap.csv");
                if (s == null) return map;
                using var r = new StreamReader(s);
                r.ReadLine(); // 跳过表头 brand,semanticVar,addrCode
                string line;
                while ((line = r.ReadLine()) != null)
                {
                    if (string.IsNullOrWhiteSpace(line)) continue;
                    var parts = line.Split(',');
                    if (parts.Length < 3) continue;
                    string sv = parts[1].Trim(), ac = parts[2].Trim(), brand = parts[0].Trim();
                    if (!map.TryGetValue(sv, out var cur)) map[sv] = brand + ":" + ac;
                    else if (!cur.Contains(ac)) map[sv] = cur + " / " + brand + ":" + ac;
                }
            }
            catch { /* 资源缺失时忽略，地址码列留空 */ }
            return map;
        }

        private void SetStatus(string s) => txtStatus.Text = s;

        private void BtnConnect_Click(object sender, EventArgs e)
        {
            try
            {
                var opt = new MqttConnectionOptions
                {
                    CleanSession = true,
                    IpAddress = txtHost.Text.Trim(),
                    Port = int.Parse(txtPort.Text.Trim()),
                    ClientId = "dash_" + Guid.NewGuid().ToString("N").Substring(0, 8),
                    Credentials = new MqttCredential("", "")
                };
                var topic = txtTopic.Text.Trim();
                _client = new MqttClient(opt);
                _client.OnMqttMessageReceived += (s, ev) =>
                {
                    string t = ev.Topic;
                    string pl = Encoding.UTF8.GetString(ev.Payload ?? new byte[0]);
                    BeginInvoke(new Action(() => Ingest(t, pl)));
                };
                var r = _client.ConnectServer();
                if (r.IsSuccess)
                {
                    _client.SubscribeMessage(topic);
                    SetStatus($"已连接 {opt.IpAddress}:{opt.Port}  订阅 {topic}");
                }
                else SetStatus("连接失败: " + r.ToMessageShowString());
            }
            catch (Exception ex) { SetStatus("错误: " + ex.Message); }
        }

        private void Disconnect()
        {
            try { _client?.ConnectClose(); } catch { }
            _client = null;
            SetStatus("已断开");
        }

        private void BtnLoad_Click(object sender, EventArgs e)
        {
            using var ofd = new OpenFileDialog { Filter = "JSONL 文件 (*.jsonl;*.txt)|*.jsonl;*.txt|所有文件|*.*" };
            if (ofd.ShowDialog() == DialogResult.OK)
                LoadFile(ofd.FileName);
        }

        public void LoadFile(string path)
        {
            try
            {
                int n = 0;
                foreach (var line in File.ReadAllLines(path))
                {
                    if (string.IsNullOrWhiteSpace(line)) continue;
                    int tab = line.IndexOf('\t');
                    string topic = tab >= 0 ? line.Substring(0, tab) : "";
                    string json = tab >= 0 ? line.Substring(tab + 1) : line;
                    Ingest(topic, json);
                    n++;
                }
                SetStatus($"已加载 {n} 条样本 ({Path.GetFileName(path)})");
            }
            catch (Exception ex) { SetStatus("加载失败: " + ex.Message); }
        }

        // topic 形如 /YLCY/CNC/CNC-01/realtime
        private void Ingest(string topic, string json)
        {
            try
            {
                lock (_lock)
                {
                    _model.Ingest(_dt, topic, json);
                }
            }
            catch { /* 单行解析失败忽略 */ }
        }

        private void RefreshGrid()
        {
            // 数据已在 Ingest 中写入 _dt，这里仅触发界面刷新（DataTable 绑定自动更新）
        }
    }
}
