using System;
using System.Collections.Generic;

namespace IoTPlatform.Core.Models;

/// <summary>
/// 一次完整采集周期的数据（包含多个标签读数 + 设备元信息）。
/// </summary>
/// <remarks>
/// 数据序列化格式（JSON）：
/// <code>
/// {
///   "deviceId": "CNC04",
///   "timestamp": 1726588800000,
///   "values": {
///     "WorkTime": 12345.6,
///     "RunTime": 67890.1,
///     "RunStatus": 1
///   },
///   "errors": {
///     "WarnStatus": "Timeout after 3000ms"
///   }
/// }
/// </code>
/// </remarks>
public sealed class SampleData
{
    /// <summary>设备标识。</summary>
    public required string DeviceId { get; init; }

    /// <summary>采样时间戳（UTC 毫秒）。</summary>
    public required long Timestamp { get; init; }

    /// <summary>采样耗时（毫秒）。</summary>
    public double ElapsedMs { get; init; }

    /// <summary>成功的标签值（key = TagDefinition.Name）。</summary>
    public Dictionary<string, object?> Values { get; init; } = new();

    /// <summary>失败的标签错误（key = TagDefinition.Name, value = error message）。</summary>
    public Dictionary<string, string> Errors { get; init; } = new();

    /// <summary>从 TagReadResult 列表构造 SampleData。</summary>
    public static SampleData FromResults(string deviceId, IReadOnlyList<TagReadResult> results, TimeSpan elapsed)
    {
        var data = new SampleData
        {
            DeviceId = deviceId,
            Timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            ElapsedMs = elapsed.TotalMilliseconds
        };
        foreach (var r in results)
        {
            if (r.IsSuccess)
            {
                data.Values[r.Tag.Name] = r.Value;
            }
            else
            {
                data.Errors[r.Tag.Name] = r.Error ?? "Unknown";
            }
        }
        return data;
    }
}
