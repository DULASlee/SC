# PILOT 单卡试点 Checklist（B′）

> 不进 git（本地勾选卡）。试点卡：**TASK-010**（scope 最小：4 个文档文件；单 gate：contract_consistency）。
> 冻结卡：TASK-008/009 attempt-3 已记 error 暂冻（RUNS.jsonl + RESET-008-009-010.md）。

- [ ] 1. 签名账已清：008/009/010 `sig_history` 全空（`RUNS.jsonl.bak.*` 有备份）
- [ ] 2. concurrency 已降为 1（dispatch.yaml）
- [ ] 3. 运行 `python .harness/scripts/poll.py`，确认只收 010 attempt-3（008/009 被 SKIP）
- [ ] 4. 四项活体验收：
  - [ ] 4a. RUNS.jsonl 出现非 -1 真实 exit code + 真实耗时
  - [ ] 4b. 记录 `model` 字段 == dispatch.yaml 的 model（R-模型坐实）
  - [ ] 4c. worktree `feat/TASK-010` 真建分支（跑完按流程清理）
  - [ ] 4d. gate 因测试结果开合，而非执行挂掉短路
- [ ] 5. 010 绿 → 解冻 008/009（attempt-3 记录改回 running 由 poll 自然回收）→ 全绿 → concurrency 回 3
- [ ] 6. DSH 默认模型被 swap 期间如有手动使用，注意它会短暂切走并恢复（modelswap 行为）
