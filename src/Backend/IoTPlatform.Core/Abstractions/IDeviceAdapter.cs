using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 设备协议适配器接口：封装具体的工业协议实现（Fanuc CNC、HttpMem、Mitsubishi EDM 等）。
/// 由 Collector 通过 IDeviceAdapterFactory 创建并使用。
/// </summary>
/// <remarks>
/// 实现要求：
///   - ConnectAsync 应当建立物理连接（如 TCP socket）并完成协议握手
///   - ReadTagAsync 应当有合理的超时控制（默认 3 秒）
///   - 任何异常应当被捕获并包装为 <see cref="TagReadResult"/> 中的 Error，不抛出
/// </remarks>
public interface IDeviceAdapter : IAsyncDisposable
{
    /// <summary>协议名称（如 "FanucCNC", "HttpMem", "MitsubishiEdm"）。</summary>
    string ProtocolName { get; }

    /// <summary>当前连接状态。</summary>
    bool IsConnected { get; }

    /// <summary>连接设备。</summary>
    /// <param name="config">设备连接配置（IP / 端口 / 协议参数）。</param>
    /// <param name="ct">取消令牌。</param>
    /// <returns>连接成功返回 true。</returns>
    Task<bool> ConnectAsync(DeviceConnectionConfig config, CancellationToken ct = default);

    /// <summary>断开连接。幂等。</summary>
    Task DisconnectAsync(CancellationToken ct = default);

    /// <summary>读取单个标签。</summary>
    /// <param name="tag">标签定义。</param>
    /// <param name="ct">取消令牌。</param>
    /// <returns>读取结果（成功 / 失败都返回，不抛异常）。</returns>
    Task<TagReadResult> ReadTagAsync(TagDefinition tag, CancellationToken ct = default);

    /// <summary>批量读取多个标签。</summary>
    /// <remarks>实现应当尽可能复用连接以提高效率。</remarks>
    Task<IReadOnlyList<TagReadResult>> ReadTagsAsync(
        IEnumerable<TagDefinition> tags,
        CancellationToken ct = default);

    /// <summary>写入标签值（如 PLC 写入、设定值下发）。</summary>
    /// <returns>写入成功返回 true。</returns>
    Task<bool> WriteTagAsync(TagDefinition tag, object value, CancellationToken ct = default);
}

/// <summary>
/// 适配器工厂接口：用于运行时根据配置创建适配器实例。
/// </summary>
public interface IDeviceAdapterFactory
{
    /// <summary>支持的协议类型。</summary>
    string ProtocolType { get; }

    /// <summary>创建适配器实例。</summary>
    IDeviceAdapter Create();
}
