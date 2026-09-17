using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;

namespace IoTPlatform.Core.Pipelines;

/// <summary>
/// JSON 文件数据汇：把每次采样以 JSON 行写入文件（NDJSON 格式）。
/// 适用于调试 / 无 MQTT Broker 环境 / 离线分析。
/// </summary>
public sealed class JsonDataSink : IDataSink
{
    private readonly string _filePath;
    private readonly object _writeLock = new();
    private StreamWriter? _writer;
    private bool _disposed;

    public string Name => "JSON-File";
    public bool IsReady => _writer is not null && !_disposed;

    public ILogger Logger { get; init; } = NullLogger.Instance;

    public JsonDataSink(string filePath)
    {
        _filePath = filePath ?? throw new ArgumentNullException(nameof(filePath));
    }

    public Task<bool> InitializeAsync(CancellationToken ct = default)
    {
        try
        {
            var dir = Path.GetDirectoryName(_filePath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            var stream = new FileStream(_filePath, FileMode.Append, FileAccess.Write, FileShare.Read);
            _writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true };
            Logger.LogInformation("JsonDataSink writing to {File}", _filePath);
            return Task.FromResult(true);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "JsonDataSink open failed");
            return Task.FromResult(false);
        }
    }

    public Task PublishAsync(string topic, SampleData data, CancellationToken ct = default)
    {
        if (_writer is null) throw new InvalidOperationException("Sink not initialized");
        var json = JsonSerializer.Serialize(new
        {
            topic,
            deviceId = data.DeviceId,
            timestamp = data.Timestamp,
            elapsedMs = data.ElapsedMs,
            values = data.Values,
            errors = data.Errors
        });
        lock (_writeLock)
        {
            _writer.WriteLine(json);
        }
        return Task.CompletedTask;
    }

    public async Task PublishBatchAsync(string topic, IEnumerable<SampleData> data, CancellationToken ct = default)
    {
        foreach (var d in data) await PublishAsync(topic, d, ct).ConfigureAwait(false);
    }

    public ValueTask DisposeAsync()
    {
        if (_disposed) return ValueTask.CompletedTask;
        _disposed = true;
        if (_writer is not null) { _writer.Flush(); _writer.Dispose(); _writer = null; }
        return ValueTask.CompletedTask;
    }
}
