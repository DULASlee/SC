using System;
using System.Collections.Generic;
using System.Data;
using System.IO;
using Xunit;

namespace GenDashboard.Tests
{
    public class DashboardModelTests
    {
        private static Dictionary<string, string> SampleMap() => new()
        {
            ["spindleSpeed"] = "fanuc:40 / mitsubishi:74804 / simens:74758",
            ["runTime"] = "fanuc:68 / mitsubishi:74807 / simens:74758",
        };

        private static DataTable NewTable()
        {
            var dt = new DataTable();
            dt.Columns.Add("Device");
            dt.Columns.Add("VarCode");
            dt.Columns.Add("VarName");
            dt.Columns.Add("AddrCode");
            dt.Columns.Add("Value");
            dt.Columns.Add("Time");
            return dt;
        }

        [Fact]
        public void ParseLine_resolves_addrCode_and_time_from_payload()
        {
            var model = new DashboardModel(SampleMap());
            const string json = "{\"properties\":[{\"MeasEncoding\":\"spindleSpeed\",\"MeasName\":\"主轴速度\",\"value\":[1790.6],\"TimeStamp\":1789618961383,\"DeviceEncoding\":\"CNC-07\"}]}";

            var recs = model.ParseLine("/YLCY/CNC/CNC-07/realtime", json);

            Assert.Single(recs);
            Assert.Equal("CNC-07", recs[0].Device);
            Assert.Equal("spindleSpeed", recs[0].VarCode);
            Assert.Equal("主轴速度", recs[0].VarName);
            Assert.Equal("1790.6", recs[0].Value);
            Assert.Contains("fanuc:40", recs[0].AddrCode);
            var expectedTime = DateTimeOffset.FromUnixTimeMilliseconds(1789618961383)
                .LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss");
            Assert.Equal(expectedTime, recs[0].Time);
        }

        [Fact]
        public void ParseLine_unknown_var_has_empty_addrCode()
        {
            var model = new DashboardModel(SampleMap());
            const string json = "{\"properties\":[{\"MeasEncoding\":\"noSuchVar\",\"MeasName\":\"未知\",\"value\":[1.0],\"TimeStamp\":1789618961383,\"DeviceEncoding\":\"CNC-07\"}]}";

            var recs = model.ParseLine("t", json);

            Assert.Single(recs);
            Assert.Equal("", recs[0].AddrCode);
        }

        [Fact]
        public void ParseLine_malformed_json_returns_empty_without_throw()
        {
            var model = new DashboardModel(SampleMap());

            var recs = model.ParseLine("t", "not json at all");

            Assert.Empty(recs);
        }

        [Fact]
        public void Ingest_upserts_same_device_code_without_duplicating()
        {
            var model = new DashboardModel(SampleMap());
            var dt = NewTable();
            const string json = "{\"properties\":[{\"MeasEncoding\":\"runTime\",\"MeasName\":\"运行时间\",\"value\":[0.0],\"TimeStamp\":1789618961383,\"DeviceEncoding\":\"CNC-07\"}]}";

            model.Ingest(dt, "t", json);
            model.Ingest(dt, "t", json);

            Assert.Equal(1, dt.Rows.Count);
            Assert.Contains("fanuc:68", dt.Rows[0]["AddrCode"].ToString());
            Assert.Equal("运行时间", dt.Rows[0]["VarName"]);
        }

        [Fact]
        public void Ingest_real_telemetry_sample_populates_multiple_devices_with_addrCode()
        {
            var model = new DashboardModel(SampleMap());
            var dt = NewTable();
            string[] lines = File.ReadAllLines("telemetry.jsonl");

            int n = 0;
            foreach (var line in lines)
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }
                int tab = line.IndexOf('\t');
                string topic = tab >= 0 ? line.Substring(0, tab) : "";
                string json = tab >= 0 ? line.Substring(tab + 1) : line;
                model.Ingest(dt, topic, json);
                n++;
            }

            Assert.True(n > 0, "样本应为非空");
            Assert.True(dt.Rows.Count > 0, "应解析出至少一条记录");
            // 同一设备同一变量不应重复（upsert 生效）
            var keys = new HashSet<string>();
            foreach (DataRow r in dt.Rows)
            {
                Assert.True(keys.Add(r["Device"] + "|" + r["VarCode"]), "出现重复主键");
            }

            // 已知变量应带地址码（spindleSpeed 在映射中）
            bool sawAddr = false;
            foreach (DataRow r in dt.Rows)
            {
                if (r["VarCode"].ToString() == "spindleSpeed" && r["AddrCode"].ToString().Contains("fanuc:40"))
                {
                    sawAddr = true;
                }
            }
            Assert.True(sawAddr, "spindleSpeed 应解析出 fanuc:40 地址码");
        }
    }
}
