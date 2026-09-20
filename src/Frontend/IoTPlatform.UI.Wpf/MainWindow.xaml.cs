using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using IoTPlatform.Adapters;
using IoTPlatform.Collectors;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Pipelines;

namespace IoTPlatform.UI.Wpf;

/// <summary>
/// WPF UI 示例骨架 — 演示如何订阅 CollectorRegistry 事件。
/// </summary>
/// <remarks>
/// 这是最简演示，仅显示日志和按钮。
/// 实际生产 UI 应使用 MVVM 模式 + ICollectorView 实现。
/// 用户可根据需要扩展为完整 WPF / Avalonia / MAUI 应用。
/// </remarks>
public partial class MainWindow : Window, ICollectorView
{
    private CollectorRegistry? _registry;
    private CancellationTokenSource? _cts;

    public MainWindow()
    {
        InitializeComponent();
    }

    private void Append(string line)
    {
        Dispatcher.Invoke(() =>
        {
            LogBox.AppendText($"[{DateTimeOffset.UtcNow:HH:mm:ss}] {line}\n");
            LogBox.ScrollToEnd();
        });
    }

    private async void OnStartMock(object sender, RoutedEventArgs e)
    {
        try
        {
            _cts = new CancellationTokenSource();
            _registry = new CollectorRegistry();
            _registry.RegisterView(this);

            var dumpDir = Path.Combine(Path.GetTempPath(), "iot-platform-demo");
            Directory.CreateDirectory(dumpDir);

            // Mock 模式：3 个 Collector 使用模拟数据，数据写入 JSON 文件
            var lnk = new LnkCollector("CNC04", "127.0.0.1", 8193, "127.0.0.1", 1883, "lnk-wpf", TimeSpan.FromMilliseconds(1000));
            lnk.DataSink = new JsonDataSink(Path.Combine(dumpDir, "CNC04.ndjson"));
            _registry.Register(lnk);

            var hb = new HanBaCollector("DHH-02", "127.0.0.1", 9990, "127.0.0.1", 1883, "hanba-wpf", TimeSpan.FromMilliseconds(2000));
            hb.DataSink = new JsonDataSink(Path.Combine(dumpDir, "DHH-02.ndjson"));
            _registry.Register(hb);

            var mel = new MelCollector("DHH-04", "127.0.0.1", 5000, "127.0.0.1", 1883, "mel-wpf", TimeSpan.FromMilliseconds(2000));
            mel.DataSink = new JsonDataSink(Path.Combine(dumpDir, "DHH-04.ndjson"));
            _registry.Register(mel);

            await _registry.StartAllAsync();
            StatusText.Text = $"状态: 运行中 ({_registry.Collectors.Count} 个采集器)";
        }
        catch (Exception ex)
        {
            Append($"ERROR: {ex.Message}");
        }
    }

    private async void OnStop(object sender, RoutedEventArgs e)
    {
        if (_registry is null) return;
        _cts?.Cancel();
        await _registry.DisposeAsync();
        _registry = null;
        StatusText.Text = "状态: 已停止";
        Append("All collectors stopped.");
    }

    public void RenderCollectors(System.Collections.Generic.IEnumerable<ICollector> collectors)
    {
        foreach (var c in collectors)
            Append($"注册: {c.DeviceId}");
    }

    public void RenderStatusChange(CollectorStatusChangedEventArgs args)
        => Append($"[{args.DeviceId}] {args.OldStatus} -> {args.NewStatus}");

    public void RenderSampleData(SampleDataCollectedEventArgs args)
    {
        var ok = 0; foreach (var r in args.Results) if (r.IsSuccess) ok++;
        Append($"[{args.DeviceId}] sampled {ok}/{args.Results.Count} in {args.Elapsed.TotalMilliseconds:F1}ms");
    }

    public void RenderError(CollectorErrorEventArgs args)
        => Append($"[{args.DeviceId}] ERROR: {args.Exception.Message}");
}
