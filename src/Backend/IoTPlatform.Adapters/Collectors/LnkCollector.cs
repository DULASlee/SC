using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Adapters;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Models;
using Microsoft.Extensions.Logging;

namespace IoTPlatform.Collectors;

/// <summary>
/// CNC04 设备采集器（替代原始 LnkCollector.dll）。
/// </summary>
/// <remarks>
/// 采集指标（来自反编译产物 CNC04/LnkCollector.decompiled.cs）：
///   - WorkTime (宏 33868) - 系统加工时间
///   - RunTime  (宏 2097)  - 系统运行时间
///   - CutTime  (宏 33565) - 切削时间
///   - Products (宏 33869) - 加工件数
///   - RunStatus  (PLC 42.0) - 运行状态
///   - StopStatus (PLC 42.1) - 停机状态
///   - WarnStatus (PLC 50.14) - 系统报警状态
/// </remarks>
public sealed class LnkCollector : BaseCollector
{
    private readonly string _endpoint;
    private readonly int _port;
    private readonly string _mqttBroker;
    private readonly int _mqttPort;
    private readonly string _mqttClientId;

    public LnkCollector(
        string deviceId,
        string endpoint, int port,
        string mqttBroker, int mqttPort, string mqttClientId,
        TimeSpan? sampleInterval = null,
        ILogger? logger = null)
        : base(deviceId, logger)
    {
        _endpoint = endpoint;
        _port = port;
        _mqttBroker = mqttBroker;
        _mqttPort = mqttPort;
        _mqttClientId = mqttClientId;
        if (sampleInterval.HasValue) SampleInterval = sampleInterval.Value;
    }

    protected override DeviceConnectionConfig BuildConnectionConfig()
        => new() { Endpoint = _endpoint, Port = _port, TimeoutMs = 3000 };

    protected override Task<IoTPlatform.Core.Abstractions.IDeviceAdapter> BuildAdapterAsync(CancellationToken ct)
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDeviceAdapter>(new FanucCncAdapter { MockMode = true });

    protected override Task<IoTPlatform.Core.Abstractions.IDataSink> BuildDataSinkAsync(CancellationToken ct)
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDataSink>(
            new IoTPlatform.Core.Pipelines.MqttDataSink(_mqttBroker, _mqttPort, _mqttClientId)
            { Logger = this.Logger });

    protected override IReadOnlyList<TagDefinition> DefineTags() => _tags;

    private static readonly IReadOnlyList<TagDefinition> _tags = new TagDefinition[]
    {
        new() { Name = "WorkTime",  Type = TagType.CNCMacro, Address = "33868", DisplayName = "系统加工时间", Unit = "ms" },
        new() { Name = "RunTime",   Type = TagType.CNCMacro, Address = "2097",  DisplayName = "系统运行时间", Unit = "ms" },
        new() { Name = "CutTime",   Type = TagType.CNCMacro, Address = "33565", DisplayName = "切削时间",     Unit = "ms" },
        new() { Name = "Products",  Type = TagType.CNCMacro, Address = "33869", DisplayName = "加工件数" },
        new() { Name = "RunStatus", Type = TagType.PLCBit,   Address = "42.0",  DisplayName = "运行状态" },
        new() { Name = "StopStatus",Type = TagType.PLCBit,   Address = "42.1",  DisplayName = "停机状态" },
        new() { Name = "WarnStatus",Type = TagType.PLCBit,   Address = "50.14", DisplayName = "系统报警" }
    };
}
