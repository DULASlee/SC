using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 采集器接口：每个设备实例对应一个 ICollector。
/// 负责按 <see cref="SampleInterval"/> 周期调用 <see cref="IDeviceAdapter"/> 采集数据，
/// 通过 <see cref="IDataSink"/> 上报到 MQTT Broker 或其他目标。
/// </summary>
/// <remarks>
/// 生命周期：
///   Created -> StartAsync -> Running (周期循环) -> StopAsync -> Disposed
/// 异常处理：
///   适配器连接失败 -> Status = Error，自动重连（Backoff）
///   标签读取失败 -> 单条 TagReadResult 标记 Error，整体循环继续
/// </remarks>
public interface ICollector : IAsyncDisposable
{
    /// <summary>设备唯一标识（如 "CNC04", "DHH-02", "DHH-04"）。</summary>
    string DeviceId { get; }

    /// <summary>采集器描述（用于 UI 显示）。</summary>
    string? Description { get; }

    /// <summary>采集器当前状态。</summary>
    CollectorStatus Status { get; }

    /// <summary>采集周期。</summary>
    TimeSpan SampleInterval { get; }

    /// <summary>设备协议适配器实例。</summary>
    IDeviceAdapter Adapter { get; }

    /// <summary>数据汇实例。</summary>
    IDataSink DataSink { get; }

    /// <summary>启动采集循环。幂等：已启动时直接返回。</summary>
    /// <param name="ct">外部取消令牌（程序关闭时使用）。</param>
    Task StartAsync(CancellationToken ct = default);

    /// <summary>停止采集循环。幂等：未启动时直接返回。</summary>
    /// <param name="ct">外部取消令牌。</param>
    Task StopAsync(CancellationToken ct = default);

    /// <summary>手动触发一次采集（UI 测试按钮、健康检查）。</summary>
    /// <returns>本次采集的全部标签结果。</returns>
    Task<IReadOnlyList<TagReadResult>> SampleOnceAsync(CancellationToken ct = default);

    /// <summary>状态变化事件。UI 订阅此事件刷新显示。</summary>
    event EventHandler<CollectorStatusChangedEventArgs>? StatusChanged;

    /// <summary>采集数据事件（每次完整采集周期触发）。</summary>
    event EventHandler<SampleDataCollectedEventArgs>? SampleCollected;

    /// <summary>错误事件（适配器或 Sink 异常）。</summary>
    event EventHandler<CollectorErrorEventArgs>? Error;
}

/// <summary>采集器状态枚举。</summary>
public enum CollectorStatus
{
    /// <summary>已创建，未启动。</summary>
    Stopped,
    /// <summary>正在启动（连接适配器 + 连接 Sink）。</summary>
    Starting,
    /// <summary>正常运行。</summary>
    Running,
    /// <summary>降级运行（如 MQTT 重连中，但本地采集继续）。</summary>
    Degraded,
    /// <summary>错误状态（适配器断开 / 配置错误）。</summary>
    Error,
    /// <summary>正在停止。</summary>
    Stopping
}

/// <summary>状态变化事件参数。</summary>
public sealed class CollectorStatusChangedEventArgs : EventArgs
{
    public required string DeviceId { get; init; }
    public required CollectorStatus OldStatus { get; init; }
    public required CollectorStatus NewStatus { get; init; }
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
    public string? Reason { get; init; }
}

/// <summary>采集数据事件参数。</summary>
public sealed class SampleDataCollectedEventArgs : EventArgs
{
    public required string DeviceId { get; init; }
    public required IReadOnlyList<TagReadResult> Results { get; init; }
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
    public TimeSpan Elapsed { get; init; }
}

/// <summary>错误事件参数。</summary>
public sealed class CollectorErrorEventArgs : EventArgs
{
    public required string DeviceId { get; init; }
    public required Exception Exception { get; init; }
    public string? Context { get; init; }
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
}
