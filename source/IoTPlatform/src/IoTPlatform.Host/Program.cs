using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Adapters;
using IoTPlatform.Collectors;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Pipelines;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Console;

namespace IoTPlatform.Host;

/// <summary>
/// IoTPlatform 自宿主入口。
/// </summary>
/// <remarks>
/// 用法：
///   IoTPlatform.Host.exe                          # 默认 appsettings.json
///   IoTPlatform.Host.exe --config appsettings.dev.json
///   IoTPlatform.Host.exe --mock                   # 强制所有 Collector 进入 Mock 模式
///   IoTPlatform.Host.exe --dump-json [out_dir]    # 把采集数据 dump 到 NDJSON 文件
/// </remarks>
public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        var configFile = args.Length > 0 && !args[0].StartsWith("--") ? args[0] : "appsettings.json";
        var forceMock = args.Contains("--mock");
        var dumpIdx = Array.IndexOf(args, "--dump-json");
        var dumpDir = dumpIdx >= 0 && dumpIdx + 1 < args.Length ? args[dumpIdx + 1] : null;

        var config = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile(configFile, optional: false)
            .AddEnvironmentVariables()
            .Build();

        using var loggerFactory = LoggerFactory.Create(b =>
        {
            b.AddConfiguration(config.GetSection("Logging"));
            b.AddSimpleConsole(o => { o.SingleLine = true; o.TimestampFormat = "HH:mm:ss "; });
            b.SetMinimumLevel(LogLevel.Information);
        });
        var logger = loggerFactory.CreateLogger("IoTPlatform");

        logger.LogInformation("=========================================");
        logger.LogInformation("IoTPlatform Host starting");
        logger.LogInformation("Config: {Config} | Mock: {Mock} | Dump: {Dump}",
            configFile, forceMock, dumpDir ?? "(none)");
        logger.LogInformation("=========================================");

        var registry = new CollectorRegistry();
        var collectorSection = config.GetSection("Collectors");
        if (!collectorSection.Exists())
        {
            logger.LogError("No 'Collectors' section in config");
            return 1;
        }

        foreach (var sec in collectorSection.GetChildren())
        {
            try
            {
                var collector = BuildCollector(sec, dumpDir, forceMock, logger);
                if (collector is null) continue;
                registry.Register(collector);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to build collector {DeviceId}", sec.Key);
            }
        }

        registry.RegisterView(new ConsoleView(logger));

        var cts = new CancellationTokenSource();
        Console.CancelKeyPress += (_, e) => { e.Cancel = true; cts.Cancel(); };

        try
        {
            await registry.StartAllAsync();
            logger.LogInformation("All collectors started. Press Ctrl+C to stop.");
            try { await Task.Delay(Timeout.Infinite, cts.Token); }
            catch (OperationCanceledException) { }
        }
        finally
        {
            await registry.DisposeAsync();
            logger.LogInformation("IoTPlatform Host stopped");
        }

        return 0;
    }

    private static ICollector? BuildCollector(
        IConfigurationSection sec, string? dumpDir, bool forceMock, ILogger logger)
    {
        var deviceId = sec["DeviceId"] ?? throw new InvalidOperationException("DeviceId missing");
        var sampleMs = int.TryParse(sec["SampleIntervalMs"], out var ms) ? ms : 1000;
        var mqttBroker = sec["Mqtt:Broker"] ?? "127.0.0.1";
        var mqttPort = int.TryParse(sec["Mqtt:Port"], out var p) ? p : 1883;
        var clientId = sec["Mqtt:ClientId"] ?? deviceId;
        var topicPrefix = sec["Mqtt:TopicPrefix"] ?? $"realtime/{deviceId}";

        IDataSink sink;
        if (!string.IsNullOrEmpty(dumpDir))
        {
            var path = Path.Combine(dumpDir, $"{deviceId}.ndjson");
            sink = new JsonDataSink(path) { Logger = logger };
        }
        else
        {
            sink = new MqttDataSink(mqttBroker, mqttPort, clientId) { Logger = logger };
        }

        var adapterType = sec["Adapter:Type"] ?? "";
        var endpoint = sec["Adapter:Endpoint"] ?? "127.0.0.1";
        var port = int.TryParse(sec["Adapter:Port"], out var ap) ? ap : 0;
        var interval = TimeSpan.FromMilliseconds(sampleMs);

        return adapterType.ToLowerInvariant() switch
        {
            "fanuccnc" => new LnkCollector(deviceId, endpoint, port, mqttBroker, mqttPort, clientId, interval, logger)
            { DataSink = sink },
            "httpmem" => new HanBaCollector(deviceId, endpoint, port, mqttBroker, mqttPort, clientId, interval, logger)
            { DataSink = sink },
            "mitsubishiedm" => new MelCollector(deviceId, endpoint, port, mqttBroker, mqttPort, clientId, interval, logger)
            { DataSink = sink },
            "gogateway" => new GoGatewayCollector(deviceId, endpoint, port, mqttBroker, mqttPort, clientId, interval, logger)
            { DataSink = sink },
            _ => throw new NotSupportedException($"Unknown adapter type: {adapterType}")
        };
    }

    /// <summary>控制台 View：状态变化 + 数据节流输出到日志。</summary>
    private sealed class ConsoleView : ICollectorView
    {
        private readonly ILogger _logger;
        private readonly Dictionary<string, DateTime> _lastSample = new();

        public ConsoleView(ILogger logger) => _logger = logger;

        public void RenderCollectors(IEnumerable<ICollector> collectors)
        {
            _logger.LogInformation("Registered collectors: {Count}", collectors.Count());
            foreach (var c in collectors)
                _logger.LogInformation("  - {DeviceId} ({Status})", c.DeviceId, c.Status);
        }

        public void RenderStatusChange(CollectorStatusChangedEventArgs args)
            => _logger.LogInformation("[{DeviceId}] {Old} -> {New} ({Reason})",
                args.DeviceId, args.OldStatus, args.NewStatus, args.Reason ?? "");

        public void RenderSampleData(SampleDataCollectedEventArgs args)
        {
            if (_lastSample.TryGetValue(args.DeviceId, out var last) &&
                (DateTime.UtcNow - last).TotalSeconds < 5) return;
            _lastSample[args.DeviceId] = DateTime.UtcNow;
            var ok = args.Results.Count(r => r.IsSuccess);
            var fail = args.Results.Count - ok;
            _logger.LogInformation("[{DeviceId}] sampled {Ok}/{Total} in {Ms:F1}ms",
                args.DeviceId, ok, args.Results.Count, args.Elapsed.TotalMilliseconds);
        }

        public void RenderError(CollectorErrorEventArgs args)
            => _logger.LogError(args.Exception, "[{DeviceId}] error in {Context}",
                args.DeviceId, args.Context ?? "");
    }
}
