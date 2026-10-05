using System;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Abstractions;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Core.Base;

/// <summary>
/// 适配器抽象基类：实现 IDeviceAdapter 的通用连接管理。
/// 子类只需实现协议特定的 <see cref="ConnectCoreAsync"/>、<see cref="DisconnectCoreAsync"/>、
/// <see cref="ReadTagCoreAsync"/>、<see cref="WriteTagCoreAsync"/>。
/// </summary>
public abstract class BaseAdapter : IDeviceAdapter
{
    private bool _disposed;

    public abstract string ProtocolName { get; }
    public bool IsConnected { get; private set; }
    protected DeviceConnectionConfig? CurrentConfig { get; private set; }

    public async Task<bool> ConnectAsync(DeviceConnectionConfig config, CancellationToken ct = default)
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(GetType().Name);
        }
        try
        {
            IsConnected = false;
            CurrentConfig = config;
            IsConnected = await ConnectCoreAsync(config, ct).ConfigureAwait(false);
            return IsConnected;
        }
        catch (Exception)
        {
            IsConnected = false;
            throw;
        }
    }

    public async Task DisconnectAsync(CancellationToken ct = default)
    {
        if (!IsConnected)
        {
            return;
        }

        try
        {
            await DisconnectCoreAsync(ct).ConfigureAwait(false);
        }
        finally
        {
            IsConnected = false;
            CurrentConfig = null;
        }
    }

    public async Task<TagReadResult> ReadTagAsync(TagDefinition tag, CancellationToken ct = default)
    {
        if (!IsConnected)
        {
            return TagReadResult.Failure(tag, "Not connected", TimeSpan.Zero);
        }
        var sw = System.Diagnostics.Stopwatch.StartNew();
        try
        {
            var value = await ReadTagCoreAsync(tag, ct).ConfigureAwait(false);
            sw.Stop();
            return TagReadResult.Success(tag, value, sw.Elapsed);
        }
        catch (Exception ex)
        {
            sw.Stop();
            return TagReadResult.Failure(tag, ex.Message, sw.Elapsed);
        }
    }

    public async Task<IReadOnlyList<TagReadResult>> ReadTagsAsync(
        System.Collections.Generic.IEnumerable<TagDefinition> tags, CancellationToken ct = default)
    {
        var list = new System.Collections.Generic.List<TagReadResult>();
        foreach (var tag in tags)
        {
            if (ct.IsCancellationRequested)
            {
                break;
            }

            if (!tag.Enabled)
            {
                continue;
            }

            list.Add(await ReadTagAsync(tag, ct).ConfigureAwait(false));
        }
        return list;
    }

    public async Task<bool> WriteTagAsync(TagDefinition tag, object value, CancellationToken ct = default)
    {
        if (!IsConnected)
        {
            return false;
        }

        try
        {
            return await WriteTagCoreAsync(tag, value, ct).ConfigureAwait(false);
        }
        catch
        {
            return false;
        }
    }

    /// <summary>子类实现：协议特定的连接逻辑。</summary>
    protected abstract Task<bool> ConnectCoreAsync(DeviceConnectionConfig config, CancellationToken ct);

    /// <summary>子类实现：协议特定的断开逻辑。</summary>
    protected abstract Task DisconnectCoreAsync(CancellationToken ct);

    /// <summary>子类实现：协议特定的单标签读取逻辑。</summary>
    protected abstract Task<object?> ReadTagCoreAsync(TagDefinition tag, CancellationToken ct);

    /// <summary>子类实现：协议特定的单标签写入逻辑。</summary>
    protected abstract Task<bool> WriteTagCoreAsync(TagDefinition tag, object value, CancellationToken ct);

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        try
        {
            await DisconnectAsync().ConfigureAwait(false);
        }
        catch
        {
            /* ignore */
        }
        await DisposeCoreAsync().ConfigureAwait(false);
        GC.SuppressFinalize(this);
    }

    /// <summary>子类可重写以释放非托管资源。</summary>
    protected virtual ValueTask DisposeCoreAsync() => ValueTask.CompletedTask;
}
