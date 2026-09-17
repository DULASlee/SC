using System.Collections.Generic;

namespace GenCollector.Drivers
{
    // 设备驱动统一接口：引擎与协议解耦，新增协议只需实现该接口
    public interface IDeviceDriver
    {
        bool Connect(DeviceConfig dev, SettingConfig setting);
        // 返回 varId -> 数值列表（与原报文 value 数组对应）
        Dictionary<string, List<double>> ReadVariables(List<VarInfo> vars);
        void Disconnect();
        string LastError { get; }
        string DriverName { get; }
    }
}
