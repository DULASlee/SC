using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;

namespace IoTPlatform.Core.Base;

/// <summary>
/// 采集器抽象基类：实现 ICollector 的通用周期循环、状态机、事件分发。
/// </summary>
public abstract class BaseCollector : ICollector
{
    private readonly object _statusLock = new();
    private CancellationTokenSource? _loopCts;
    private Task? _loopTask;
    private CollectorStatus _status = CollectorStatus.Stopped;

    protected ILogger Logger { get; }

    public string DeviceId { get; }
    public string? Description { get; init; }
    public TimeSpan SampleInterval { get; init; } = TimeSpan.FromSeconds(1);

    /// <summary>设备协议适配器实例。可由 Host 在 Start 之前注入。</summary>
    public IDeviceAdapter Adapter { get; set; } = null!;

    /// <summary>数据汇实例。可由 Host 在 Start 之前注入。</summary>
    public IDataSink DataSink { get; set; } = null!;

    public CollectorStatus Status
    {
        get
        {
            lock (_statusLock)
            {
                return _status;
            }
        }

        private set
        {
            lock (_statusLock)
            {
                _status = value;
            }
        }
    }

    public event EventHandler<CollectorStatusChangedEventArgs>? StatusChanged;
    public event EventHandler<SampleDataCollectedEventArgs>? SampleCollected;
    public event EventHandler<CollectorErrorEventArgs>? Error;

    protected BaseCollector(string deviceId, ILogger? logger = null)
    {
        if (string.IsNullOrWhiteSpace(deviceId))
        {
            throw new ArgumentException("DeviceId cannot be empty", nameof(deviceId));
        }
        DeviceId = deviceId;
        Logger = logger ?? NullLogger.Instance;
    }

    protected abstract Task<IDeviceAdapter> BuildAdapterAsync(CancellationToken ct);
    protected abstract Task<IDataSink> BuildDataSinkAsync(CancellationToken ct);
    protected abstract IReadOnlyList<TagDefinition> DefineTags();
    protected virtual IReadOnlyList<TagReadResult> PostProcess(IReadOnlyList<TagReadResult> raw) => raw;
    protected virtual string TopicTemplate => "realtime/{deviceId}";

    public async Task StartAsync(CancellationToken ct = default)
    {
        if (Status != CollectorStatus.Stopped)
        {
            Logger.LogWarning("Collector {DeviceId} already started (status={Status})", DeviceId, Status);
            return;
        }

        SetStatus(CollectorStatus.Starting, "Starting");

        try
        {
            if (Adapter is null)
            {
                Adapter = await BuildAdapterAsync(ct).ConfigureAwait(false);
            }

            if (DataSink is null)
            {
                DataSink = await BuildDataSinkAsync(ct).ConfigureAwait(false);
            }

            var ready = await DataSink.InitializeAsync(ct).ConfigureAwait(false);
            if (!ready)
            {
                throw new InvalidOperationException($"DataSink {DataSink.Name} failed to initialize");
            }

            _loopCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            _loopTask = RunLoopAsync(_loopCts.Token);

            SetStatus(CollectorStatus.Running, "Running");
            Logger.LogInformation("Collector {DeviceId} started (interval={IntervalMs}ms)",
                DeviceId, SampleInterval.TotalMilliseconds);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Collector {DeviceId} start failed", DeviceId);
            SetStatus(CollectorStatus.Error, ex.Message);
            await DisposeAdapterAndSinkAsync().ConfigureAwait(false);
            throw;
        }
    }

    public async Task StopAsync(CancellationToken ct = default)
    {
        if (Status == CollectorStatus.Stopped || Status == CollectorStatus.Stopping)
        {
            return;
        }

        SetStatus(CollectorStatus.Stopping, "Stopping");
        _loopCts?.Cancel();
        if (_loopTask is not null)
        {
            try
            {
                await _loopTask.ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                /* expected */
            }
        }
        await DisposeAdapterAndSinkAsync().ConfigureAwait(false);
        SetStatus(CollectorStatus.Stopped, "Stopped");
        Logger.LogInformation("Collector {DeviceId} stopped", DeviceId);
    }

    public async Task<IReadOnlyList<TagReadResult>> SampleOnceAsync(CancellationToken ct = default)
    {
        if (Adapter is null)
        {
            throw new InvalidOperationException("Adapter not initialized");
        }
        var tags = DefineTags();
        var sw = Stopwatch.StartNew();
        var results = await Adapter.ReadTagsAsync(tags, ct).ConfigureAwait(false);
        sw.Stop();
        results = PostProcess(results);
        OnSampleCollected(results, sw.Elapsed);
        return results;
    }

    private async Task RunLoopAsync(CancellationToken ct)
    {
        var backoff = TimeSpan.FromSeconds(1);
        var maxBackoff = TimeSpan.FromSeconds(60);
        var tags = DefineTags();
        var topic = TopicTemplate.Replace("{deviceId}", DeviceId);

        while (!ct.IsCancellationRequested)
        {
            var sw = Stopwatch.StartNew();
            try
            {
                if (!Adapter.IsConnected)
                {
                    var connConfig = BuildConnectionConfig();
                    var ok = await Adapter.ConnectAsync(connConfig, ct).ConfigureAwait(false);
                    if (!ok)
                    {
                        Logger.LogWarning("Adapter connect failed for {DeviceId}, retry in {Backoff}s",
                            DeviceId, backoff.TotalSeconds);
                        await Task.Delay(backoff, ct).ConfigureAwait(false);
                        backoff = TimeSpan.FromTicks(Math.Min(backoff.Ticks * 2, maxBackoff.Ticks));
                        continue;
                    }

                    backoff = TimeSpan.FromSeconds(1);
                }

                var results = await Adapter.ReadTagsAsync(tags, ct).ConfigureAwait(false);
                results = PostProcess(results);
                OnSampleCollected(results, sw.Elapsed);

                if (DataSink.IsReady)
                {
                    var sample = SampleData.FromResults(DeviceId, results, sw.Elapsed);
                    try
                    {
                        await DataSink.PublishAsync(topic, sample, ct).ConfigureAwait(false);
                        if (Status == CollectorStatus.Degraded)
                        {
                            SetStatus(CollectorStatus.Running, "Sink recovered");
                        }
                    }
                    catch (Exception sinkEx)
                    {
                        SetStatus(CollectorStatus.Degraded, $"Sink failed: {sinkEx.Message}");
                        OnError(sinkEx, "DataSink.PublishAsync");
                    }
                }

                await Task.Delay(SampleInterval, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Loop error in {DeviceId}", DeviceId);
                SetStatus(CollectorStatus.Error, ex.Message);
                OnError(ex, "RunLoopAsync");
                try
                {
                    await Task.Delay(backoff, ct).ConfigureAwait(false);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }
    }

    protected virtual DeviceConnectionConfig BuildConnectionConfig()
        => new() { Endpoint = "127.0.0.1", Port = 0 };

    private void OnSampleCollected(IReadOnlyList<TagReadResult> results, TimeSpan elapsed)
        => SampleCollected?.Invoke(this, new SampleDataCollectedEventArgs
        {
            DeviceId = DeviceId,
            Results = results,
            Elapsed = elapsed
        });

    private void OnError(Exception ex, string context)
        => Error?.Invoke(this, new CollectorErrorEventArgs
        {
            DeviceId = DeviceId,
            Exception = ex,
            Context = context
        });

    private void SetStatus(CollectorStatus newStatus, string reason)
    {
        var old = Status;
        Status = newStatus;
        if (old != newStatus)
        {
            Logger.LogDebug("Collector {DeviceId}: {Old} -> {New} ({Reason})",
                DeviceId, old, newStatus, reason);
            StatusChanged?.Invoke(this, new CollectorStatusChangedEventArgs
            {
                DeviceId = DeviceId,
                OldStatus = old,
                NewStatus = newStatus,
                Reason = reason
            });
        }
    }

    private async Task DisposeAdapterAndSinkAsync()
    {
        if (Adapter is not null)
        {
            try
            {
                await Adapter.DisposeAsync().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "Adapter dispose error");
            }
        }

        if (DataSink is not null)
        {
            try
            {
                await DataSink.DisposeAsync().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                Logger.LogWarning(ex, "DataSink dispose error");
            }
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync().ConfigureAwait(false);
        _loopCts?.Dispose();
        GC.SuppressFinalize(this);
    }
}
