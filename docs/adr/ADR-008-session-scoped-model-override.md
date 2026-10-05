# ADR-008：模型选择会话化，不写共享基线（D-Parallel-003 + D-Parallel-005）

- 状态：已接受
- 日期：2026-09-21
- 关联：v1.1 §6/§12；评审报告 §7（双探针实证）；ADR-007

## 背景
旧派发路径"持锁→备份→改写用户级 ~/.dsh/settings.yaml→跑→恢复"：
共享写入跨仓库、跨手工会话生效，且该文件默认带监视器（改写热发布到
运行中会话）；派发器被迫"同轮同模型"降级并自认存在跨轮竞态窗口。

## 决策
**Model selection is session-scoped and does not mutate the shared baseline.**
每 attempt 生成私有设置副本（基线只读 + 替换 agent-default-model +
保留其余命名空间），spawn 经 `dsh --patch` 把组合树 settings 条目
重定向到该副本（config.path 显式优先、watch:false 关热发布）。
值优先级（文件层>组合层）与副本消费行为由真实 headless 探针正反两例实证。

## 后果
- 全局配置写入路径从派发/管线两路径消失；锁/备份/恢复链退役。
- "同轮同模型"与"模型未对齐 fail-fast"降级作废，多模型可同轮并行。
- 探针顺带发现派发默认模型免费档已上游 404（R1c），模型行定案为
  live 验证（Gate C 在线面/canary）前置，登记于完工报告。
