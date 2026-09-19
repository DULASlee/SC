本清单有效期：022 退出裁定完成之前。裁定完成后转为归档引用，不再更新。

# RECON-CLEANUP 归位清单（工作树 19 项残留处置底稿）

> 版本：2026-09-19 初稿（022 closeout 后首轮）。配套：提案子清单（§3）、022 退出条件（§6）。
> 19 项当前状态：**全部未暂存，阻断态保持**（`git status` 暂存区 0 项）。本稿只出清单，不动任何一项。

## §0 术语确认（架构师纠正已吸收）

FROZEN 约束的准确表述：**FROZEN 卡的 allow_write 处于关闭状态，任何写入请求（无论内容多相关）都无授权通道**——是授权机制问题，不是内容匹配问题。因此本清单对 025-028 相关条目一律采用「新开独立卡 + 待开卡标记不抢跑」，不借 FROZEN 卡通道。

## §1 逐条判定表（开新卡 7 项，非 6 项）

| # | 条目 | diff 实证 | 判定 | 去向 |
|---|---|---|---|---|
| 1 | `.harness/dispatch.yaml`（+3/-1） | `model_fallbacks` 填值 + `auto_fallback: true`；代码侧 `dispatch.py:58-59`/`poll.py:306-307` 真实读取（非装饰配置） | **开新卡**（拟 TASK-032） | 独立验收：fallback 链路行为；022 射程不含 dispatch.yaml |
| 2 | `.harness/schema/task-card.schema.json`（+4） | 新增 `approver` 字段；**HEAD 版 schema `approver` 计数 = 0**，而 HEAD 已有 12+ 张卡携带 approver → **CI validate job 现处于红灯态**（检出即判 additionalProperties 违规） | **开新卡，最高优先级**（拟 TASK-033） | schema 回填已在产线使用的字段；先落地解 CI 红灯 |
| 3 | `.harness/scripts/modelswap.py`（+20，新增 snapshot/verify_selection） | 真实新函数；全仓 active 卡 allow_write **零覆盖**（grep 确认） | **开新卡**（拟 TASK-034） | 见 §2 依赖与 022 覆盖洞 |
| 4 | `.harness/scripts/replan.py`（+20，新增 plan_retry） | 同上，零覆盖 | **开新卡**（拟 TASK-035） | 同上 |
| 5 | `.harness/scripts/runs.py`（+17，新增 budget_attempts） | 同上，零覆盖 | **开新卡**（拟 TASK-036） | 同上 |
| 6 | `.harness/tasks/active/PILOT-CHECKLIST.md`（±16） | `[ ]`→`[x]` 勾选态翻转；**文件头自声明「不进 git（本地勾选卡）」** | **丢弃**（worktree restore） | 本地试点操作态，非交付物；跟踪态本身存疑但移出跟踪超出本轮射程，记录待议 |
| 7 | `.harness/tasks/archive/TASK-002.yaml`（±46） | `git diff --ignore-all-space --stat` → **0/0，纯空白改写** | **丢弃**（worktree restore）+ 永久性注释（见 §5） | 硬理由：零实质变更；防循环噪音见 §5 |
| 8 | `AGENTS.md`（+14） | 新增 agit 会话管控规则块（含 "Never rebase…" 硬约束措辞） | **开新卡**（拟 TASK-037，待提案裁定后动） | 规则块内容 partly 属提案（见 P3），先裁定后施工 |
| 9 | `docs/ai-workspace/skills/README.md`（+22） | 新增路由表 + 已装清单（on-disk 5 目录已核验存在，事实部分可验）+ 「唯一源/只允许 Junction/安装落地铁律」措辞 | **拆分**：事实部分随新卡（拟 TASK-038，待提案裁定后动）；规则措辞入提案子清单 P1/P2 | 见 §3 |
| 10 | `docs/ai-workspace/rules/lessons-learned.md`（+20 行 + [TASK-024]） | 混合：流程/事实行 + 规则提案行（见 §4 拆分） | **拆分**：归位行候选 022 后续工作项 / 提案行入 §3；整文件暂缓（见 §4 选项 A/B） | 归位走对应卡通道，绝不混入 |
| 11 | `docs/architecture/asyncapi.yaml`（±1074） | `--ignore-all-space --stat` → **0，纯格式噪音** | **丢弃** | 同 #7 硬理由 |
| 12 | `docs/architecture/openapi.yaml`（±2204） | 同上，0 实质变更 | **丢弃** | 同上 |
| 13 | `debug2.py/3/4`（全文件重写，抽样 debug2.py 内容同义） | 会话调试脚本（PE 解析），无交付目标、无卡授权 | **丢弃** | 会话过渡态 |
| 14 | `extract_addrmap.py/extract_strings.py/gen_map_doc.py` | 一次性逆向辅助脚本，同上 | **丢弃** | 同上 |

（注：#13/#14 上表按文件组合并为 2 行；19 项 = 14 行中 #6/#7/#11/#12/#13/#14 丢弃 6 文件 + #10 拆分。）

## §2 新开 7 卡计划（编号避开冻结 025-028）

| 拟卡号 | 对应项 | 内容 | 顺序 |
|---|---|---|---|
| TASK-033 | #2 schema | `approver` 字段回填（已在产线使用，解 CI 红灯） | **最先**（阻塞 CI） |
| TASK-032 | #1 dispatch.yaml | `model_fallbacks` 值 + `auto_fallback`（代码已读，需验收 fallback 行为） | 033 后 |
| TASK-034/035/036 | #3/#4/#5 | modelswap/replan/runs 新函数逐卡验收 | 032 后（schema→dispatch→脚本，不可颠倒） |
| TASK-037 | #8 AGENTS.md | agit 规则块（事实部分；提案部分先裁定） | 提案子清单裁定后 |
| TASK-038 | #9 skills/README | 路由表 + 已装清单（事实部分）；规则措辞先裁定 | 提案子清单裁定后 |

**022 覆盖洞（本次清单真正的洞，架构师已点名）**：#3/#4/#5（含 #1/#2 的配置文件）当前**零卡覆盖**——任何会话可直接改这三个脚本而不触发 check_approval。032-036 落地即恢复覆盖；落地前靠纪律（不直接改），不另设临时门禁。

## §3 提案子清单（022 裁定用：类型 / 违反者 / 检测 / 动作）

| ID | 来源 | 原文主张 | 类型 | 违反者 | 如何被发现 | 022 裁定建议 |
|---|---|---|---|---|---|---|
| P1 | skills/README | 「agent 目录只允许 Junction 符号链接指向此处」 | 硬约束型（"只允许"） | 向 .agents/skills/ 写实体副本的会话/CLI | **无**（全仓无 hook/脚本扫描 .agents/ 实体） | 伪提案：驳回，或降级为推荐型（除非补检测手段） |
| P2 | skills/README | 「安装落地铁律：实体必须移入…（含字节比对），agent 目录只放 Junction」 | 硬约束型（"铁律/必须"） | 跳过迁移的 skill 安装执行者 | 人工（ORIGIN.md 记录），无机器门禁 | 降级为推荐型（流程指南），或补检测 |
| P3 | AGENTS.md agit 块 | 「Never rebase or force-push AgentGit history」等 | 硬约束型 | merge agent | **无** | 降级为会话级惯例（明确标注非强制执行），或补检测 |
| P4 | lessons L61/L62 | Junction 迁移「正确流程」三步 | 流程知识（how-to，非"规则该改"） | —（知识条目） | 与现状一致即成立 | 事实型→归位（§4） |
| P5 | lessons L47 | ORIGIN.md 记录格式 | 流程事实 | — | 与现状一致即成立 | 事实型→归位（§4） |
| P6 | lessons L20 | 「未来考虑：hook 识别一次性豁免关键词自动放行」 | 规则变更草图 | — | 已被 SKIP_PROTECTED_CHECK 部分替代 | 推荐型候选→022 裁定（很可能关闭） |

其余 lessons 行（model-config 参数实测、scout 搜索程序、retire 审计程序、TASK-021 Base URL、TASK-024 pathspec）：事实型→归位（§4）。
机密检查：model-config 行提及 "CN sk-cp key" 为前缀片段，目检无完整密钥；归位提交前由执行卡复核铁律 9。

## §4 lessons 20 行拆分与去向问题

- **归位候选**：流程/事实行（P4/P5/其余事实行）。
- **提案行**：P1-P3 相关表述（若 lessons 行内出现）+ P6 → 入 §3，不随归位动。
- **去向二选一（待裁定）**：
  - A：022 后续工作项（allow_write 已含 lessons-learned.md，免新开卡；但 022 设计域为 checker 脚本，需裁定是否 stretching）。
  - B：随 §2 新卡同批（整文件待提案裁定后一次性归位； surgical 逐行恢复易错，不推荐逐行手术）。
  - 推荐 B（整文件 defer，一次归位），裁定请示。

## §5 TASK-002 丢弃 + 永久性注释

- 丢弃动作：`git checkout -- .harness/tasks/archive/TASK-002.yaml`（worktree 恢复，无需卡——非提交）。
- 永久性注释（防循环噪音）：`archive/` 下尚无 README；注释文件 `archive/README.md` 为**新文件**（.harness/** 受保护），需卡覆盖——**与下一次触碰 archive/ 的卡同批落地**（或单独立卡），措辞：
  > 归档卡为历史快照，格式冻结，不再参与现行格式修订。归档格式迁移由专门的"归档格式修订卡"一次性处理，不散落在会话工作树里。

## §6 022 常驻覆盖态退出条件（架构师裁定记录）

- 采用**有条件退出**（非永久覆盖）：机制成本与问题规模脱钩时机制即应退出；永久覆盖是死债。
- 退出信号（两段可观测）：
  1. 连续 **3** 轮施工无卡片触碰 5 个脚本（观测窗口）；
  2. 且架构师显式宣告维修窗口关闭（显式动作）。
- 「3」的依据：预期两轮治理改动之间的最小间隔的上界——实证：029/023/022/024 四轮连续触碰 5 脚本集（check-pr-scope@029、dispatch+pipeline@023、poll+check-local-scope@022/024），改动波约每轮一次；连续 3 轮静默 = 政权更替信号（治理进入例外维护态）；1-2 轮静默可能是批量施工噪音。逃生：若条件永不触发（改动波不断），应重审"覆盖机制是否该退出"本身，而非调数字。
- 退出动作：022 `done→archived` + notes 补记：
  > 本卡为限时覆盖机制，已按 [退出宣告 commit] 退出，后续相关改动由现行门禁自行覆盖。
  该行把"022 为什么存在过"留给后人。

## §7 风险提示：五卡 ready 态的 dispatch 资格（未擅动，待裁定）

TASK-023/024/029/030/031 当前 status 均为 **ready**（`grep ^status:` 实证），dispatch 扫描即 eligible。
其中 029 为真实待执行（索引未建）；023/024/030/031 的实施工作已随架构师指令 commit 落地，
按 L3「done 唯一来源是人类 verify-all + archive-task.py」不得自报 done → 当前悬置。
选项（待裁定，不擅动）：A) 翻 in-progress-hold（022 先例 b077bca，可逆）；B) 维持 ready + 人工 verify-all 尽快归档；C) 维持现状。
