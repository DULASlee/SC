# Lessons Learned — GenCollector Harness

<!--
  格式：[来源] 场景 → 教训
  规则：每条不超过 2 行；场景必须具体到可识别触发条件；纯抽象道理无效
  维护：每个任务卡 done 时至少提炼 1 条；每周整理去重
-->

- [TASK-003] Windows Python subprocess 默认 GBK 编码 → 必须显式指定 `encoding='utf-8'`，否则 silent-pass 且门禁失效
- [TASK-003] AI 执行者用空格规避机制自检（TASK 004 vs TASK-004）→ 机制应支持 done 状态卡免检，而非靠 hack 绕过
- [TASK-004/005/006] 事后补卡不能成为常规流程 → 必须先开 PR 经架构师审核，一次性豁免需记录在 governance.md
- [TASK-004/005/006] git commit-tree 在 unborn 状态下构造测试 commit → 会损坏本地 git 历史，禁止用此方式做脚本自测
- [TASK-004/005/006] 架构师指令内部矛盾（"立即 pull" vs "先看 diff"）→ 执行者发现矛盾时应停下来报告，这是正确行为
- [TASK-004/005/006] emoji 在 PowerShell GBK 下抛 UnicodeEncodeError → hook 脚本输出只用 ASCII（[OK]/[FAIL]/[WARN]）
- [PR 4] 施工包中 done_when 写了非法 gate 格式 → 施工包作者必须先用 validate-task-card 校验自己写的卡模板
- [PR 4] 红态证据校验脚本未处理"卡为 done 状态"的跳过逻辑 → 校验脚本必须读取卡状态，done 卡不触发红态检查
- [origin sync] 本地 main 与 origin 出现分叉前未检查 diff → 执行 `git pull` 前必须先 `git fetch` + 查看 diff stat
- [harness] 任务卡 allow_write 路径写 `src/**` 通配符 → 必须用具体路径，防止执行者越权修改

<!-- 新增经验追加在上方，格式保持一致 -->
