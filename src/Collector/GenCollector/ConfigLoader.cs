using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;

namespace GenCollector
{
    public static class ConfigLoader
    {
        public static SettingConfig LoadSetting(string dir)
        {
            var path = Path.Combine(dir, "setting.ini");
            if (!File.Exists(path)) return new SettingConfig();
            var doc = IniDocument.Parse(File.ReadAllText(path));
            // 合并 全局 + 各 section（兼容带 [setting] 节头与无节头两种写法）
            var g = new Dictionary<string, string>();
            foreach (var kv in doc.Global) g[kv.Key] = kv.Value;
            foreach (var sec in doc.Sections.Values) foreach (var kv in sec) g[kv.Key] = kv.Value;
            var s = new SettingConfig
            {
                AppId = g.TryGet("appId"),
                MqttServer = g.TryGet("mqttServer"),
                MqttPrefix = g.TryGet("mqttPrefix"),
                Port = int.TryParse(g.TryGet("port"), out var p) ? p : 8080,
                AuthCode = g.TryGet("authCode"),
                // 注意：authMsg/authCode/sn/devId 仅作信息保留，引擎不再做授权/设备数限制（已通用化）
            };
            if (g.TryGet("simulate") == "1") s.Simulate = true;
            if (string.IsNullOrEmpty(s.MqttPrefix)) s.MqttPrefix = "/YLCY/CNC/";
            return s;
        }

        public static List<DeviceConfig> LoadDevices(string dir)
        {
            var list = new List<DeviceConfig>();
            foreach (var f in Directory.GetFiles(dir, "device_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                var sources = new List<Dictionary<string, string>> { doc.Global };
                sources.AddRange(doc.Sections.Values);
                foreach (var kvp in sources)
                    foreach (var kv in kvp)
                    {
                        try
                        {
                            var d = JsonConvert.DeserializeObject<DeviceConfig>(kv.Value);
                            if (d != null) { d.Id = d.Id ?? kv.Key; list.Add(d); }
                        }
                        catch { }
                    }
            }
            return list;
        }

        // section 名即协议族（family），如 [mitsubishi_cnc]
        public static Dictionary<string, List<VarInfo>> LoadVarInfo(string dir)
        {
            var map = new Dictionary<string, List<VarInfo>>();
            foreach (var f in Directory.GetFiles(dir, "var_info_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                foreach (var sec in doc.Sections)
                {
                    var lst = new List<VarInfo>();
                    foreach (var kv in sec.Value)
                    {
                        try
                        {
                            var v = JsonConvert.DeserializeObject<VarInfo>(kv.Value);
                            if (v != null) { v.Id = kv.Key; if (string.IsNullOrEmpty(v.Group)) v.Group = "realtime"; lst.Add(v); }
                        }
                        catch { }
                    }
                    var key = sec.Key.ToLower();
                    if (!map.ContainsKey(key)) map[key] = new List<VarInfo>();
                    map[key].AddRange(lst);
                }
            }
            return map;
        }

        public static List<VarGroup> LoadVarGroups(string dir)
        {
            var list = new List<VarGroup>();
            foreach (var f in Directory.GetFiles(dir, "var_group_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                foreach (var sec in doc.Sections)
                    foreach (var kv in sec.Value)
                    {
                        try
                        {
                            var g = JsonConvert.DeserializeObject<VarGroup>(kv.Value);
                            if (g != null) list.Add(g);
                        }
                        catch { }
                    }
            }
            if (list.Count == 0) list.Add(new VarGroup { Id = "realtime", Timer = 20 });
            return list;
        }

        public static Dictionary<string, ProtocolConfig> LoadProtocols(string dir)
        {
            var map = new Dictionary<string, ProtocolConfig>();
            foreach (var f in Directory.GetFiles(dir, "protocol_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                foreach (var sec in doc.Sections)
                {
                    var pc = new ProtocolConfig { Id = sec.Key };
                    if (int.TryParse(sec.Value.TryGet("pollingInterval"), out var pi)) pc.PollingInterval = pi;
                    if (int.TryParse(sec.Value.TryGet("tagInterval"), out var ti)) pc.TagInterval = ti;
                    map[sec.Key] = pc;
                }
            }
            return map;
        }
    }
}
