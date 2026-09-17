using System;
using System.Collections.Generic;

namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// UI 视图接口：UI 层只需实现这个接口即可与采集平台交互，
/// 不绑定具体 UI 框架（WPF / Avalonia / MAUI / WinForms / Console 通用）。
/// </summary>
/// <remarks>
/// 推荐用法：
///   1. UI 创建时注册到 CollectorRegistry
///   2. CollectorRegistry 在采集器状态变化时调用对应 View 方法
///   3. UI 通过 ViewModel 进一步渲染到具体控件
/// </remarks>
public interface ICollectorView
{
    /// <summary>显示采集器列表（程序启动时调用一次）。</summary>
    void RenderCollectors(IEnumerable<ICollector> collectors);

    /// <summary>显示状态变化（每次 Collector 状态切换）。</summary>
    void RenderStatusChange(CollectorStatusChangedEventArgs args);

    /// <summary>显示实时数据（每次采样完成）。</summary>
    void RenderSampleData(SampleDataCollectedEventArgs args);

    /// <summary>显示错误。</summary>
    void RenderError(CollectorErrorEventArgs args);
}
