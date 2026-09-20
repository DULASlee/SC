using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 数据汇接口：Collector 采集数据后的上报目标。
/// </summary>
/// <remarks>
/// 内置实现：
///   - <see cref="IoTPlatform.Core.Pipelines.MqttDataSink"/> — MQTT Broker（生产）
///   - <see cref="IoTPlatform.Core.Pipelines.JsonDataSink"/> — 本地 JSON 文件（调试）
/// 扩展：
///   - DbDataSink（InfluxDB / TimescaleDB）
///   - RestDataSink（HTTP POST 到 MES/ERP）
///   - ConsoleDataSink（stdout，仅调试）
/// </remarks>
public interface IDataSink : IAsyncDisposable
{
    /// <summary>数据汇名称（如 "MQTT-Broker", "JSON-File"）。</summary>
    string Name { get; }

    /// <summary>是否已连接/就绪。</summary>
    bool IsReady { get; }

    /// <summary>初始化（建立连接、打开文件等）。</summary>
    Task<bool> InitializeAsync(CancellationToken ct = default);

    /// <summary>发布单条采样数据。</summary>
    /// <param name="topic">目标主题（如 "realtime/CNC04"）。</param>
    /// <param name="data">采样数据。</param>
    Task PublishAsync(string topic, SampleData data, CancellationToken ct = default);

    /// <summary>批量发布（提高吞吐）。</summary>
    Task PublishBatchAsync(string topic, IEnumerable<SampleData> data, CancellationToken ct = default);
}
