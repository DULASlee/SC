using System;
using System.Collections.Generic;
using HslCommunication;
using HslCommunication.ModBus;
using HslCommunication.Profinet.Melsec;
using HslCommunication.Profinet.Siemens;
using HslCommunication.Profinet.Omron;

namespace GenCollector.Drivers
{
    // 通用 PLC 驱动：基于开源 HslCommunication，覆盖 Modbus / 三菱PLC / 西门子PLC / 欧姆龙
    public class HslPlcDriver : IDeviceDriver
    {
        private object _net;
        private string _family;
        public string LastError { get; private set; }
        public string DriverName => "HslPlc:" + _family;

        public HslPlcDriver(string family) { _family = family; }

        public bool Connect(DeviceConfig dev, SettingConfig setting)
        {
            try
            {
                int port = int.TryParse(dev.Port, out var p) ? p : 0;
                switch (_family)
                {
                    case "modbus": _net = new ModbusTcpNet(dev.Ip, port == 0 ? 502 : port); break;
                    case "melsec": case "mitsubishi_plc": _net = new MelsecMcNet(dev.Ip, port == 0 ? 1025 : port); break;
                    case "siemens_plc": case "siemens": _net = new SiemensS7Net(SiemensPLCS.S1200, dev.Ip); break;
                    case "omron": _net = new OmronFinsNet(dev.Ip, port == 0 ? 9600 : port); break;
                    default: LastError = "unsupported family " + _family; return false;
                }
                dynamic net = (dynamic)_net;
                var r = net.ConnectServer();
                return r.IsSuccess;
            }
            catch (Exception ex) { LastError = ex.Message; return false; }
        }

        public Dictionary<string, List<double>> ReadVariables(List<VarInfo> vars)
        {
            var res = new Dictionary<string, List<double>>();
            if (_net == null) return res;
            dynamic net = (dynamic)_net;
            foreach (var v in vars)
            {
                try
                {
                    var fr = net.ReadFloat(v.Addr);
                    if (fr.IsSuccess) { res[v.Id] = new List<double> { (double)fr.Content }; continue; }
                    var ir = net.ReadInt32(v.Addr);
                    if (ir.IsSuccess) { res[v.Id] = new List<double> { (double)ir.Content }; continue; }
                    var sr = net.ReadInt16(v.Addr);
                    if (sr.IsSuccess) { res[v.Id] = new List<double> { (double)sr.Content }; continue; }
                    res[v.Id] = new List<double> { 0 };
                }
                catch (Exception ex) { LastError = ex.Message; res[v.Id] = new List<double> { 0 }; }
            }
            return res;
        }

        public void Disconnect() { try { ((dynamic)_net).ConnectClose(); } catch { } _net = null; }
    }
}
