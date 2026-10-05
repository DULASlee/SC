using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using IoTPlatform.Core.Abstractions;

namespace IoTPlatform.Core.Pipelines;

/// <summary>
/// 采集器注册中心：管理所有 ICollector 实例，并向所有注册的 ICollectorView 广播事件。
/// </summary>
public sealed class CollectorRegistry
{
    private readonly ConcurrentDictionary<string, ICollector> _collectors = new();
    private readonly List<ICollectorView> _views = new();
    private readonly object _viewLock = new();

    public IReadOnlyCollection<ICollector> Collectors => (IReadOnlyCollection<ICollector>)_collectors.Values;

    public void Register(ICollector collector)
    {
        if (collector is null)
        {
            throw new ArgumentNullException(nameof(collector));
        }

        if (!_collectors.TryAdd(collector.DeviceId, collector))
        {
            throw new InvalidOperationException($"Collector {collector.DeviceId} already registered");
        }

        collector.StatusChanged += OnStatusChanged;
        collector.SampleCollected += OnSampleCollected;
        collector.Error += OnError;

        BroadcastView(v => v.RenderCollectors(Collectors));
    }

    public bool Unregister(string deviceId)
    {
        if (!_collectors.TryRemove(deviceId, out var c))
        {
            return false;
        }
        c.StatusChanged -= OnStatusChanged;
        c.SampleCollected -= OnSampleCollected;
        c.Error -= OnError;
        BroadcastView(v => v.RenderCollectors(Collectors));
        return true;
    }

    public void RegisterView(ICollectorView view)
    {
        if (view is null)
        {
            throw new ArgumentNullException(nameof(view));
        }
        lock (_viewLock)
        {
            _views.Add(view);
        }
        view.RenderCollectors(Collectors);
    }

    public ICollector? Get(string deviceId) => _collectors.TryGetValue(deviceId, out var c) ? c : null;

    public async Task StartAllAsync()
    {
        var tasks = _collectors.Values.Select(c => c.StartAsync()).ToArray();
        await Task.WhenAll(tasks).ConfigureAwait(false);
    }

    public async Task StopAllAsync()
    {
        var tasks = _collectors.Values.Select(c => c.StopAsync()).ToArray();
        await Task.WhenAll(tasks).ConfigureAwait(false);
    }

    public async ValueTask DisposeAsync()
    {
        await StopAllAsync().ConfigureAwait(false);
        foreach (var c in _collectors.Values)
        {
            try
            {
                await c.DisposeAsync().ConfigureAwait(false);
            }
            catch
            {
                /* ignore */
            }
        }
        _collectors.Clear();
    }

    private void OnStatusChanged(object? sender, CollectorStatusChangedEventArgs e)
        => BroadcastView(v => v.RenderStatusChange(e));

    private void OnSampleCollected(object? sender, SampleDataCollectedEventArgs e)
        => BroadcastView(v => v.RenderSampleData(e));

    private void OnError(object? sender, CollectorErrorEventArgs e)
        => BroadcastView(v => v.RenderError(e));

    private void BroadcastView(Action<ICollectorView> action)
    {
        ICollectorView[] snapshot;
        lock (_viewLock)
        {
            snapshot = _views.ToArray();
        }
        foreach (var v in snapshot)
        {
            try
            {
                action(v);
            }
            catch
            {
                /* don't let one view break others */
            }
        }
    }
}
