using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace GenCollector.Drivers
{
    // 三菱 CNC 驱动：直接复用原机带的 RemoteComm.dll（PInvoke 调用，已验证可用）
    public class MitsubishiCncDriver : IDeviceDriver
    {
        [DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
        static extern int remote_new_connect(string IP);

        [DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
        static extern int remote_read_macro_p(int nHandle, int nMacro, double[] val);

        [DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
        static extern int remote_read_plc_variable_p_2(int nHandle, string PLCAdress, int type, long[] val);

        private int _handle = -1;
        public string LastError { get; private set; }
        public string DriverName => "MitsubishiCnc(RemoteComm)";

        public bool Connect(DeviceConfig dev, SettingConfig setting)
        {
            try { _handle = remote_new_connect(dev.Ip); return _handle >= 0; }
            catch (Exception ex) { LastError = ex.Message; return false; }
        }

        public Dictionary<string, List<double>> ReadVariables(List<VarInfo> vars)
        {
            var res = new Dictionary<string, List<double>>();
            if (_handle < 0) return res;
            foreach (var v in vars)
            {
                try
                {
                    string rt = string.IsNullOrEmpty(v.ReadType) ? Infer(v) : v.ReadType;
                    if (rt == "plc")
                    {
                        long[] buf = new long[1];
                        remote_read_plc_variable_p_2(_handle, v.Addr, 1, buf);
                        res[v.Id] = new List<double> { (double)buf[0] };
                    }
                    else
                    {
                        if (!int.TryParse(v.Addr, out var macro)) { res[v.Id] = new List<double> { 0 }; continue; }
                        double[] buf = new double[1];
                        remote_read_macro_p(_handle, macro, buf);
                        res[v.Id] = new List<double> { buf[0] };
                    }
                }
                catch (Exception ex) { LastError = ex.Message; res[v.Id] = new List<double> { 0 }; }
            }
            return res;
        }

        static string Infer(VarInfo v)
        {
            if (v.Addr != null && v.Addr.Contains(".")) return "plc";
            return "macro";
        }

        public void Disconnect() { _handle = -1; }
    }
}
