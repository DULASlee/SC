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
/// DHH-02 设备采集器（替代原始 HanBaCollector.exe）。
/// </summary>
/// <remarks>
/// 采集指标（来自反编译产物 DHH02/HanBaCollector.decompiled.cs）：
///   - YXMS (R0577) - 运行模式
///   - DQDL (R0974) - 电流
///   - FDSJH (R1929) - 放电火花 计数
///   - FDSJF (R1928) - 放电火花 幅度
///   - KJSJH (R1443) - 加工时间 计数
///   - KJSJF (R1442) - 加工时间 幅度
/// 注：原始 HanBaCollector 调用 HslCommunication.Authorization.SetAuthorizationCode，
///     这里因为是开源 MIT 版本，无授权检查。
/// </remarks>
public sealed class HanBaCollector : BaseCollector
{
    private readonly string _endpoint;
    private readonly int _port;
    private readonly string _mqttBroker;
    private readonly int _mqttPort;
    private readonly string _mqttClientId;

    public HanBaCollector(
        string deviceId, string endpoint, int port,
        string mqttBroker, int mqttPort, string mqttClientId,
        TimeSpan? sampleInterval = null, ILogger? logger = null)
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
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDeviceAdapter>(new HttpMemAdapter { MockMode = true });

    protected override Task<IoTPlatform.Core.Abstractions.IDataSink> BuildDataSinkAsync(CancellationToken ct)
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDataSink>(
            new IoTPlatform.Core.Pipelines.MqttDataSink(_mqttBroker, _mqttPort, _mqttClientId)
            { Logger = this.Logger });

    protected override IReadOnlyList<TagDefinition> DefineTags() => _tags;

    private static readonly IReadOnlyList<TagDefinition> _tags = new TagDefinition[]
    {
        new() { Name = "YXMS",  Type = TagType.HttpMemRegister, Address = "R0577", DisplayName = "运行模式" },
        new() { Name = "DQDL",  Type = TagType.HttpMemRegister, Address = "R0974", DisplayName = "电流" },
        new() { Name = "FDSJH", Type = TagType.HttpMemRegister, Address = "R1929", DisplayName = "放电计数" },
        new() { Name = "FDSJF", Type = TagType.HttpMemRegister, Address = "R1928", DisplayName = "放电幅度" },
        new() { Name = "KJSJH", Type = TagType.HttpMemRegister, Address = "R1443", DisplayName = "加工时间计数" },
        new() { Name = "KJSJF", Type = TagType.HttpMemRegister, Address = "R1442", DisplayName = "加工时间幅度" }
    };
}
