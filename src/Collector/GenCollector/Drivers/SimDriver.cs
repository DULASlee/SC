using System;
using System.Collections.Generic;

namespace GenCollector.Drivers
{
    // 模拟驱动：无硬件时合成数据，便于 UI / 平台联调
    public class SimDriver : IDeviceDriver
    {
        private Random _rnd = new Random();
        private int _seq = 0;
        public string LastError { get; private set; }
        public string DriverName => "Simulator";

        public bool Connect(DeviceConfig dev, SettingConfig setting) => true;

        public Dictionary<string, List<double>> ReadVariables(List<VarInfo> vars)
        {
            var res = new Dictionary<string, List<double>>();
            foreach (var v in vars)
            {
                double val = 0;
                switch ((v.Id ?? "").ToLower())
                {
                    case "sts": case "statusstd": val = _seq % 2; break;
                    case "spindlespeed": val = Math.Round(800 + _rnd.NextDouble() * 4000, 1); break;
                    case "products": case "setproducts": val = _seq * 3; break;
                    case "runtime": case "runtine": val = _seq * 60; break;
                    case "cuttime": val = _seq * 45; break;
                    default: val = Math.Round(_rnd.NextDouble() * 100, 2); break;
                }
                res[v.Id] = new List<double> { val };
            }
            _seq++;
            return res;
        }

        public void Disconnect() { }
    }
}
