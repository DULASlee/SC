using System;
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
using System.IO;
using System.Threading;
using Newtonsoft.Json;
using GenCollector.Drivers;

namespace GenCollector.Core
{
    // 采集引擎：配置驱动 + 协议可插拔 + 统一 MQTT 上送
    public class CollectorEngine
    {
        public Action<DeviceConfig, string, string> OnPublish;  // (设备, topic, json) 供 UI 订阅
        public Action<string> OnLog;

        private readonly SettingConfig _setting;
        private readonly List<DeviceConfig> _devices;
        private readonly Dictionary<string, List<VarInfo>> _varInfos;
        private readonly List<VarGroup> _groups;
        private readonly Dictionary<string, ProtocolConfig> _protocols;
        private readonly bool _simulate;
        public bool NoMqtt { get; set; }
        public string TelemetryLogFile { get; set; }
        private MqttPublisher _mqtt;
        private readonly List<CancellationTokenSource> _cts = new List<CancellationTokenSource>();

        public CollectorEngine(SettingConfig s, List<DeviceConfig> devs,
            Dictionary<string, List<VarInfo>> vars, List<VarGroup> groups,
            Dictionary<string, ProtocolConfig> prots, bool simulate)
        {
            _setting = s; _devices = devs; _varInfos = vars;
            _groups = groups; _protocols = prots; _simulate = simulate;
        }

        public void Start()
        {
            if (!NoMqtt)
            {
                _mqtt = new MqttPublisher();
                _mqtt.Init(_setting);
                _mqtt.Connect();
            }
            foreach (var dev in _devices)
            {
                if (!dev.Enabled) { Log($"跳过未启用设备 {dev.Id}"); continue; }
                var cts = new CancellationTokenSource();
                _cts.Add(cts);
                var d = dev;
                var t = new Thread(() => RunDevice(d, cts.Token)) { IsBackground = true };
                t.Start();
            }
            Log($"采集引擎已启动：{_devices.Count} 台设备，模拟模式={_simulate}");
        }

        public void Stop() { foreach (var c in _cts) try { c.Cancel(); } catch { } }

        [SuppressMessage("Usage", "RS0030:Do not use banned Thread.Sleep", Justification = "ADR-001: Hardware polling thread requires synchronous sleep; see docs/adr/ADR-001-Collector-Thread-Sleep-Exemption.md")]
        void RunDevice(DeviceConfig dev, CancellationToken token)
        {
            var driver = DriverFactory.Create(dev.Protocol, _simulate);
            bool ok = driver.Connect(dev, _setting);
            Log($"设备 {dev.Id}({dev.Protocol}) 驱动[{driver.DriverName}] 连接={(ok ? "成功" : "失败")}");

            var lastPub = new Dictionary<string, DateTimeOffset>();
            while (!token.IsCancellationRequested)
            {
                try
                {
                    if (_mqtt != null && !_mqtt.IsConnected) _mqtt.Connect();

                    _varInfos.TryGetValue(dev.ProtocolFamily, out var allVars);
                    foreach (var g in _groups)
                    {
                        int interval = g.Timer > 0 ? g.Timer * 1000 : 20000;
                        if (!lastPub.ContainsKey(g.Id)) lastPub[g.Id] = DateTimeOffset.MinValue;
                        if ((DateTimeOffset.UtcNow - lastPub[g.Id]).TotalMilliseconds < interval) continue;

                        var vars = allVars?.FindAll(x => x.Enabled && x.Group == g.Id);
                        lastPub[g.Id] = DateTimeOffset.UtcNow;
                        if (vars == null || vars.Count == 0) continue;

                        var data = driver.ReadVariables(vars);
                        string json = BuildPayload(dev, vars, data);
                        string topic = _setting.MqttPrefix + dev.MqttDeviceId + "/" + g.Id;
                        bool pub = _mqtt != null && _mqtt.Publish(topic, json);
                        OnPublish?.Invoke(dev, topic, json);
                        if (!string.IsNullOrEmpty(TelemetryLogFile))
                        {
                            try { File.AppendAllText(TelemetryLogFile, topic + "\t" + json + "\n"); } catch { }
                        }
                        if (_simulate) Log($"[{dev.Id}] -> {topic} 发布={pub}");
                    }
                }
                catch (Exception ex) { Log($"[{dev.Id}] 异常: {ex.Message}"); }
                Thread.Sleep(500);
            }
            driver.Disconnect();
        }

        string BuildPayload(DeviceConfig dev, List<VarInfo> vars, Dictionary<string, List<double>> data)
        {
            long ts = (long)(DateTimeOffset.UtcNow - new DateTimeOffset(1970, 1, 1, 0, 0, 0, TimeSpan.Zero)).TotalMilliseconds;
            var props = new List<object>();
            foreach (var v in vars)
            {
                data.TryGetValue(v.Id, out var vals);
                if (vals == null) vals = new List<double> { 0 };
                props.Add(new
                {
                    MeasEncoding = v.Id,
                    MeasName = v.Remark,
                    value = vals,
                    TimeStamp = ts,
                    DeviceEncoding = dev.MqttDeviceId
                });
            }
            return JsonConvert.SerializeObject(new { properties = props });
        }

        void Log(string m) { OnLog?.Invoke($"[{DateTimeOffset.UtcNow:HH:mm:ss}] {m}"); }
    }
}
