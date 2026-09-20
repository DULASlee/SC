using System;
using System.Collections.Generic;
using System.Data;
using Newtonsoft.Json.Linq;

namespace GenDashboard
{
    // 看板核心数据模型：脱离 WinForms，可独立单元测试。
    // 负责把一行 JSONL 遥测（topic\tjson）解析为结构化记录，并按 设备|变量编码 主键 upsert 到 DataTable。
    public class TelemetryRecord
    {
        public string Device = "";
        public string VarCode = "";
        public string VarName = "";
        public string AddrCode = "";
        public string Value = "";
        public string Time = "";
    }

    public class DashboardModel
    {
        private readonly Dictionary<string, string> _addrMap;

        // addrMap: 语义变量(MeasEncoding) -> 协议地址码展示串（可多品牌合并）
        public DashboardModel(Dictionary<string, string> addrMap)
        {
            _addrMap = addrMap ?? new Dictionary<string, string>();
        }

        public List<TelemetryRecord> ParseLine(string topic, string json)
        {
            var list = new List<TelemetryRecord>();
            try
            {
                var obj = JObject.Parse(json);
                if (obj["properties"] is not JArray props) return list;
                foreach (var p in props)
                {
                    string dev = (string)p["DeviceEncoding"] ?? "";
                    string code = (string)p["MeasEncoding"] ?? "";
                    string name = (string)p["MeasName"] ?? "";
                    string val = "";
                    if (p["value"] is JArray v && v.Count > 0) val = v[0].ToString();
                    long ts = p["TimeStamp"] != null ? (long)p["TimeStamp"] : 0;
                    string time = ts > 0
                        ? DateTimeOffset.FromUnixTimeMilliseconds(ts).LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss")
                        : "";
                    string addr = _addrMap.TryGetValue(code, out var a) ? a : "";
                    list.Add(new TelemetryRecord
                    {
                        Device = dev,
                        VarCode = code,
                        VarName = name,
                        AddrCode = addr,
                        Value = val,
                        Time = time
                    });
                }
            }
            catch { /* 单行解析失败忽略 */ }
            return list;
        }

        public void Ingest(DataTable dt, string topic, string json)
        {
            foreach (var rec in ParseLine(topic, json))
            {
                var rows = dt.Select(
                    $"Device='{rec.Device.Replace("'", "''")}' AND VarCode='{rec.VarCode.Replace("'", "''")}'");
                if (rows.Length > 0)
                {
                    rows[0]["VarName"] = rec.VarName;
                    rows[0]["AddrCode"] = rec.AddrCode;
                    rows[0]["Value"] = rec.Value;
                    rows[0]["Time"] = rec.Time;
                }
                else
                {
                    dt.Rows.Add(rec.Device, rec.VarCode, rec.VarName, rec.AddrCode, rec.Value, rec.Time);
                }
            }
        }
    }
}
