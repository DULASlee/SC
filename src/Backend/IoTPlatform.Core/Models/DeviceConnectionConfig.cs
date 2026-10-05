using System.Collections.Generic;

namespace IoTPlatform.Core.Models;

/// <summary>
/// 设备连接配置。
/// </summary>
/// <remarks>
/// 配置来源：appsettings.json 或 UI 动态编辑。
/// </remarks>
public sealed class DeviceConnectionConfig
{
    /// <summary>设备 IP 地址（如 "192.168.3.14"）。</summary>
    public required string Endpoint { get; init; }

    /// <summary>设备端口（如 Fanuc CNC = 8193, HttpMem = 9990）。</summary>
    public required int Port { get; init; }

    /// <summary>可选的协议特定参数（如超时、重试次数）。</summary>
    public Dictionary<string, string>? Parameters { get; init; }

    /// <summary>连接超时（毫秒）。默认 3000。</summary>
    public int TimeoutMs { get; init; } = 3000;

    /// <summary>读/写超时（毫秒）。默认 3000。</summary>
    public int OperationTimeoutMs { get; init; } = 3000;

    public override string ToString() => $"{Endpoint}:{Port}";
}
