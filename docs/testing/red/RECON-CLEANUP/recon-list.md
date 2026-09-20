本清单有效期：022 退出裁定完成之前。裁定完成后转为归档引用，不再更新。

# RECON-CLEANUP 归位清单（工作树 19 项残留处置底稿）

> 版本：2026-09-19 v2（含架构师四项裁定回填，本节顶部裁定快照随稿提交；
> 此后 032-040 卡片落地过程中的状态变化不再更新本稿，转归档引用）。

## 架构师裁定快照（v2 新增，2026-09-19）

### R1 五卡 ready 处置 → C（状态语义归位）

029 保持 ready（真实待执行，正确）。023/024/030/031 → closed（架构师确认落地即归档）。
会话不得自报 done；架构师裁定 closed 是 approver 角色行为，非自报。
衍生扫描（本稿 §10）结论：008/009/010/011/012/013/014/017/018/019/020 十张 in-progress 卡
同为「实施已落地但未关」状态（L3 收口缺位）——本次一并扫描记录，关闭裁定按卡逐张走
（010/021 等存在真实未收口工作项的除外，见 §10 逐卡实证列）。

### R2 CI 红灯 → 033 P0 立即放行

033 验收判据（钉死）：
1. schema 增补 approver 字段定义（类型 + 枚举值约束，防拼写幽灵条目）；
2. 对现有卡（回填集 = §11 全量 grep 结果，18 张）做一次回填校验，产出「需补 approver」清单；
3. CI validate job 转绿，且 `git show HEAD:.harness/schema/task-card.schema.json | grep -c approver ≥ 1`；
4. 判定 schema 是否被 schema 自检（防 schema-of-schema 失实）。
032 与 033 分卡：033 紧急窄范围先动，032（字段增补讨论）可缓。
红灯成因追查（架构师要求）：定位红灯起始 commit 与成因（回归 vs 长期分叉），
写入 033 closeout（机制失效成因归档）。

### R3 开卡顺序分三段（032-040 编号已按裁定重排，v2）

- 阶段一（机制修复，一次收口）：033 schema 修红灯。
- 阶段二（配置与消费者，依赖 033）：032 schema 字段增补 → 034 dispatch.yaml →
  035 modelswap.py → 036 replan.py → 037 runs.py → 038 归档注释（最后，措辞随 033-037 定稿）。
  一卡一提交，同一施工单元连续执行。
- 阶段三（文档，依赖提案裁定）：039 AGENTS.md → 040 ai-workspace/README.md。
- 038 裁定域收窄（架构师第 6 项埋点）：038 产出 = 归档目录说明里的**一条不可变原则
  + 现有归档卡各一行指针**；**禁止**逐张归档卡写注释（黑洞）。措辞反映 033-037 定稿后的机制。
- P1-P3 的去向（架构师裁定）：转事实型，并入 038 或单开轻量卡：
  全仓文档重复段落清单 + 现行所有非 Junction 引用路径 → 产出「事实清单」而非规则提案，
  拿到清单后再决定是否立规。

### R4 提案子清单 P1-P6 裁定

| ID | 裁定 | 执行 |
|---|---|---|
| P1/P2/P3 | 去（伪提案：无违反者、无检测、无动作定义即无规则资格） | 担忧真实成分保留：并入 038/轻量卡做「先测量后立规」事实清单 |
| P4/P5 | 归位，走 022 吸收面 | 事实型，与 022 closeout 语义连贯；单卡单提交 |
| P6 | 推荐型降级写入 | 显式「建议/recommended」标记，与硬约束（必须/不得）文档层级分开；若文档无此层级，该结构问题并入 039 |

lessons 去向（架构师裁定）：**B**——20 行归位 + P4/P5 合并为 022 的一次追加裁定
（一次 commit，allow_write = lessons-learned.md；022 closeout notes 补一行
「追加 lessons 归位，P4/P5 事实型」）。PILOT-CHECKLIST 改判丢弃（文件头自声明不进 git）
→ 022 吸收面清空即成 022 退出观测信号之一。

022 退出条件（架构师裁定，维持 §6 两段信号）：3 轮静默 + 显式宣告；
「3」= 治理改动波间隔上界（029/023/022/024 四轮连续触碰 5 脚本集为实证）；
永不触发则重审机制本身，不调数字。

### R5（本轮新增，2026-09-19）事故记录 + R1-C 执行记录

- **事故**：批量 PowerShell 注入 4 张卡 closeout notes 时，`WriteAllText` 写回破坏
  TASK-023/024/030/031 的 YAML 块标量缩进（notes 段 2 空格缩进丢失）→ 门禁
  `validate --all` 当场拦截 4 张卡，4 次 pre-commit 全部 FAIL；循环中 4 次
  `git add` 在门禁失败后仍把损坏版本推入暂存区（add 不跑门禁）→ 暂存区污染。
  恢复：`git restore --staged` ×4 + `git checkout --` ×4（worktree 与 index 均回到
  提交时干净态，`validate --all` 全 OK 复核通过）。
- **处置**：closeout notes 改用**逐卡手工 Edit**重做（4 commit，各一卡，门禁全绿）：
  165b97c (023) / 91cbdda (024) / f8f0b56 (030) / 4a6bc42 (031)。状态保持 ready
  （R1-C 语义：裁定记录非状态翻转，done→archived 走 L3 收口）。
- **教训**（并入 024 精神——声明项实现前取证；机器门禁已证明其价值：损坏在
  提交前被 `validate --all` 拦下，未进 HEAD）：
  ① 对含块标量（`|`）的 YAML 禁用脚本整体写回，插入一律走文本级 Edit（锚点定位）；
  ② 循环中 `git add` 必须跟随门禁结果（FAIL 即中止循环，不得继续 add）；
  ③ 暂存区污染处置 SOP = `git restore --staged <paths>` + `git checkout -- <paths>`。

### R6（2026-09-19 第二轮审计后新增）证据落盘纪律 + 033 补强 + 039 拆卡 + 038 前置断言

- **自指缺口（架构师点破）**：022/033 的「取证结论」（18 卡回填时点、判据 5、C2 交叉核验、
  CI 核对）当时只有文字断言，**原始 stdout 未落盘** → 038 归档时要写的证据链，其取证
  环节本身违反证据纪律。修复：全部 git log -S / blame / CI 核对原始输出落
  `.harness/artifacts/`（022-closeout-blame-evidence.txt / 033-approver-blame-groups.txt /
  033-criterion5-stdout.txt / 033-ci-continue-on-error.txt），后续 038 只引用路径不复述内容。
- **033 closeout 补强表（架构师要求：covered_by_this_change vs deferred）**：
  - covered：approver 字段定义+枚举、点名层（未声明字段指名）、drafts 扫描、
    判据 5 故意违规（A/B/A3）、回填清单（backfill-report.md）。
  - **deferred → 拆 TASK-039**：「红灯不被当阻断项」流程缺口（CI validate job
    现状待核：ci.yml:118/158 的 continue-on-error 属覆盖率观察期/stryker，
    与 validate job 是否同构需架构师核）。039 要素：触发条件 / 责任人 /
    最晚关闭时点 / 未关闭前人工兜底（批量提交双人复核）。
- **034-037 放行前置（架构师裁定：机器可判定断言，非自然语言态度）**：
  四断言任一 evidence 缺失 → 不放行（038 内 prereqs-034-037.yaml 载体）：
  1. schema.approver.enum_locked → `git show cd5b7d3:.harness/schema/task-card.schema.json | grep -c '"enum"'` ≥ 1
  2. validate.criterion5.all_green → `git show 6bf56b2 --stat | grep run_criterion5` 命中 + 重跑绿
  3. validate.drafts_scan.clean → `python .harness/scripts/validate-task-card.py --all` exit 0 且含 drafts
  4. ci.validate.non_optional → `.harness/artifacts/033-ci-continue-on-error.txt` 判定为 B/C（非 A）
- **判据 5 口径修正（架构师裁定）**：A2 降级为「已识别的冗余设计」；
  判据 5 实际 = 2 类真故障（幽灵字段 / 枚举外值）+ 1 类前瞻防护（A3，防未来枚举扩容）。
- **033 面范围更正（架构师裁定）**：「033 只动自己面」表述前提有误——schema 本身
  属阻断面（schema 变更应触发全量重校验），且 21 项清单含 archive/TASK-002 + PILOT-CHECKLIST
  → 033 allow_write 实际覆盖整个 .harness/tasks/；新检测面（validate 点名层 + drafts 扫描）
  必须登记为 033 名下检测面（下轮改 validate 者须查此登记）。

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

## §10 衍生扫描：全 active 卡「实施已落地但未关」完整性核查（架构师 §7 衍生要求）

active 卡全量状态扫描（2026-09-19）：

| 卡 | status | 实施状态 | 未关原因 / 关闭路径 |
|---|---|---|---|
| 023/024/030/031 | ready | 实施已落地（各自 commit 证据链） | 架构师裁定 closed（R1），closeout notes 待补 |
| 029 | ready | **真实待执行**（lessons-index.json 未建，LessonsIndexTests 当前空真通过） | 保持 ready，dispatch 资格正确 |
| 022 | in-progress | 覆盖卡常驻态（b077bca），closeout 已收口 | 按 R4/§6 两段信号退出，非 closeout |
| 008/009/010/011/012/013/014/017/018/019/020 | in-progress | 历史施工已落地（各卡 commit 链 + RUNS.jsonl 归档记录） | **L3 收口缺位**（done 唯一来源 = 人类 verify-all + archive-task，从未执行）；关闭须逐卡裁定，不在本稿擅动 |
| 001 | draft | 设计期卡 | 正常 |

「未关」面远大于 §7 初判的 5 张——11 张 in-progress 历史卡同属 L3 收口缺位。
处置边界：本稿只**记录与定位**，关闭裁定逐张走（需要 verify-all 证据 + 架构师
逐卡 closeout 裁定），不批量翻状态。

## §11 红灯定位实证（033 P0 输入）

- 回填集（`grep '^approver:' .harness/tasks/active/*.yaml` 全量）：**18 张**
  （008,009,010,011,012,013,014,017,018,019,020,021,022,023,024,029,030,031），
  非初判的 12+。
- 红灯成因定位：HEAD 的 `validate-task-card --all` 本地全绿（HEAD schema 无 approver
  字段，validate_card 对未声明字段不拦截）；但 CI validate job 若按同一 HEAD 运行，
  行为与本地一致 → 当前红灯的实际位置是**「schema 与现行实践分叉」而非 CI 物理红灯**：
  18 张卡的 approver 在 schema 视角下是未声明字段，门禁承诺（additionalProperties:false
  应拦下未声明字段）**形同虚设**。分叉起始 = `28c0f06`（023 首次批量写 approver 进 12 张卡
  + schema 未同步；schema 的 approver 定义行在 worktree 停留至今）。
- 红灯年龄结论：**023 合入即分叉（非 030/031 回归）**，分叉至今 3 轮。033 closeout
  记录此定位（架构师「为何未被更早捕获」之问：validate-task-card.py 未做
  additionalProperties 逐字段校验，schema 失实不在该脚本检测面内——检测面缺口
  本身并入 033 验收判据 4 的 schema 自检回路）。

## §7 风险提示：五卡 ready 态的 dispatch 资格（未擅动，待裁定）

TASK-023/024/029/030/031 当前 status 均为 **ready**（`grep ^status:` 实证），dispatch 扫描即 eligible。
其中 029 为真实待执行（索引未建）；023/024/030/031 的实施工作已随架构师指令 commit 落地，
按 L3「done 唯一来源是人类 verify-all + archive-task.py」不得自报 done → 当前悬置。
选项（待裁定，不擅动）：A) 翻 in-progress-hold（022 先例 b077bca，可逆）；B) 维持 ready + 人工 verify-all 尽快归档；C) 维持现状。
