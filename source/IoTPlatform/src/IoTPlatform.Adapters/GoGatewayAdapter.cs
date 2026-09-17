using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using IoTPlatform.Core.Base;
using IoTPlatform.Core.Models;

namespace IoTPlatform.Adapters;

/// <summary>
/// Go 主网关 HTTP API 客户端适配器：调用 iot_CNC_PLC_IMM 重写后的 HTTP 服务。
/// </summary>
/// <remarks>
/// 反编译注释显示 iot_CNC_PLC_IMM 使用 echo 框架，handler 在 elinks/* 命名空间下。
/// 重建后的 Go 服务预期暴露 RESTful API：
///   GET  /api/version
///   GET  /api/menu
///   GET  /api/protocol/{name}?address=...
///   POST /api/command/{name}
///
/// 本适配器作为协议适配器的"客户端形态"使用：从 .NET 端调用 Go 重写后的 HTTP 服务。
///
/// 注：此适配器暂作为 HTTP 客户端实现，待 Go 主网关源码重建（C9）完成后，
///     通过调试验证 endpoint 路径与 JSON 结构。
/// </remarks>
public sealed class GoGatewayAdapter : BaseAdapter
{
    public override string ProtocolName => "GoGateway";
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(3) };
    private string _baseUrl = "";

    protected override async Task<bool> ConnectCoreAsync(DeviceConnectionConfig config, CancellationToken ct)
    {
        _baseUrl = $"http://{config.Endpoint}:{config.Port}";
        try
        {
            // 探测：调 /api/version
            var resp = await _http.GetAsync($"{_baseUrl}/api/version", ct).ConfigureAwait(false);
            return resp.IsSuccessStatusCode;
        }
        catch { return false; }
    }

    protected override Task DisconnectCoreAsync(CancellationToken ct) => Task.CompletedTask;

    protected override async Task<object?> ReadTagCoreAsync(TagDefinition tag, CancellationToken ct)
    {
        var url = $"{_baseUrl}/api/protocol/{tag.Type}?address={Uri.EscapeDataString(tag.Address)}";
        try
        {
            var resp = await _http.GetFromJsonAsync<GoValueResponse>(url, ct).ConfigureAwait(false);
            return resp?.Value;
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"GoGateway read {tag.Address} failed: {ex.Message}");
        }
    }

    protected override async Task<bool> WriteTagCoreAsync(TagDefinition tag, object value, CancellationToken ct)
    {
        var url = $"{_baseUrl}/api/protocol/{tag.Type}/{tag.Address}";
        try
        {
            var resp = await _http.PostAsJsonAsync(url, new { value }, ct).ConfigureAwait(false);
            return resp.IsSuccessStatusCode;
        }
        catch { return false; }
    }

    protected override ValueTask DisposeCoreAsync()
    {
        _http.Dispose();
        return ValueTask.CompletedTask;
    }

    /// <summary>Go HTTP API 响应包装。</summary>
    private sealed class GoValueResponse
    {
        [JsonPropertyName("value")]
        public object? Value { get; set; }

        [JsonPropertyName("error")]
        public string? Error { get; set; }
    }
}
