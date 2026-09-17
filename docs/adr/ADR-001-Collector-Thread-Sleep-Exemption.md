# ADR-001: CollectorEngine 同步轮询主循环豁免 BannedSymbols

## 状态
已接受

## 背景
L2-A 阶段引入了 `BannedSymbols.txt` 分析器，禁止使用 `Thread.Sleep`，以推广 `Task.Delay`。
但在 `GenCollector/Core/CollectorEngine.cs:94` 中，`RunDevice` 是一个同步包装的硬件轮询主循环。
该线程具有特定的硬件/COM 线程亲和性要求（RemoteComm.dll P/Invoke 调用），若贸然改为 `async Task.Delay`，会牵动启动/停止路径，极易导致并发竞态或非托管 DLL 死锁。

## 决策
1. 仅修改 `Program.cs` 中无关的 `Thread.Sleep` 调用（无限阻塞等待 Ctrl+C → `Task.Delay(Timeout.Infinite)`，语义等价）。
2. 对于 `CollectorEngine.RunDevice` 中的 `Thread.Sleep(500)`，允许豁免 BannedSymbols。
3. 豁免必须严格限定在 `CollectorEngine.cs` 文件级（用方法级 `[SuppressMessage]` 精确包裹 `RunDevice`），不得全局关闭该规则。
4. 在未来进行硬件层重构（如引入专用定时器 `System.Threading.PeriodicTimer` 或 `CancellationTokenSource.CancelAfter`）时，需重新评估此豁免。

## 后果
- 该文件必须显式标记豁免，并注明原因（本 ADR）。
- CI 仍需保证其他所有项目/文件没有违反 BannedSymbols。
- `BannedSymbols.txt` 注释更新为包含 ADR 引用。
- L1-α 报告 + L2-A 报告均需引用此 ADR。

## 关联
- `Directory.Build.props`（L2-A 引入 BannedApiAnalyzers）
- `BannedSymbols.txt`（L2-A 严格按架构师指令）
- `GenCollector/Core/CollectorEngine.cs` RunDevice 方法（实际豁免点）
