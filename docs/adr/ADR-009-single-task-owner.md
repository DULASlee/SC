# ADR-009：任务状态单主单源（D-Parallel-004 + A3 三硬语义）

- 状态：已接受
- 日期：2026-09-21
- 关联：v1.1 §7/§13；评审报告 A3

## 背景
旧机制无显式 ownership：独占性靠"占坑改卡状态 + 单派发器"隐式保证，
并行出现即失效；且 claim 的"读→改→提交"存在 TOCTOU（git index.lock
只防同时写、不防先后读旧值）。

## 决策
**Task state has a single owner and a single authoritative state source.**
ownership 落 <runs>/ownership/<TASK>.json（吸收 TASK-042 sessions 登记簿，
不留双源）。权限：claim 仅当无主；写状态/释放仅 owner；读人人可；
执行仅 owner（提交钩子按 worktree 反查绑定）。冲突=拒绝，非 warning。
三条硬语义：①键=TaskId（非 attempt）②重试链合法复用同 worktree/同
session（幂等）③OwnerSession 更替仅发生在任务释放（blocked/
awaiting-review/done）后。

## 后果
- claim/释放全程在 coord 临界区内；dispatch/poll/pipeline/手工 CLI 四入口同构。
- 遗留 in-progress 无主卡拒绝旁路接管，迁移期要求人工释放/复位。
- done 唯一来源不变（人类 verify-all + archive），判定权零让渡延续。
