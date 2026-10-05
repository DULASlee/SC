# TASK-047 证据（退役清理：044 [retire-scope] 挂账兑现）

## 转换前状态（红锚面）
- HEAD 版 modelswap 仍含 swap_for_run/restore/acquire_lock/maybe_restore/
  snapshot/verify_selection/read_selection；poll 仍含 finalize_model_restore
  且 main 保留收尾死调用（044 revert 后未再摘，grep 实证）。
- test_gates/test_modelswap 存在断言旧链的用例类（TestSwapRestore/TestLock/
  TestMaybeRestore/TestSnapshotVerify/TestFinalizeVerify）。

## 铁律 4 四要件（测试转换非删除）
①原因：API 依 ADR-008/010 废止，保留断言=为死代码供血；
②影响：被删断言的行为（"全局会被改写"）已不存在，新契约=全局零写入；
③替代：更强覆盖——缺席守卫（复活即红）×3 文件 + builder 隔离用例
（基线 SHA256 不变断言）+ 源码级零引用断言；
④人类确认：架构师授权链（对话 2026-09-21 临时全权+立即推进），
本卡 approver 字段为载体，验收时逐卡追认。

## 结果
- 176 tests OK（185→176：删除的是对已不存在行为的 13 个旧断言用例，
  新增 4 组守卫/覆盖用例；净语义覆盖增强）。
- 全仓 grep：退役 API 在 scripts/hooks/tests 无任何 live 引用
  （仅存于守卫断言字符串、注释与历史文档——白名单核过）。
- README 模型路由真相/运行约定/非目标/管线账本互通四处按现行机制重写
  （消除"文档断言与实现脱节"病灶两例：串行前提、槽位互通）。
- loop.py 注释引用修正（历史来源标注）。
