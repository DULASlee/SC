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
- [TASK-017] check-pr-scope 先查 deny 后查 allow 且卡内 allow/deny 区间重叠（TASK-012 `tests/**/*.cs`）→ allow 成死信；v3 已改为 allow 先行 + 重叠显式报 [CONFIG-CONFLICT]
- [TASK-017] scope 检查器若用"全文 TASK-\d+"提取授权卡，会把正文里引用/对比/路径中的历史卡（如 draft TASK-001 的 deny `.harness/**`）也加载进并集 → 自举 PR 自撞 10 个 CONFLICT；v3 只认交付声明（`## TASK-XXX` 标题 / Closes|Fixes|Refs|任务卡 关键词引导）+ 卡须 ready/in_progress，否定语境行（未改动/不在/not）整行跳过
- [TASK-017] DSH shell 工具全部 0xC0000142 且零输出 ≠ pwsh 未装/损坏：是 workspace-write 的 Windows ACL restricted-token 沙箱 runner 自身启动失败；danger-full-access 绕过沙箱即正常。诊断顺序：先用升级模式跑一次再下"环境坏了"结论，勿在表象层反复重试同一命令
- [TASK-017/TASK-018] 设计权衡：v3 声明式卡号提取（只认 `## TASK-XXX` 标题 / Closes|Fixes|Resolves|Refs|任务卡 引导）把 PR 模板与提交规范变成硬约束——PR 描述不按此约定声明卡号，门禁会误判越界。收益（杜绝散文卡号被误当授权卡）大于代价（模板写法受限）；任何 PR 模板改版必须同步评估该解析规则，否则半年后换写法必踩坑
- [dispatcher-mvp] 编排层"不常驻"设计：dispatch/poll 各只做一轮，状态全落盘（RUNS.jsonl 账本 + git worktree 隔离）→ 进程崩了重跑 poll.py 即可续，无需守护进程；前提是同一时刻只跑其一（账本无跨进程锁，串行即正确性保障）
- [dispatcher-mvp] 判定权零让渡：自动化脚本永不写 done，只能改 in-progress（占坑）/blocked（超重试）/awaiting-review（门禁通过）；done 唯一来源仍是人类 verify-all.py + archive-task.py。轻量机器门禁只做 scope+规模+卡校验三层，dotnet 全量 build/test 留验收侧
- [dispatcher-mvp] 机器门禁量 worktree 未提交变更必须 `git -c core.quotepath=off status --porcelain -uall`：默认会把整棵未跟踪目录折叠成一行（如 `newdir/`）→ deny_write 命中与规模上限双双失效，越界新建被判 pass
- [dispatcher-mvp] `python -m unittest discover -s .harness/tests -t .` 在 Py3.14 报 `ImportError: KeyError: ''`——顶层目录名 `.harness` 以点开头像非法包名；顶层须用 `-t .harness`（写成 runner 或文档固化，别散在各任务）

- [Phase2] `loop --once --max-tasks 0` 不是纯只读 dry-run → poll 会把 fail-exec 回收并重派新 attempt（fire-and-forget 还会拉起 dsh 子进程），跑前须确认副作用可接受，runs/worktrees 必须 gitignore
- [Phase2] 运行手册里的每个数字/语义都要先 grep 对码（预算 2000/12288、fail-fast、pre_approved 三规则皆有对应实现行）→ 文档断言无码可依即虚假文档，写前先取证

- [Phase2] Windows 下 subprocess 直拉 npm 垫片(dsh 无 exe)必 FileNotFoundError exit=-1 → run-exec 按后缀经 cmd.exe/pwsh 包裹；教训：e2e 必须含一次真 headless 派发，dry-run 永远发现不了执行器链路问题
<!-- 新增经验追加在上方，格式保持一致 -->
