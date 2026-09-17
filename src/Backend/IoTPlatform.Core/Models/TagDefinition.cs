using System;
using System.Diagnostics.CodeAnalysis;

namespace IoTPlatform.Core.Models;

/// <summary>
/// 标签（数据点）定义。
/// </summary>
/// <remarks>
/// 设计参考原始 Collector 中的硬编码采集点：
///   - LnkCollector: CNC 宏变量 33868/2097/33565/33869 + PLC 寄存器 42.0/42.1/50.14
///   - HanBaCollector: HttpMem 寄存器 R0577/R0974/R1929/R1928/R1443/R1442
/// </remarks>
public sealed class TagDefinition
{
    /// <summary>逻辑名称（如 "WorkTime", "RunStatus", "YXMS"）。</summary>
    public required string Name { get; init; }

    /// <summary>数据类型。</summary>
    public required TagType Type { get; init; }

    /// <summary>
    /// 协议地址。
    /// Fanuc CNC: "33868" (宏变量) 或 "D100" (数据寄存器)
    /// HttpMem: "R0577"
    /// Mitsubishi: "D100", "M100", "B100"
    /// </summary>
    public required string Address { get; init; }

    /// <summary>UI 显示名（中文/英文）。</summary>
    public string? DisplayName { get; init; }

    /// <summary>单位（如 "ms", "mm", "A"）。</summary>
    public string? Unit { get; init; }

    /// <summary>小数位数（用于显示）。</summary>
    public int Decimals { get; init; }

    /// <summary>是否启用（false 时跳过采集）。</summary>
    public bool Enabled { get; init; } = true;

    public override string ToString() => $"{Name} ({Type}@{Address})";
}

/// <summary>标签数据类型。</summary>
public enum TagType
{
    /// <summary>CNC 宏变量（双精度浮点）。</summary>
    CNCMacro,
    /// <summary>PLC 位寄存器（bool）。</summary>
    PLCBit,
    /// <summary>PLC 字寄存器（short/long）。</summary>
    PLCWord,
    /// <summary>PLC 浮点寄存器（float/double）。</summary>
    PLCFloat,
    /// <summary>HttpMem 寄存器（int/double）。</summary>
    HttpMemRegister,
    /// <summary>字符串。</summary>
    String,
    /// <summary>布尔。</summary>
    Boolean,
    /// <summary>整数。</summary>
    Integer,
    /// <summary>浮点数。</summary>
    Double
}

/// <summary>
/// 单个标签的读取结果。
/// </summary>
[SuppressMessage("Usage", "RS0030:Do not use banned DateTime.UtcNow", Justification = "ADR-003: Core abstraction layer; IClock injection is a separate follow-up task. See docs/adr/ADR-003-IoTPlatform-Core-DateTime-UtcNow-Exemption.md.")]
public sealed class TagReadResult
{
    /// <summary>标签定义（对应采集的哪个标签）。</summary>
    public required TagDefinition Tag { get; init; }

    /// <summary>读取是否成功。</summary>
    public bool IsSuccess { get; init; }

    /// <summary>读取值（失败时为 null）。</summary>
    public object? Value { get; init; }

    /// <summary>采集时间戳（UTC）。</summary>
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;

    /// <summary>采集耗时。</summary>
    public TimeSpan Elapsed { get; init; }

    /// <summary>错误信息（成功时为 null）。</summary>
    public string? Error { get; init; }

    public static TagReadResult Success(TagDefinition tag, object? value, TimeSpan elapsed)
        => new() { Tag = tag, IsSuccess = true, Value = value, Elapsed = elapsed };

    public static TagReadResult Failure(TagDefinition tag, string error, TimeSpan elapsed)
        => new() { Tag = tag, IsSuccess = false, Error = error, Elapsed = elapsed };
}
