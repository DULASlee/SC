# ADR-007：全局运行时协调采用仓库级共享权威（D-Parallel-002）

- 状态：已接受
- 日期：2026-09-21
- 关联：v1.1 §10/§11；评审报告 A5/B5

## 背景
多会话并行需要全局账本、额度与跨进程锁。候选协调根：仓库级 / 仓库元数据 /
用户级 runtime root。用户级曾因其"天然跨 worktree"被纳入考虑。

## 决策
**Global runtime coordination uses repository-level shared authority.**
协调根 = 仓库级 .harness/runs/（coord.lock / RUNS+PIPELINE / ownership/），
不新建存储产品、不引入第三方协调设施；锁沿用 modelswap/loop 两处已在
Windows 实战的 mkdir+pid+600s-stale 模式泛化（coord.py）。

## 后果
- 显式排除用户级根：任务 ID 跨仓冲突、锁与被保护对象层级错配（旧
  modelswap 锁在仓库级却保护用户级文件即反例）。
- Windows 并发 append 无逐行原子保证 → 锁覆盖账本全部写路径（含 append）。
- 串行"崩了重跑即可续"约定升级为机制化互斥；serial 从正确性前提降级为性能惯例。
