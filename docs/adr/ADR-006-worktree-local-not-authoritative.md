# ADR-006：Worktree 本地状态对全局协调无权威（D-Parallel-001）

- 状态：已接受
- 日期：2026-09-21
- 关联：docs/superpowers/plans/2026-09-20-parallel-session-isolation-plan-v1.1.md §4/§10；评审报告 A1/A5

## 背景
并行会话改造评审中确认：运行账本集中于主树 .harness/runs/（双账本 RUNS/PIPELINE），
但 worktree 内的钩子按 `--show-toplevel`/`__file__` 解析任务卡，读到的是分支快照，
与主树实时状态实测分叉（12 vs 21）。若各 worktree 的本地副本参与协调判定，
等于多个事实源。

## 决策
**Worktree-local state is not authoritative for global coordination.**
所有全局协调读取一律经 `git rev-parse --git-common-dir` 锚点回到主树
（coordination root = 仓库级 .harness/runs/）；worktree 本地日志仅作诊断副本。

## 后果
- ownership 引擎、提交钩子、verify-parallel 全部以主树为唯一读取面（V8 实证）。
- 旧分支 worktree 缺新脚本时钩子 fail-closed（防旁路，符合预期）。
- "钩子读分支快照卡"缺陷（P0 映射缺陷 B/C）随本决策关闭。
