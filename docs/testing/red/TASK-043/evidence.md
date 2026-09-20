# TASK-043 证据链（v1.1 §10/§11 + A1/A5/B1/B5）

## 红（对 HEAD 版实现调用本卡新 API，真实复现）
- red-01-head-api-absence.txt：对 `git show HEAD:` 抽取的改动前脚本执行探测——
  capacity_used / list_active / RunsStore(lock_dir=) / coord.py 全部不存在
  （5/5 RED-CONFIRMED），证伪"改动前已有跨账本保护"的可能。
  复现脚本逻辑：临时目录抽取 HEAD 版 scripts → import → 探测新 API。
- 既有实现缺陷（改动前状态，代码级证据）：
  1) running_count 注释宣称"含 pipeline"，实际只读 RUNS.jsonl 单文件——
     PIPELINE.jsonl 活动记录零占额（README"槽位互通"为文档断言，实现脱节）；
  2) 计数只数 running，不数在途 spawning（落盘后未回填 pid 的窗口可超发）；
  3) 账本写路径无跨进程互斥（Windows 并发 append 可交织）；
  4) spawning 崩溃滞留无回收通道（poll 只遍历 running）。

## 绿（实现后）
- test_coord.py 13/13：锁原语（获取/释放/重入/跨线程/跨进程/600s stale 恢复/
  is_held/touch 心跳）+ 双账本容量合计 + spawning 计入额度 + 并发 append 不丢行 +
  gc_stale_spawned 回收 + gc_worktrees 保守回收（脏目录/未知目录/活跃任务均不动，
  分支不删）。
- 全量回归：Ran 169 tests OK（基线 156 → 169，含本卡 +13；147 旧基线零回归）。

## 实现落点
- coord.py（新）：跨进程可重入 mkdir 锁（复用 modelswap/loop 实战模式，不引新基建）。
- runs.py：RunsStore 可选 lock_dir（写自保护+持锁心跳），critical_section 复合块，
  list_active（running+spawning）。
- dispatch.py：逐卡 容量复核→卡态复核→占坑→派发 单临界区（§5.2 消除
  check-then-act）；capacity_used 跨双账本；争锁超时=顺延不崩轮。
- poll.py：回收判定+复位重派整段临界区；GC：stale spawning 记 error 释放额度、
  清洁 worktree 回收（B1）。
- pipeline.py：账本接入同一协调锁。
- 锁层级：coord.lock（账本临界区）≠ loop.lock（单实例）≠ modelswap.lock（P4 退役）。
  持锁段实测秒级（claim 含 git 提交，touch 心跳兜底），远低于 600s stale。

## 边界自证（v1.1 §15/§16 总闸门）
未动：model routing（modelswap 函数零改动）、卡状态权威模型、Hook 其余部分、
任务系统语义（done 仍只来自人类验收）。serial 约定从"正确性前提"降级为"性能惯例"。
