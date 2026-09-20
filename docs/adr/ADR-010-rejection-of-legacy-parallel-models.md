# ADR-010：废止旧并行模型与单会话规则（Explicit Rejection + B3）

- 状态：已接受
- 日期：2026-09-21
- 关联：v1.1 §18；lessons [parallel-sessions]/[TASK-013]

## 背景
本仓此前以"同一时间只允许一个 AI 会话操作仓库"规则 + "同一时刻只跑
dispatch 或 poll 之一"约定维持正确性；TASK-013 并行会话污染事故证明
约定不可靠。并行安全工程落地后，这些规则必须显式作废，否则新旧并存
造成执行者矛盾。

## 决策
显式废止下列模型与规则：
1. 每 Worktree 一份并发账本（含把分支快照卡当协调依据）；
2. 每 Worktree 一把模型锁；
3. 通过修改全局配置实现模型切换（含监视器热发布语义）；
4. 各 Worktree 各自判断 Task authorization；
5. 用户级 runtime root 作为协调根；
6. attempt 粒度的 ownership（重试链必须按 Task 粒度）；
7. 规则"同一时间只允许一个 AI 会话操作仓库"（lessons-learned
   [parallel-sessions] 条目）——自本 ADR 起由 L0/L1/L2 机制替代，
   原条目保留并标注 superseded（本仓先例见该文件 55/61 行）。

## 后果
- 替代物：coord 锁 + ownership 单源 + 会话覆盖 + 提交归属门禁
  （substrate 验证 11/11 PASS，docs/testing/red/PARALLEL-SAFETY/）。
- "串行即正确"降级为性能建议；live 全链路关闭条件见完工报告 PENDING 节。
