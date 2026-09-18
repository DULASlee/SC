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
- [TASK-008] 架构师豁免授权未用 hook 认可的语法（[APPROVED-BY:] 标记）→ 豁免必须同时满足：①口头/文本明确授权 ②commit message 含 `[APPROVED-BY: <name>]`。架构师签发豁免时应直接提供完整 merge 命令含标记
- [hook-design] commit-msg hook 的 protected-paths 检查与铁律豁免是两层独立机制 → 铁律豁免不等于 hook 豁免，两者需分别满足。未来考虑：hook 识别"一次性豁免"关键词自动放行，或架构师设 SKIP_PROTECTED_CHECK=1
- [parallel-sessions] 同一仓库开两个并行 AI 会话 → 分支状态不可预测、文件冲突风险。规则：同一时间只允许一个 AI 会话操作仓库
- [TASK-009/010] 施工包 Phase H 期望"无 WARN"是错配 → 文件迁移（git mv）不等于全局引用更新。迁移后 grep 必然发现历史文档中的旧路径引用，这是预期行为而非缺陷。施工包应区分"迁移完整性检查"和"引用一致性检查"，后者单独开卡
- [TASK-009/010] 历史任务卡（TASK-008.yaml）引用旧路径 → 任务卡是历史工件，不应为迁移而篡改。正确做法：保留原引用 + 加注释说明路径已变更
- [TASK-013] 并行会话在 feature 分支上留下未授权 commit → 即使内容"看起来有用"也必须 revert/reset。混入未授权提交会污染任务卡的 scope 边界，且可能复活已删除文件。检测手段：`git log` 发现非本会话 commit → 立即暂停
- [TASK-013] `git stash` + `git reset --hard` + `git stash pop` 是清理污染分支的标准操作。feature 分支的 force push 是允许的，不违反铁律 13
- [TASK-013] `git stash` 默认不保存 untracked 文件 → 重建比恢复快。重要 untracked 文件应 `git stash -u` 或先 `git add`
- [TASK-017] 任务卡 allow_write 不含 lessons-learned.md 但铁律 12 强制修改它 → 每个合规 PR 必挂 L3 scope 门禁（4 个 PR 连续红灯）；卡模板与 active 卡必须包含该文件
- [TASK-017] check-pr-scope 先查 deny 后查 allow 且卡内 allow/deny 区间重叠（TASK-012 `tests/**/*.cs`）→ allow 成死信；v2 已改为 allow 先行 + 重叠显式报 [CONFIG-CONFLICT]

<!-- 新增经验追加在上方，格式保持一致 -->
