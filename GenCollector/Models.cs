using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;

namespace GenCollector
{
    // ---------- 配置数据模型（与原始 INI 契约一致）----------

    public class SettingConfig
    {
        public string AppId { get; set; } = "CNC";
        public string MqttServer { get; set; } = "127.0.0.1:1883";
        public string MqttPrefix { get; set; } = "/YLCY/CNC/";
        public int Port { get; set; } = 8080;
        public string AuthCode { get; set; } = "";   // 仅保留字段，引擎不再校验（通用化）
        public bool Simulate { get; set; } = false;  // 无硬件时合成数据，便于 UI 开发
    }

    public class DeviceConfig
    {
        public string Id { get; set; }
        public string Ip { get; set; }
        public string Port { get; set; }
        public string Protocol { get; set; }     // 格式: family:version，例如 mitsubishi_cnc:mitsubishi_v3
        public string MqttDeviceId { get; set; }
        public string Use { get; set; }
        [JsonIgnore] public string ProtocolFamily => (Protocol ?? "").Split(':')[0];
        [JsonIgnore] public bool Enabled => (Use ?? "1") == "1";
    }

    public class VarInfo
    {
        public string Id { get; set; }
        public string Addr { get; set; }          // 真实协议地址（宏号 / PLC地址 / 寄存器地址）
        public string Remark { get; set; }        // 中文语义名
        public string DataType { get; set; }      // int / float / string
        public string Group { get; set; }         // realtime / tech / spc
        public string DeviceId { get; set; }
        public string Trigger { get; set; }
        public string Use { get; set; }
        public string ReadType { get; set; }      // 扩展：macro / plc / reg（驱动如何读取该变量）
        [JsonIgnore] public bool Enabled => (Use ?? "1") == "1";
    }

    public class VarGroup
    {
        public string Id { get; set; }
        public int Timer { get; set; } = 20;      // 秒
    }

    public class ProtocolConfig
    {
        public string Id { get; set; }
        public int PollingInterval { get; set; }  // 毫秒
        public int TagInterval { get; set; }
    }

    // ---------- 极简 INI 解析（支持 [section] 与 key=value，value 可为 JSON）----------

    public class IniDocument
    {
        public Dictionary<string, string> Global { get; set; } = new Dictionary<string, string>();
        public Dictionary<string, Dictionary<string, string>> Sections { get; set; } =
            new Dictionary<string, Dictionary<string, string>>();

        public static IniDocument Parse(string text)
        {
            var doc = new IniDocument();
            Dictionary<string, string> current = null;
            foreach (var raw in text.Replace("\r\n", "\n").Split('\n'))
            {
                var line = raw.Trim();
                if (line == "" || line.StartsWith("#") || line.StartsWith(";")) continue;
                if (line.StartsWith("[") && line.EndsWith("]"))
                {
                    var name = line.Substring(1, line.Length - 2);
                    current = new Dictionary<string, string>();
                    doc.Sections[name] = current;
                    continue;
                }
                int eq = line.IndexOf('=');
                if (eq < 0) continue;
                var key = line.Substring(0, eq).Trim();
                var val = line.Substring(eq + 1).Trim();
                if (current == null) doc.Global[key] = val;
                else current[key] = val;
            }
            return doc;
        }
    }

    public static class DictExt
    {
        public static string TryGet(this Dictionary<string, string> d, string k)
        {
            return d != null && d.TryGetValue(k, out var v) ? v : "";
        }
    }
}
