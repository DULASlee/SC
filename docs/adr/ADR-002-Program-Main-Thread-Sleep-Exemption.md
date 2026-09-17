# ADR-002: Program.Main 同步入口豁免 BannedSymbols

## 状态
已接受

## 背景
L2-A 阶段 `BannedSymbols.txt` 禁止 `Thread.Sleep(int)`，包括 `Thread.Sleep(Timeout.Infinite)`。
`GenCollector/Program.cs:55` 用 `Thread.Sleep(Timeout.Infinite)` 等待 Ctrl+C——这是 `static void Main` 同步入口的标准阻塞模式。

## 决策
1. 维持 `static void Main` 签名（不改 async Task Main，避免牵动 Main 启动路径）。
2. 允许 `Program.cs` 方法级 `[SuppressMessage]` 豁免 `Thread.Sleep(Timeout.Infinite)`。
3. 豁免必须严格限定在 `Program.Main` 方法（不让整个文件豁免）。
4. 未来如引入 hosted service（如 Generic Host）切换为 async Main，可重新评估此豁免。

## 后果
- `Program.cs` 必须显式标记豁免。
- CI 仍需保证其他所有 .cs 文件没有违反 BannedSymbols。
- 与 ADR-001 互不冲突（不同文件、不同方法、不同理由）。

## 关联
- ADR-001：CollectorEngine.RunDevice（硬件线程亲和性）
- ADR-002：Program.Main（同步入口）
