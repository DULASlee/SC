using System;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Adapters;

/// <summary>
/// Fanuc CNC 协议适配器：实现 Fanuc Focas 协议子集。
/// </summary>
/// <remarks>
/// Fanuc Focas 协议是 CNC 行业标准协议，HslCommunication v13 仅有消息类型定义
/// （CNCFanucSeriesMessage 等）但未提供 TCP 客户端实现。本类直接用 TcpClient
/// 实现 Focas 协议的核心命令：
///   - 读取 CNC 宏变量 (#1 ~ #33 / #100~ / #500~ / #1000~ 公共变量)
///   - 读取数据寄存器 D0 ~
///   - 读取 PMC 寄存器 R0~ / M0~
/// Focas 协议端口：8193 (Ethernet)
/// 二进制协议细节（包头/包尾/读写时序）需要 Wireshark 抓包确认，
/// 当前提供框架代码 + Mock 数据返回，便于 UI/采集器层测试。
///
/// 注：真实部署时建议：
///   1. 用 Wireshark 抓取 RemoteComm.dll 与 CNC 通信的报文
///   2. 根据实际报文格式调整 SendFrame / ReadFrame 方法
///   3. 或考虑使用商业 Focas 库（如 Fanuc Focas Library）
/// </remarks>
public sealed class FanucCncAdapter : BaseAdapter
{
    public override string ProtocolName => "FanucCNC";
    private TcpClient? _tcp;

    /// <summary>Mock 模式（默认 true）：无真实 CNC 时返回模拟数据，便于框架测试。</summary>
    public bool MockMode { get; init; } = true;

    protected override async Task<bool> ConnectCoreAsync(DeviceConnectionConfig config, CancellationToken ct)
    {
        if (MockMode) return true;
        try
        {
            _tcp = new TcpClient { NoDelay = true };
            using var connectCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            connectCts.CancelAfter(config.TimeoutMs);
            await _tcp.ConnectAsync(config.Endpoint, config.Port, connectCts.Token).ConfigureAwait(false);
            return _tcp.Connected;
        }
        catch { return false; }
    }

    protected override async Task DisconnectCoreAsync(CancellationToken ct)
    {
        if (_tcp is not null)
        {
            try { _tcp.Close(); } catch { }
            _tcp = null;
        }
        await Task.CompletedTask;
    }

    protected override async Task<object?> ReadTagCoreAsync(TagDefinition tag, CancellationToken ct)
    {
        if (MockMode) return await MockReadAsync(tag).ConfigureAwait(false);
        if (_tcp is null || !_tcp.Connected)
            throw new InvalidOperationException("Not connected");

        // 真实 Focas 协议：根据 tag 类型构建不同请求
        //   - CNCMacro: cmd=0x83 (read macro), payload=macro_id(2B) + length(2B)
        //   - PLCBit:   cmd=0x?? (read PMC)
        //   - PLCWord:  cmd=0x?? (read D register)
        // 此处省略真实协议实现（需 Wireshark 抓包确认）
        throw new NotImplementedException("Real Fanuc Focas protocol requires Wireshark capture; use MockMode=true for testing.");
    }

    protected override async Task<bool> WriteTagCoreAsync(TagDefinition tag, object value, CancellationToken ct)
    {
        if (MockMode) return true;
        throw new NotImplementedException("Real Fanuc Focas protocol requires Wireshark capture");
    }

    /// <summary>Mock 数据生成（按 tag 类型返回合理模拟值）。</summary>
    private static Task<object?> MockReadAsync(TagDefinition tag)
    {
        object value = tag.Name switch
        {
            "WorkTime"   => Random.Shared.NextDouble() * 100000,
            "RunTime"    => Random.Shared.NextDouble() * 200000,
            "CutTime"    => Random.Shared.NextDouble() * 50000,
            "Products"   => Random.Shared.Next(0, 500),
            "RunStatus"  => Random.Shared.Next(0, 2) == 1,
            "StopStatus" => false,
            "WarnStatus" => Random.Shared.Next(0, 100) < 5,
            _ => tag.Type switch
            {
                TagType.CNCMacro        => Random.Shared.NextDouble() * 1000,
                TagType.PLCBit           => Random.Shared.Next(0, 2) == 1,
                TagType.PLCWord          => (short)Random.Shared.Next(short.MinValue, short.MaxValue),
                TagType.HttpMemRegister  => Random.Shared.Next(0, 1000),
                _                        => 0
            }
        };
        return Task.FromResult<object?>(value);
    }

    protected override ValueTask DisposeCoreAsync()
    {
        _tcp?.Dispose();
        _tcp = null;
        return ValueTask.CompletedTask;
    }
}
