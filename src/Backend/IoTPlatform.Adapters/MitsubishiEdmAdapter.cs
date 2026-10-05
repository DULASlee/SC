using System;
using System.Threading;
using System.Threading.Tasks;
using HslCommunication.Profinet.Melsec;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Adapters;

/// <summary>
/// 三菱 CNC EDM 电火花加工适配器：基于 HslCommunication.Profinet.Melsec.MelsecA1EAsciiNet（MIT 开源）。
/// </summary>
/// <remarks>
/// 替代原始 MknEdmRm1201.dll（三菱 CNC OEM SDK）。
/// MelsecA1EAsciiNet 实现 MELSEC A1E 协议（Fx5U / A 系列 PLC）。
/// MELSEC 默认端口：5000 (TCP)
/// 注：HslCommunication v13 的 MelsecA1E 类使用 ConnectServer 返回 OperateResult，
///     没有公开 IsConnect 属性，需自行跟踪连接状态。
/// </remarks>
public sealed class MitsubishiEdmAdapter : BaseAdapter
{
    public override string ProtocolName => "MitsubishiEdm";
    public bool MockMode { get; init; } = true;
    private MelsecA1EAsciiNet? _plc;

    protected override async Task<bool> ConnectCoreAsync(DeviceConnectionConfig config, CancellationToken ct)
    {
        if (MockMode) return true;
        try
        {
            _plc = new MelsecA1EAsciiNet();
            _plc.IpAddress = config.Endpoint;
            _plc.Port = config.Port;
            var op = await _plc.ConnectServerAsync().ConfigureAwait(false);
            return op.IsSuccess;
        }
        catch { return false; }
    }

    protected override async Task DisconnectCoreAsync(CancellationToken ct)
    {
        if (_plc is not null)
        {
            try { await _plc.ConnectCloseAsync().ConfigureAwait(false); } catch { }
            _plc = null;
        }
    }

    protected override async Task<object?> ReadTagCoreAsync(TagDefinition tag, CancellationToken ct)
    {
        if (MockMode)
        {
            await Task.Delay(50, ct).ConfigureAwait(false);
            return tag.Type switch
            {
                TagType.PLCBit => (object)(Random.Shared.Next(0, 2) == 1),
                TagType.PLCWord => (object)(short)Random.Shared.Next(short.MinValue, short.MaxValue),
                _ => 0
            };
        }
        if (_plc is null)
            throw new InvalidOperationException("PLC not connected");
        return tag.Type switch
        {
            TagType.PLCBit => (object)((await _plc.ReadBoolAsync(tag.Address).ConfigureAwait(false)).Content),
            TagType.PLCWord => (object)((await _plc.ReadInt16Async(tag.Address).ConfigureAwait(false)).Content),
            _ => throw new NotSupportedException($"Tag type {tag.Type} not supported by MitsubishiEdm")
        };
    }

    protected override async Task<bool> WriteTagCoreAsync(TagDefinition tag, object value, CancellationToken ct)
    {
        if (MockMode) return true;
        if (_plc is null) return false;
        return tag.Type switch
        {
            TagType.PLCWord when short.TryParse(value?.ToString(), out var s) =>
                (await _plc.WriteAsync(tag.Address, s).ConfigureAwait(false)).IsSuccess,
            TagType.PLCBit when bool.TryParse(value?.ToString(), out var b) =>
                (await _plc.WriteAsync(tag.Address, b).ConfigureAwait(false)).IsSuccess,
            _ => false
        };
    }

    protected override ValueTask DisposeCoreAsync()
    {
        _plc?.Dispose();
        _plc = null;
        return ValueTask.CompletedTask;
    }
}
