using System;
using System.IO;
using System.Threading;
using GenCollector.Core;

namespace GenCollector
{
    class Program
    {
        static void Main(string[] args)
        {
            string configDir = "config";
            bool simulate = false;
            bool noMqtt = false;
            string dumpFile = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--config" && i + 1 < args.Length) configDir = args[++i];
                else if (args[i] == "--simulate") simulate = true;
                else if (args[i] == "--no-mqtt") noMqtt = true;
                else if (args[i] == "--dump" && i + 1 < args.Length) dumpFile = args[++i];
            }
            if (simulate && dumpFile == null)
                dumpFile = Path.Combine(AppContext.BaseDirectory, "telemetry.jsonl");
            if (!Path.IsPathRooted(configDir)) configDir = Path.Combine(AppContext.BaseDirectory, configDir);
            if (!Directory.Exists(configDir)) { Console.WriteLine("配置目录不存在: " + configDir); return; }

            var setting = ConfigLoader.LoadSetting(configDir);
            var devices = ConfigLoader.LoadDevices(configDir);
            var varInfos = ConfigLoader.LoadVarInfo(configDir);
            var groups = ConfigLoader.LoadVarGroups(configDir);
            var protocols = ConfigLoader.LoadProtocols(configDir);
            if (setting.Simulate) simulate = true;

            Console.WriteLine("== GenCollector 通用采集器（无授权限制）==");
            Console.WriteLine($"配置目录 : {configDir}");
            Console.WriteLine($"MQTT     : {setting.MqttServer}  前缀: {setting.MqttPrefix}");
            Console.WriteLine($"设备数   : {devices.Count}   变量族: {varInfos.Count}   变量组: {groups.Count}");
            Console.WriteLine($"模拟模式 : {simulate}");

            var engine = new CollectorEngine(setting, devices, varInfos, groups, protocols, simulate);
            engine.NoMqtt = noMqtt;
            engine.TelemetryLogFile = dumpFile;
            engine.OnLog = m => Console.WriteLine(m);
            engine.OnPublish = (dev, topic, json) =>
            {
                // UI 层可在此订阅实时数据（或订阅 MQTT topic）
                if (simulate) Console.WriteLine($"PUBLISH {topic}\n  {json}");
            };
            engine.Start();

            Console.WriteLine("按 Q 退出（无控制台时按 Ctrl+C 停止）...");
            if (Console.IsInputRedirected)
            {
                Thread.Sleep(Timeout.Infinite);
            }
            else
            {
                while (true)
                {
                    var k = Console.ReadKey(true);
                    if (k.KeyChar == 'q' || k.KeyChar == 'Q') break;
                }
            }
            engine.Stop();
        }
    }
}
