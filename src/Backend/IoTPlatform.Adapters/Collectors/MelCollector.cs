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
/// DHH-04 三菱 CNC EDM 电火花加工采集器（替代原始 MelCollector.exe）。
/// </summary>
/// <remarks>
/// 采集指标基于原始 MelCollector.exe + MknEdmRm1201.dll 反编译推断：
///   - ALARM_STATUS / ALARM_NUM / ALARM_MSG（报警状态/数量/消息）
///   - EFCT_SP_COND / EFCT_SP_COND_DATA（电加工条件）
///   - RNW_MACH_DEPTH / RNW_COND_DATA / RNW_EFCT_RADIUS（加工参数）
///   - RNW_EFCT_IES / RNW_EFCT_ENAB_PULSE / RNW_EFCT_ADC（电加工电气参数）
///   - RNW_WIRE_INFO（电极丝信息）
/// 注：原 C++ SDK 的 EDM 协议部分（GetEfctSpCondData 等）需 Wireshark 抓包确认；
///     当前以 MELSEC A1E PLC 寄存器形式暴露关键状态。
/// </remarks>
public sealed class MelCollector : BaseCollector
{
    private readonly string _endpoint;
    private readonly int _port;
    private readonly string _mqttBroker;
    private readonly int _mqttPort;
    private readonly string _mqttClientId;

    public MelCollector(
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
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDeviceAdapter>(new MitsubishiEdmAdapter { MockMode = true });

    protected override Task<IoTPlatform.Core.Abstractions.IDataSink> BuildDataSinkAsync(CancellationToken ct)
        => Task.FromResult<IoTPlatform.Core.Abstractions.IDataSink>(
            new IoTPlatform.Core.Pipelines.MqttDataSink(_mqttBroker, _mqttPort, _mqttClientId)
            { Logger = this.Logger });

    protected override IReadOnlyList<TagDefinition> DefineTags() => _tags;

    private static readonly IReadOnlyList<TagDefinition> _tags = new TagDefinition[]
    {
        // 报警状态
        new() { Name = "AlarmStatus", Type = TagType.PLCWord, Address = "D100", DisplayName = "报警状态" },
        new() { Name = "AlarmNum",    Type = TagType.PLCWord, Address = "D101", DisplayName = "报警数量" },
        new() { Name = "AlarmMsg",    Type = TagType.PLCWord, Address = "D102", DisplayName = "最新报警码" },
        // EDM 加工参数
        new() { Name = "EfctSpCond",      Type = TagType.PLCWord, Address = "D200", DisplayName = "电加工条件码" },
        new() { Name = "EfctSpCondData",  Type = TagType.PLCWord, Address = "D201", DisplayName = "电加工条件数据" },
        new() { Name = "RnwMachDepth",    Type = TagType.PLCFloat,Address = "D202", DisplayName = "加工深度", Unit = "mm" },
        new() { Name = "RnwCondData",     Type = TagType.PLCWord, Address = "D203", DisplayName = "加工条件" },
        new() { Name = "RnwEfctRadius",   Type = TagType.PLCFloat,Address = "D204", DisplayName = "电加工半径", Unit = "mm" },
        new() { Name = "RnwEfctIES",      Type = TagType.PLCWord, Address = "D205", DisplayName = "电加工 IES" },
        new() { Name = "RnwEfctEnabPulse",Type = TagType.PLCWord, Address = "D206", DisplayName = "电加工脉冲使能" },
        new() { Name = "RnwEfctADC",      Type = TagType.PLCWord, Address = "D207", DisplayName = "电加工 ADC" },
        new() { Name = "RnwWireInfo",     Type = TagType.PLCWord, Address = "D208", DisplayName = "电极丝信息" },
        // 运行状态
        new() { Name = "RunStatus",  Type = TagType.PLCBit, Address = "M100", DisplayName = "运行中" },
        new() { Name = "WireBroken", Type = TagType.PLCBit, Address = "M101", DisplayName = "断丝报警" }
    };
}
