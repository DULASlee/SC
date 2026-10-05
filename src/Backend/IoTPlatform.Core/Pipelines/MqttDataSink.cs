using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using MQTTnet;
using MQTTnet.Protocol;

namespace IoTPlatform.Core.Pipelines;

/// <summary>
/// MQTT 数据汇：将 SampleData 通过 MQTT 5.0 发布到 Broker。
/// </summary>
/// <remarks>
/// 实现要点：
///   - 使用 MQTTnet 5.x（MqttClientFactory）
///   - QoS 0（AtMostOnce），与原始 LnkCollector 一致
///   - 自动重连由 MQTTnet 内部处理
/// </remarks>
public sealed class MqttDataSink : IDataSink
{
    private readonly MqttClientOptions _options;
    private readonly string _clientId;
    private IMqttClient? _client;
    private bool _disposed;

    public string Name => "MQTT-Broker";
    public bool IsReady => _client?.IsConnected ?? false;

    public ILogger Logger { get; init; } = NullLogger.Instance;

    public MqttDataSink(string broker, int port, string clientId,
        string? username = null, string? password = null)
    {
        _clientId = clientId;
        var builder = new MqttClientOptionsBuilder()
            .WithClientId(clientId)
            .WithTcpServer(broker, port)
            .WithCleanSession(true)
            .WithKeepAlivePeriod(TimeSpan.FromSeconds(60));
        if (!string.IsNullOrEmpty(username))
        {
            builder = builder.WithCredentials(username, password);
        }
        _options = builder.Build();
    }

    public async Task<bool> InitializeAsync(CancellationToken ct = default)
    {
        try
        {
            var factory = new MqttClientFactory();
            _client = factory.CreateMqttClient();
            _client.DisconnectedAsync += async e =>
                Logger.LogWarning("MQTT [{ClientId}] disconnected: {Reason}", _clientId, e.Reason);
            _client.ConnectedAsync += async e =>
                Logger.LogInformation("MQTT [{ClientId}] connected", _clientId);

            await _client.ConnectAsync(_options, ct).ConfigureAwait(false);
            return _client.IsConnected;
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "MQTT [{ClientId}] connect failed", _clientId);
            return false;
        }
    }

    public async Task PublishAsync(string topic, SampleData data, CancellationToken ct = default)
    {
        if (_client is null || !_client.IsConnected)
        {
            throw new InvalidOperationException("MQTT client not connected");
        }

        var payload = SerializeToJson(data);
        var msg = new MqttApplicationMessageBuilder()
            .WithTopic(topic)
            .WithPayload(payload)
            .WithQualityOfServiceLevel(MqttQualityOfServiceLevel.AtMostOnce)
            .Build();
        await _client.PublishAsync(msg, ct).ConfigureAwait(false);
    }

    public async Task PublishBatchAsync(string topic, IEnumerable<SampleData> data, CancellationToken ct = default)
    {
        foreach (var d in data)
        {
            await PublishAsync(topic, d, ct).ConfigureAwait(false);
        }
    }

    /// <summary>序列化为 IoTPlatform 标准 JSON。</summary>
    public static byte[] SerializeToJson(SampleData data)
    {
        return JsonSerializer.SerializeToUtf8Bytes(new
        {
            deviceId = data.DeviceId,
            timestamp = data.Timestamp,
            elapsedMs = data.ElapsedMs,
            values = data.Values,
            errors = data.Errors
        });
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        if (_client is not null)
        {
            try
            {
                await _client.DisconnectAsync().ConfigureAwait(false);
            }
            catch
            {
                /* ignore */
            }
            _client.Dispose();
        }
    }
}
