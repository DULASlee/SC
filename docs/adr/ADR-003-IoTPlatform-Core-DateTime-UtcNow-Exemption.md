# ADR-003: IoTPlatform.Core 抽象层 DateTime.UtcNow 豁免 BannedSymbols

## 状态
待批准（L2-A 期间草拟；需架构师签字）

## 背景
L2-A 阶段 BannedSymbols.txt 禁止 `DateTime.UtcNow`，要求 IClock 注入。
但 `source/IoTPlatform/src/IoTPlatform.Core` 是**抽象基类 / 数据模型层**（`ICollector`、`TagDefinition`）：
- `TagReadResult.Timestamp` 默认初始化为 `DateTime.UtcNow`（属性默认值）
- `ICollector.StatusChanged` / `SampleCollected` / `Error` 事件参数 `Timestamp` 初始化为 `DateTime.UtcNow`

引入 IClock 需要：
1. 在 `IoTPlatform.Core.Abstractions` 新增 `IClock` 接口
2. 在所有 `BaseCollector` / `BaseAdapter` 注入 IClock
3. 改 4 处属性默认值为 `IClock.UtcNow`（但属性默认值不能用方法调用）
4. 修改所有 Consumer（GenCollector 4 处 + IoTPlatform.Host 2 处）

这是 **Core 抽象层的契约变更**，不是 L2-A "建立编译门禁" 的范围。

## 决策
1. 暂允许 `IoTPlatform.Core` 层豁免 `DateTime.UtcNow`，方法级 `[SuppressMessage]` 精确包裹每个属性初始化。
2. 不变更现有 API。
3. L2-A 完成后，由 L2-B 任务（架构测试 / 覆盖率差分）前先开 IClock 注入的 ADR-004 跟进。

## 后果
- 4 处 SuppressMessage 必须显式标注 ADR-003 引用。
- CI 仍需保证 IoTPlatform.Core 之外的工程没有 `DateTime.UtcNow` 违规。

## 关联
- ADR-001：CollectorEngine.RunDevice（Thread.Sleep）
- ADR-002：Program.Main（Thread.Sleep）
- ADR-003（本）：IoTPlatform.Core 抽象层（DateTime.UtcNow）
