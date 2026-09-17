# ADR-004: LnkCollector_src 反编译对照源全文件 BannedSymbols 豁免

## 状态
待批准（L2-A 期间草拟；需架构师签字）

## 背景
`LnkCollector_src/` 是 **netcoreapp3.1 反编译对照源**（见 `docs/superpowers/plans/2026-09-17-industrial-platform-phase0.md`）。
其源码是从 `CNC04/LnkCollector.dll` 反编译得到的，目标是为新工程（GenCollector）提供语义参考。

反编译代码包含 9 处 `Thread.Sleep(1000)` 用于 1 秒间隔轮询（原始是同步 P/Invoke 调用的节奏控制）。
**反编译代码不应该被门禁控制**——它的目的是展示原二进制怎么写，不是供未来使用。

## 决策
1. 通过 `Directory.Build.props` 的 MSBuild 条件 `Condition="$(MSBuildProjectName.Contains('LnkCollector'))"` 单独豁免 LnkCollector_src 工程的 BannedSymbols。
2. 不修改 LnkCollector_src 源码。

## 后果
- LnkCollector_src.csproj 不需要引入 BannedApiAnalyzers 包（条件跳过）。
- LnkCollector_src 仍可通过 .editorconfig 的 UTF-8 等其他 L0 约束。
- 未来 L2-B / L2-C 仍可在此工程跑测试，但 BannedSymbols 检查跳过。

## 关联
- ADR-001：CollectorEngine.RunDevice
- ADR-002：Program.Main
- ADR-003：IoTPlatform.Core 抽象层
- ADR-004（本）：LnkCollector_src 反编译对照源
