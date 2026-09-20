using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Adapters;

/// <summary>
/// HttpMem 协议适配器：实现 HttpMemAPI.dll 的 HttpGDEGetBit 等接口。
/// </summary>
/// <remarks>
/// 原 HttpMemAPI.dll 是 VS2008 MFC + Poco 实现的 HTTP 客户端库，
/// 调用方（HanBaCollector）通过 P/Invoke 使用 HttpGDEGetBit 读寄存器。
/// 本实现用 .NET HttpClient 重写，行为与原 API 等价：
///   - GET http://{ip}:{port}/api/get?reg=R0577  → 返回 int dwVal
/// 注：原 HttpMemAPI 协议细节需要 Wireshark 抓包确认，
///     当前实现基于反编译函数名推断。
/// </remarks>
public sealed class HttpMemAdapter : BaseAdapter
{
    public override string ProtocolName => "HttpMem";
    public bool MockMode { get; init; } = true;

    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(3) };

    protected override async Task<bool> ConnectCoreAsync(DeviceConnectionConfig config, CancellationToken ct)
    {
        if (MockMode) return true;
        try
        {
            using var probe = new HttpRequestMessage(HttpMethod.Get,
                $"http://{config.Endpoint}:{config.Port}/api/status");
            using var resp = await _http.SendAsync(probe, ct).ConfigureAwait(false);
            return resp.IsSuccessStatusCode;
        }
        catch { return false; }
    }

    protected override Task DisconnectCoreAsync(CancellationToken ct) => Task.CompletedTask;

    protected override async Task<object?> ReadTagCoreAsync(TagDefinition tag, CancellationToken ct)
    {
        if (MockMode)
        {
            await Task.Delay(50, ct).ConfigureAwait(false);
            return Random.Shared.Next(0, 1000);
        }
        if (CurrentConfig is null) throw new InvalidOperationException("Not connected");
        var url = $"http://{CurrentConfig.Endpoint}:{CurrentConfig.Port}/api/get?reg={tag.Address}";
        using var req = new HttpRequestMessage(HttpMethod.Get, url);
        using var resp = await _http.SendAsync(req, ct).ConfigureAwait(false);
        resp.EnsureSuccessStatusCode();
        var body = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
        if (body.Contains("\"value\""))
        {
            using var doc = System.Text.Json.JsonDocument.Parse(body);
            var v = doc.RootElement.GetProperty("value");
            return v.ValueKind switch
            {
                System.Text.Json.JsonValueKind.Number => v.TryGetInt32(out var i) ? i : v.GetDouble(),
                System.Text.Json.JsonValueKind.String => v.GetString(),
                System.Text.Json.JsonValueKind.True => true,
                System.Text.Json.JsonValueKind.False => false,
                _ => v.ToString()
            };
        }
        return int.TryParse(body, out var n) ? n : body.Trim();
    }

    protected override async Task<bool> WriteTagCoreAsync(TagDefinition tag, object value, CancellationToken ct)
    {
        if (MockMode) return true;
        if (CurrentConfig is null) return false;
        var url = $"http://{CurrentConfig.Endpoint}:{CurrentConfig.Port}/api/set?reg={tag.Address}&value={Uri.EscapeDataString(value?.ToString() ?? "")}";
        using var req = new HttpRequestMessage(HttpMethod.Post, url);
        using var resp = await _http.SendAsync(req, ct).ConfigureAwait(false);
        return resp.IsSuccessStatusCode;
    }

    protected override ValueTask DisposeCoreAsync()
    {
        _http.Dispose();
        return ValueTask.CompletedTask;
    }
}
