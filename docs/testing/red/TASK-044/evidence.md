# TASK-044 证据链（v1.1 §12 + A2 设计定案落地）

## 红（对 HEAD=043-tip 抽取版探测，真实可复现）
- red-01：build_session_override / assemble_executor_argv 在 HEAD 均不存在；
  HEAD 的 spawn 仍走 swap_for_run 全局写入路径。
- red-02：铁律 15 门的真实拦截——改后 `dispatch --dry-run` 被 canary 门整轮拒绝
  （"canary_required：先跑 canary.py 留证"），证明执行器链路变更必须留证、无逃生口。
  本轮未跑 canary 真探针：当前 dispatch.yaml 的默认模型免费档已上游 404
  （评审报告 R1c），真探针与双模型 V4 在线复测**待架构师定模型行后执行**。
- red-03：旧 argv 组装式（a.replace("{prompt}")）会把 --patch 令牌整段丢弃——
  即使覆盖件存在也是死信；新 assemble 注入位序正确（--patch 在 prompt 位置参数前）。

## 绿
- 全量：Ran 175 tests OK（169→175，+6：副本保键/基线零写/patch 文本/A B 双会话
  隔离 与 argv 组装三态）。旧测试零删改。
- 单元级 V4：两会话各建副本（model-a/model-b 互不可见），基线 SHA256 不变——
  在线版（真双 dsh 并发 + 会话产物模型断言）挂 TASK-046 场景。

## 退役边界（诚实记录）
- 派发路径不再写全局：dispatch spawn 与 pipeline 非执行阶段全部改走
  build_session_override + --patch 注入；_model_aligned"模型未对齐"与
  "同轮同模型"降级删除；poll.main 不再调用收尾恢复。
- 旧链（swap_for_run/restore/acquire_lock/release_lock/maybe_restore/snapshot/
  verify_selection 及 poll.finalize_model_restore 定义）**保留为死代码**：
  它们被已入库的 test_gates.py 断言覆盖，而 test_gates.py 不在本卡 allow_write
  （物理删除会越权改测试，铁律 4/13 双重红线）。→ FOLLOW-UP：
  单独一张"退役清理卡"（allow 含 modelswap/poll/test_gates 三件），
  或并入 TASK-046 完工后整理。运行时安全目标（不再写共享态）本卡已达成。
- pipeline 非执行阶段旧行为=不覆盖（跟随全局现状，与 dispatch 不一致的缺陷
  ——P0 补漏 3）本次一并修复：两路径同机制。
- 铁律 15：executor 命令构造方式已变（assemble 注入）→ 合并后首次 dispatch
  前必须跑 canary 真探针留证（前置=模型行定案）。
