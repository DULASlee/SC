using System;

namespace GenCollector.Drivers
{
    // 协议驱动工厂：引擎按 device.protocol 的 family 选择驱动（协议可插拔）
    public static class DriverFactory
    {
        public static IDeviceDriver Create(string protocol, bool simulate)
        {
            if (simulate) return new SimDriver();
            var fam = (protocol ?? "").Split(':')[0].ToLower();
            switch (fam)
            {
                case "mitsubishi_cnc":
                    return new MitsubishiCncDriver();
                case "modbus":
                case "melsec":
                case "mitsubishi_plc":
                case "siemens_plc":
                case "siemens":
                case "omron":
                    return new HslPlcDriver(fam);
                // fanuc_cnc / siemens_cnc / haidehan620_cnc / gsk_cnc / syntec / brother / knd / mazak
                // 接入真实驱动后即可直连（地址映射写在 var_info_<family>.ini）。
                default:
                    Console.WriteLine($"[warn] 协议族 {fam} 暂未实现专用驱动，使用模拟数据（请在 Drivers/ 实现并注册到 DriverFactory）。");
                    return new SimDriver();
            }
        }
    }
}
