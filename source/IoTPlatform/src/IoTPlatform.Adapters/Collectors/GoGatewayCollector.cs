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
/// Go 主网关客户端采集器（iot_CNC_PLC_IMM 重写后通过 HTTP 调用）。
/// </summary>
/// <remarks>
/// 待 Go 主网关源码重建（C9）完成后，此 Collector 通过 HTTP 调用其
/// /api/protocol/{type}?address=... 接口采集 CNC 设备数据。
/// </remarks>
public sealed class GoGatewayCollector : BaseCollector
{
    private readonly string _endpoint;
    private readonly int _port;
    private readonly string _mqttBroker;
    private readonly int _mqttPort;
    private readonly string _mqttClientId;

    public GoGatewayCollector(
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
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDeviceAdapter>(new GoGatewayAdapter());

    protected override Task<IoTPlatform.Core.Abstractions.IDataSink> BuildDataSinkAsync(CancellationToken ct)
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDataSink>(
            new IoTPlatform.Core.Pipelines.MqttDataSink(_mqttBroker, _mqttPort, _mqttClientId)
            { Logger = this.Logger });

    protected override IReadOnlyList<TagDefinition> DefineTags() => _tags;

    private static readonly IReadOnlyList<TagDefinition> _tags = new TagDefinition[]
    {
        new() { Name = "DeviceCount",   Type = TagType.Integer, Address = "stats.device_count" },
        new() { Name = "ActiveAlarms",  Type = TagType.Integer, Address = "stats.alarms" },
        new() { Name = "TotalSamples",  Type = TagType.Integer, Address = "stats.samples" },
        new() { Name = "Uptime",        Type = TagType.Integer, Address = "stats.uptime_seconds", Unit = "s" },
        new() { Name = "LastError",     Type = TagType.String,  Address = "stats.last_error" }
    };
}
