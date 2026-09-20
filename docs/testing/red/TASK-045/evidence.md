# TASK-045 证据链（v1.1 §7/§13 + A3 三硬语义）

## 红（对 HEAD=044-tip 探测，真实可复现）
red-01：ownership.py 不存在 / dispatch 无 claim / poll 无 release /
钩子读的是 sessions/（双事实源前身）——四项全 RED-CONFIRMED。

## 绿
- 全量 185 tests OK（044 基线 175 → +10：ownership 9 用例 + 钩子 7 重写用例，
  start_session 5 改判用例，净增 10）。
- V6 语义单元面：`claim 冲突=拒绝且原记录字节不变`（never-clobbers）、
  异 worktree 有主不泄漏（V5）、释放后再领（A3-3）、
  同 session 幂等重 claim（A3-2 重试链）、无主 assert_writer 拒绝（仅 Owner 写）。

## 单一事实源整合
- 042 的 sessions/ 登记簿被 ownership/ 吸收（同一映射不得两处存，§7.1）；
  钩子、start-session、dispatch、poll、pipeline 全部读写同一 <runs>/ownership/。
- claim 序照 §13：持锁→读卡→验无主→写卡→commit→记 ownership；
  失败路径逐级回滚（commit 失败→release；spawn 失败→回卡+force_release）。
- 终态释放点：poll 7 处（pass/blocked×4/upstream×2）+ pipeline advance 包装
  （blocked/done）。error 态保留 claim（留给排障定主，人工复位后再释放）。
- 遗留 in-progress 且无主的历史卡：start-session 明确拒绝接管（防旁路），
  要求人工释放/复位——迁移期策略，写入提示语。

## 边界自证
未动：卡状态权威模型（done 仍只来自人类验收）、model routing、账本结构。
coord.py 零改动（复用 043 临界区）。卡片 allow 补列两份 042 测试迁移文件
（起草缺口，透明记录于提交信息）。
