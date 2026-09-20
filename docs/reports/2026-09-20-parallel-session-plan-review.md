# 并行会话隔离与全局协调机制 · Formal Implementation Plan v1.0 评审报告

- 评审日期：2026-09-20
- 评审对象：《并行会话隔离与全局协调机制 Formal Implementation Plan v1.0》（用户提供稿）
- 评审方法：按方案自身 P0 原则执行——真实代码取证，不信目录名、不信方案自述
- 评审范围：方案的合理性与必要性（用户指定"最先审核"），兼及可行性与边界纪律
- 评审者身份：AI 会话（opencode / GLM-5.3）

---

## 0. 总结论

**方案合理且必要，批准进入 P0 取证阶段；冻结 v1.0 前须完成 5 处修订（A1-A5）。原方案唯一可行性未证实的部分（P4 模型会话覆盖）已于本评审内完成真实运行验证：可行（见 §7）。**

三条会改变决策的判断：

1. **方案要解决的问题大部分是真的。** 6 条目标中 5 条在代码中核实为真实存在且值得修；其中"模型切换改写共享配置"的实际危害比方案描述的更大（见 §3-断言 2）。
2. **两处对现状的断言与事实不符。** 账本并非每工作区一份（已集中）；模型配置不是仓库级而是用户机器级。不修正会误导 P0 报告与工作量估算（见 §3）。
3. **P4（模型会话覆盖）可行性已由探针实证（§7），且比方案预想的更简单**：执行器原生支持按次叠加配置层与会话级设置文件重定向，全局文件可以做到零触碰。方案 §6 的目标照单成立，实现路径已定。

边界纪律部分（§15 文件修改边界、§16 四条硬规则、以真实三工作区并发验收而非"代码写完"）是本方案最有价值的组成，与本仓历史事故（TASK-013 并行会话污染、多起"顺手重构"教训）直接对应，**建议原样保留，并按 §5.3-B 补充登记**。

---

## 1. 评审执行记录（可复核）

本次评审在方案施工前独立完成了 P0 级取证（即方案第 8 节要求的现状映射的预执行）。核心证据命令与输出摘要：

| 取证动作 | 关键输出 |
|---|---|
| 读 `.harness/README.md`（L3 协议 + Dispatcher MVP + Phase2 全文） | "同一时刻只允许 dispatch.py 或 poll.py 之一在跑：RUNS.jsonl 无跨进程锁，串行是'崩了重跑即可续'的前提"（README:265）；"同轮多模型只派第一组模型相同的卡"（README:322 上下文） |
| 读 `.harness/dispatch.yaml` | `concurrency: 1`（pilot 期降级值，原设计"先锁 3"）；`executor_argv: dsh --profile headless {prompt}`；`skills_dir: F:/JQKJ/docs/ai-workspace/skills`（绝对路径） |
| 读 `.harness/scripts/runs.py` 全文 | 账本在主树 `.harness/runs/RUNS.jsonl`；append 用 fsync 真追加、覆写用 `os.replace` 原子重写；**无任何跨进程锁** |
| 读 `.harness/scripts/modelswap.py` 全文 | 模型写入点是**用户级** `~/.dsh/settings.yaml` 的 `agent-default-model`；docstring 明示"DSH 模型唯一来源是 ~/.dsh/settings.yaml … dsh --profile headless 本身无模型参数"（modelswap.py:2-7）；mkdir 锁 `<runs_dir>/modelswap.lock`（pid + 600s stale + 二次确认），持锁仅毫秒级 |
| 读 `.harness/scripts/dispatch.py` 全文 | `ensure_worktree`（:176-191）建 `feat/{task_id}` 分支 + worktree；`slots = concurrency - running_count`（:415）为**无锁 check-then-act**；:402-405 注释自认全局 swap 存在跨轮毫秒级竞态窗口；`commit_card_status`（:338-361）在主树 git commit 改卡状态 |
| 读 `.harness/scripts/poll.py`（1-120）与 `.harness/scripts/loop.py`（1-100） | `pid_alive` 用 tasklist 判活（poll.py:62-72）；loop 有自己的 mkdir 单实例锁 `loop.lock`（loop.py:52-92，同样 pid + 600s stale）——**跨进程锁模式在本仓已有两处 Windows 实战验证** |
| 读 `.harness/scripts/start-task.py`（1-80） | 上下文写入脚本所在树的 `.harness/context/`（worktree 内运行则落在该 worktree） |
| 读 `~/.dsh/settings.yaml` 与 `~/.dsh/profiles/` | settings 顶层键：`ui-onboarding / agent-default-model / llm-pi-ai / dsh-better-sidebar / llm-deepseek`；profiles 有 desktop/headless/web，其 `cordis.patch.yml` 只见插件配置（compaction、MCP），**未见模型选择能力** |
| `git branch -a` + `git log --oneline -5` | 主树当前分支 `chore/task-018-020-followups`（人工分支）；`feat/TASK-008/009/010` 带 `+` 标记（仍挂在现存 worktree 上）；卡状态提交与人工提交混在同一历史 |
| 列 `.harness/runs/`、`.harness/worktrees/` | 现存陈旧 worktree：TASK-008/009/010（对应任务已归档）；`RUNS.jsonl.bak` 备份残留 |
| 列 `.harness/tests/` | 14 个 test_*.py（unittest），覆盖 dispatch/poll/loop/modelswap/runs/pipeline 等 |
| 列仓库根目录 | 多产品单仓既成事实：CNC、CNC04、DHH02、DHH04、MZS01、LnkCollector_src、src、source、IoTPlatform.sln、contracts、tests |
| 列 `docs/adr/` 与 `docs/architecture/adr/` | **规则矛盾**：engineering-rules 铁律 10 要求 ADR 放 `docs/adr/`（实际 5 份 ADR 全在此），AGENTS.md 速查表写 `docs/architecture/adr/`（存在但空置） |
| `dsh --help` 全参数盘点 + `--dump-config` 组合验证 + 两轮真 headless 探针 + 全局文件哈希前后比对 | 发现 `--patch` 按次叠加层与设置文件重定向能力；探针成功且全局配置零改动（完整记录见 §7） |
| `.gitignore` | `.harness/context/`、`.harness/runs/`、`.harness/worktrees/`、`.harness/**/__pycache__/` 均已忽略 |
| `lessons-learned.md` 第 21 行 | 现行规则："同一时间只允许一个 AI 会话操作仓库"——本方案将废止此规则 |

---

## 2. 现状映射（预填方案 P0 要求的 EXISTING-MAP）

| # | 方案 P0 要找的机制 | 现状位置 | 权威范围 | 使用者 |
|---|---|---|---|---|
| 1 | Worktree 创建入口 | `dispatch.py::ensure_worktree`（:176-191），根 `.harness/worktrees`（主树内、gitignored） | 仓库级 | dispatch / poll 重试轮 |
| 2 | Branch 创建入口 | 同上，`feat/{task_id}` | 仓库级 | 同上 |
| 3 | 自动派发入口 | `dispatch.py::main`；常驻编排 `loop.py`（单实例锁）；九阶段管线 `pipeline.py`（账本 owner: pipeline） | 主树 | loop / 人工手工调用 |
| 4 | 手工会话入口 | **不存在**。人工会话直接在主树工作（受单会话规则约束），无 worktree 分配、无登记 | — | — |
| 5 | 运行账本 | `runs.py::RunsStore` → 主树 `.harness/runs/RUNS.jsonl` + `PIPELINE.jsonl`（两份，槽位经 `running_count(owner=None)` 互通，dispatch.py:108-117） | 主树（**非每 worktree**） | dispatch / poll / pipeline / modelswap |
| 6 | 并发计数实现 | `dispatch.py:415` `slots = concurrency - running_count(store)`，无锁 check-then-act；安全靠串行约定 | 主树 | dispatch |
| 7 | 模型锁 | `modelswap.py::acquire_lock`（mkdir + pid + 600s stale + 二次确认），仅包裹"读+备份+写"毫秒级区间 | runs_dir（仓库级） | dispatch / poll |
| 8 | 全局模型配置写入点 | `modelswap.py::swap_for_run / restore` → `~/.dsh/settings.yaml` `agent-default-model`（**用户机器级**，跨仓库、跨所有 DSH 会话生效） | 用户级 | 派发链路；**间接受害者：一切手工会话与本机其他仓库** |
| 9 | Task Card 状态读写 | 卡 `status:` 字段；`dispatch.py::commit_card_status`（主树 git commit，pathspec 限定 + `[APPROVED-BY]` + TASK-023 自覆盖契约） | 主树 | dispatch / poll / 人工归档 |
| 10 | Task ownership 判定 | **不存在显式机制**。隐式独占 = status 占坑 + 单派发器前提 | — | — |
| 11 | Hook 读取 Task Card 位置 | `.githooks/`（`core.hooksPath` 全仓共享，worktree 天然继承）：check-local-scope、check_approval、commit-msg protected-paths | 仓库级 | 所有树内的 git 操作 |
| 12 | 不入库 / 自生成 runtime state | `.harness/runs/`、`.harness/worktrees/`、`.harness/context/`（gitignored）；`~/.dsh/settings.yaml`、`~/.dsh/profiles/`、`~/.dsh/skills`（用户主目录） | 混合 | 见上行 |

补充两个方案未列但属同一集合的共享状态：

- 13. **主树的双重角色**：主树既是人工工作区（当前分支为人工 chore 分支）又是协调中枢（卡状态 commit 落在主树当前分支）——人工提交与机器状态提交混在同一分支历史（git log 证据）。
- 14. **主树只读依赖**：worktree 会话经绝对路径读主树的上下文（`build_prompt` 用 `ctx.resolve()` 绝对路径）与 skills（`skills_dir` 为指向主树的绝对路径）。

---

## 3. 方案断言 vs 现状事实核对

| # | 方案断言 | 核对结果 | 对施工的影响 |
|---|---|---|---|
| 1 | §4.1"运行账本必须从 Worktree-local state 提升为共享状态"，并示例禁止 `Worktree A/.runtime/ledger` | **偏差**：账本今天就在主树 `.harness/runs/`，不存在每 worktree 一份账本的情形；真正的缺口是**并发写者保护与崩溃安全**（无锁、Windows 多进程 append 交织风险） | P3 工作量重定义：不是"集中"，是"加锁 + 原子区"。工作量更小，但性质不同；不改则 P0 报告失真 |
| 2 | §6"全局模型配置"需改为 Session Override；"只需打通现有配置覆盖能力" | **方向属实、程度被低估；可行性已验证为"通"**：①写入点是**用户机器级**文件，影响面跨仓库、跨所有手工会话——比方案描述更危险（现有事故面：手工会话在 swap 窗口内启动会拿到错误模型；跨轮 restore/swap 竞态已被代码注释自认，靠"同轮同模型"降级规避）；设置文件默认还带文件监视器，改写会**热发布到正在运行的其他会话**——危害面比方案写的更宽；②执行器侧的会话级覆盖能力**已实证存在**（`--patch` 叠加层 + 设置文件按会话重定向，见 §7 探针记录） | P4 可行且实现路径已定（§7）；方案 §6 的"禁止写共享配置"目标照单成立；modelswap 的 swap/restore/锁机器在派发路径上可整体退役 |
| 3 | §5.2 check-then-act 竞争窗口必须消除 | **属实**：`dispatch.py:415` 无锁计算槽位；现安全靠 README:265 的**约定**（同一时刻只跑其一），loop.lock 只保 loop 自身单实例，dispatch/poll 手工并行完全无保护 | P3 必要性成立；实现路径已有（mkdir 锁模式两处 Windows 实战验证） |
| 4 | §2 `1 Session = 1 Worktree = 1 Branch = 1 Task Owner` | **部分新造**：现状是 `1 Task = 1 Worktree = 1 Branch`（feat/TASK-XXX），且 **attempt 重试复用同一 worktree**（poll 失败 → `reset_worktree` → 重派同任务同 worktree）。方案引入的"Session"是新增维度 | P5 必须显式保留重试链语义（见修订 A3），否则施工者极易把 Owner 绑定到 attempt、打断现有重试机制 |
| 5 | §7.2 禁止双目录执行同一任务 | 现状由"占坑即改卡状态 + 单派发器"**隐式**保证；无显式拒绝机制 | 方案要求显式拒绝是合理增量，属最小改动 |
| 6 | L0"禁止手工会话绕过 worktree 创建机制" | 现状**无任何机制拦截**，只有 lessons-learned 第 21 行的规则禁令；而本仓"约定即可靠"已被多次证伪 | P1 需要 enforcement 机制而不仅是规则（见修订 A4） |

---

## 4. 必要性评估

**结论：必要。** 四条论据全部有代码/档案证据：

1. **串行约定是当前唯一正确性支柱。** 账本无锁（runs.py 全文无锁原语）、槽位计算无锁（dispatch.py:415）、手工并行无保护——多会话/多编排器一旦出现即数据竞争。经验库第 21 行"同一时间只允许一个 AI 会话操作仓库"与 TASK-013 污染事故证明这不是理论风险。
2. **模型全局改写是现存危险行为。** 用户级文件被"备份-改写-恢复"（modelswap.py），影响面跨仓库与全部手工会话；派发器被迫"同轮同模型"降级（dispatch.py:402-414），吞吐受限且竞态窗口仍在。方案 P4 修的是**已存在的事故面**，不是预防性设计。
3. **主树双重角色。** 人工工作区与协调中枢同居一树，机器卡状态提交混入人工分支历史（git log 证据）。多会话并行下此结构必然失控；方案 L0 让手工会话也进 worktree，同时顺带解决该纠缠。
4. **多产品单仓既成事实，四条产品线是既定路线。** 仓库已是多采集器产品单仓（CNC/CNC04/DHH02/DHH04/MZS01/LnkCollector_src），铁律 2 的契约清单（采集器/BFF/安灯/规则引擎）与用户声明的采集器/边侧工控/云端 SaaS/移动端规划一致。同仓多会话并行是刚需而非奢望。

**反论点与驳斥**（评审者自查）：

- *"多任务并行已存在（单 loop + N worktree + 槽位），何须多会话？"* —— 现有并行是**执行**并行；缺的是**人机混合**并行（架构师手工会话 + 常驻 loop + 多工程师同时在场）。且 P4 修复的用户级文件污染与是否多 loop 无关，独立成立。
- *"四产品线可分仓，分仓后各仓天然隔离。"* —— 即便分仓，本仓内部多产品线并行仍然存在；且用户级模型文件、机器额度协调问题跨仓存在，方案 L1 恰好覆盖。方案边界不依赖分仓假设，对两种打包策略都必要。
- *"等痛了再做不迟？"* —— 经验库 [parallel-sessions] 与 TASK-013 两条教训显示：痛的代价是分支污染与历史损坏，修复成本（stash/reset/revert）远高于本轮改造成本；且方案自身边界纪律良好，不会失控成"两个月重构"。

---

## 5. 合理性评估

### 5.1 值得肯定（建议原样保留）

| 方案组成 | 评价 | 依据 |
|---|---|---|
| L0/L1/L2 分层与责任边界（L0 不管全局、L1 不管归属） | 与现有代码组织一致（worktree/账本/卡状态三层本来就分离），改造可增量落位 | §2 映射表 |
| §15 文件边界 + §16 四条硬规则 + 总闸门句 | **全案最有价值部分**：直接对应本仓事故史（TASK-013 借机污染、[Phase2] 顺手重构教训），是防漂移的真实护栏 | lessons-learned 第 24 行等 |
| Rule 4"真实三 worktree 运行 ≠ 单元测试通过" | 与本仓 e2e 教训一致（"dry-run 永远发现不了执行器链路问题"） | lessons-learned [Phase2] |
| 复用优先（锁机制、运行时） | 可行：mkdir 锁模式在 modelswap/loop 两处已有 Windows 实战验证，P3 直接泛化即可 | §1 取证 |
| "L0 和 L1 必须作为一个完整施工包验收" | 正确：L0 孤立交付 = worktree 有了，安全仍靠约定，等于没改 | §3 断言 3/6 |
| ADR 四决策 + 显式废止清单 | 符合铁律 10；显式废止（Explicit Rejection）是本仓治理惯例（多份 lessons 皆因"旧结论未被显式作废"而反复踩坑） | 铁律 10、lessons 第 55/61 行 |
| 完工定义（§21）与最终报告格式（§20） | 符合铁律 3（禁止自行宣布完成）与铁律 11（报告可验证） | engineering-rules §3/§11 |

### 5.2 冻结前必须修订（A 清单）

- **A1（§4.1 框架纠正）**：改写为"账本已集中于主树 `.harness/runs/`（RUNS.jsonl + PIPELINE.jsonl 双账本、槽位互通）；P3 的实际工作是**跨进程写锁 + 临界区原子化 + 并发崩溃安全**，不是'提升为共享'"。同时把"双账本（dispatch/pipeline）统一保护"列入 P3 范围——方案全文未提 PIPELINE.jsonl，漏掉它则管线槽位仍可穿透额度。
- **A2（P4 设计定案，可行性已验证）**：原要求"前置验证 DSH 会话级模型选择能力"**已完成，结论：可行**（证据链见 §7）。P4 施工设计据此定案：①派发时生成每运行（per-attempt）设置副本——读全局 `~/.dsh/settings.yaml`、替换 `agent-default-model` 为本任务模型、写入该运行的运行目录（run_dir 已按任务+尝试隔离）；②`executor_argv` 增加 `--patch <patch.yml>`，patch 内容把 `settings` 条目重定向到该副本（`config: {path: <副本>, watch: false}`）；③全局文件**零写入**，无锁、无备份、无恢复路径，`modelswap.py` 的 swap/restore/锁在派发路径整体退役（保留 `read_selection` 等只读函数供对账用与否由施工定）；④手工会话可用同一机制（`dsh --patch` 是普通 CLI 参数，人手可用）。
- **A3（P5 语义补丁）**：写死三条：① ownership 键 = TaskId（非 attempt）；② attempt 重试链合法复用同一 worktree（`reset_worktree` 既有语义保留）；③ OwnerSession 变更仅允许发生在任务释放（blocked / awaiting-review / done）之后。否则施工者按 §2 图把 Owner 绑进 attempt 粒度，会打断现有重试机制并误伤 Gate F 回归。
- **A4（P1 入口工件与 enforcement）**：①指定手工会话的最小入口工件（建议 `start-session.py` 薄包装：`ensure_worktree` + `start-task` 上下文 + ownership 登记，三步全是既有能力的组合）；②把"禁止绕过"从规则落成机制——在 pre-commit hook 增加"提交发生地 = 已登记 worktree 且提交者 = 该任务 owner"校验（hook 已是全仓共享基础设施，属允许修改面 D/E 的最小延伸）。现状"约定即可靠"已被本仓证伪多次，只写规则不写机制等于没写。
- **A5（§10 协调根定位）**：在 P0 结论里**显式排除"用户级 runtime root"**。理由：①任务 ID 跨仓冲突（多仓共用一份 ownership/ledger 会互相污染）；②本仓已有教训——锁与被保护对象必须同层级（modelswap 锁在仓库级却保护用户级文件，正是现存设计瑕疵）。仓库级（沿用 `.harness/runs/` 目录语义）是唯一与现模型一致的位置，且方案 §16 Rule 2 禁止新建存储产品，更无理由另起炉灶。

### 5.3 建议补充（B 清单——登记入计划，不扩施工边界）

- **B1（worktree 回收）**：现存 TASK-008/009/010 陈旧 worktree 证明需要回收策略。归入 P3 崩溃恢复（slot 释放时同步判 worktree 可回收），不是新功能。
- **B2（主树只读依赖登记）**：worktree 会话经绝对路径读主树上下文与 skills。只读、可接受；P6 验证补一条"主树分支切换期间 worktree 会话读取不中断"。
- **B3（旧规则废止登记）**：lessons-learned 第 21 行"同一时间只允许一个 AI 会话操作仓库"在本方案落地时必须**显式废止并改写**（登记进 §20 报告与 ADR），否则新旧规则并存造成执行者矛盾。
- **B4（V 场景补两条）**：V9 重试链（并行负载下 attempt 复用同 worktree 的 reset 语义不破坏）；V10 主树卡状态提交与 worktree 会话并发互不干扰。
- **B5（append 交织风险点名）**：Windows 多进程对同一文件并发 append 无逐行原子保证——这正是 P3 锁必须覆盖账本**全部写操作**（含 append 路径）的原因；§5.2 已含要求，落实清单里点名防漏。
- **B6（ADR 目录矛盾）**：engineering-rules 铁律 10 说 ADR 放 `docs/adr/`（既有 5 份 ADR 全在此），AGENTS.md 速查表说 `docs/architecture/adr/`（空置）。按 AGENTS.md 原则 1 已上报；建议沿用事实惯例 `docs/adr/`，同步修 AGENTS.md 表述。方案 §18 的 D-Parallel-001~004 应编号为 ADR-006~009。
- **B7（回归命令固化）**：Gate F 的回归命令应写死 `python -m unittest discover -s .harness/tests -t .harness`（`-t .` 在 Python 3.14 下因 `.harness` 点开头目录必炸——lessons [dispatcher-mvp]）。

---

## 6. 风险清单

| # | 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | P4 会话级模型覆盖能力不存在（DSH 无参数、profile 不支持） | ~~中高~~ **已排除（§7 探针实证可行）** | ~~全案最大不确定性~~ 已消除 | 验证记录与实现设计见 §7 / A2 |
| R1b | 设置文件默认带文件监视器（watch: true），全局改写会热发布到正在运行的其他会话——现行 swap 方案的事故面比方案 §6 描述的更宽 | 高（现行设计下真实存在） | 高（运行中会话模型被中途换掉） | P4 落地即根治；patch 中显式 `watch: false`（§7 探针已验证该字段生效） |
| R1c | 探针发现现行派发默认模型的上游免费档已下线：`openrouter/deepseek/deepseek-v4-flash-0731:free` 现返回 404（"unavailable for free"，提示改用付费 slug `deepseek/deepseek-v4-flash-0731`）——dispatch.yaml 第 3 行的 `model` 今天派发即失败 | 已确认（探针第一轮实测命中） | 高（当前派发链路对默认模型已断） | 属配置修复，不在本方案边界内：**上报架构师改 dispatch.yaml 的 model 行**（付费 slug 或换 `cohere/north-mini-code:free`，后者探针已实测可用） |
| R2 | DSH 在进程启动瞬间读 settings（dispatch.py:402 注释）——即便覆盖能力存在，读取时点与 spawn 时序仍需对齐 | 中 | 中 | P6 V4 场景覆盖；spawn 侧保持"先配置后拉起"顺序 |
| R3 | 多写者对主树 git index 的卡状态提交竞争 | 低 | 中 | claim 锁覆盖"读状态→写→commit"整段临界区（git index.lock 只防同时写、不防 TOCTOU） |
| R4 | 四产品线若分仓，方案部分价值后移 | 低 | 低 | 必要性论证不依赖分仓假设（§4 驳斥 2） |
| R5 | P2"推荐结构"被施工者当新存储产品设计，漂移成"协调中心" | 中 | 高（正是方案要防的漂移） | A5 写死沿用 `.harness/runs/` 目录语义；§16 Rule 2 已禁 |
| R6 | 冻结版仍带着 §3 断言 1/2 的失实描述进入施工 | 中 | 中（P0 报告失真、工作量误判） | 本报告 A1 已给出改写文本 |

---

## 7. P4 可行性验证记录（模型会话覆盖 · 真实探针，2026-09-20）

本节是对 §0 判断 3 / 修订 A2 的取证与实证记录。验证目标：**执行器是否具备"每个会话各自用各自的模型、不碰共享全局配置"的原生能力**。

### 7.1 能力发现（静态取证）

| 能力 | 证据 |
|---|---|
| CLI 按次叠加配置层 | `dsh --help`：`--patch <path>` "extra patch-list overlay applied after the profile layer (repeatable)"（bin.js:85 同文） |
| 设置文件路径可按次重定向 | `dsh-settings-file` 的 `resolveSpec`（lib/index.js:31-41）："an explicit `path` wins, otherwise the document lives at `<harness home>/settings.yaml`"——settings 条目是 profile 树中的普通插件条目（组合树 dump 可见 `id: settings`），故 patch 可改其 `config.path` |
| 值优先级：文件层 > 组合层 | `dsh-settings` 模块 doc（lib/index.js:76-81）："layers schema defaults, the registrant's composition `base`, and the user document section, **in that order**"；`installSection` 把组合条目注册为 `base`，`scope.get()` 返回 `mergeLayers(base, userSection)` 解析值——**重定向后的会话文件即用户层，覆盖一切组合默认** |
| 文件监视器可关 | settings 条目 `config.watch`（默认 true，chokidar 热发布）；patch 中置 `false` 探针实证生效（§7.2 组合验证） |
| 组合层验证 | `dsh --profile headless --patch <p> --dump-config` 输出中 `settings` 条目成功带上 `path: <会话副本>` 与 `watch: false` |

### 7.2 运行时实证（真 headless 探针）

环境：全局 `~/.dsh/settings.yaml` 的 `agent-default-model` 为 `qwen-token-plan-cn/qwen3.8-flash`（其 API 密钥不在本环境——若会话按全局走必然认证失败，构成天然阴性对照）。

| 步骤 | 结果 |
|---|---|
| 1. 生成会话设置副本（全局内容 + `agent-default-model` 换为 `openrouter/deepseek/deepseek-v4-flash-0731:free`），patch 文件把 settings 条目指向该副本 | 副本与 patch 落临时目录，全局文件不动 |
| 2. 真实 headless 派发：`dsh --profile headless --patch <patch.yml> "Reply with exactly this token..."` | 失败，错误为 `PI_AI_ERROR: 404: This model is unavailable for free... use this slug instead: deepseek/deepseek-v4-flash-0731`——**错误精确命中探针副本里的模型**，证明请求确实按副本路由（顺带发现该免费档上游已下线，见 R1c） |
| 3. 副本模型换为 `cohere/north-mini-code:free` 重跑 | **成功**，会话返回精确探针令牌 `PROBE-OK-7f3a` |
| 4. 全局文件哈希前后比对（SHA256） | **一致，全局文件零改动** |
| 5. 探针产物清理 | 临时目录三个探针文件已删除 |

### 7.3 结论

**P4 可行，且实现为纯配置组合、零新基建、零全局写入**：

```text
派发时（spawn 侧，全在现有 run_dir 内）：
  读全局 settings.yaml → 替换 agent-default-model → 写 <run_dir>/settings.yaml
  写 <run_dir>/model.patch.yml（内容：settings 条目 path 指向上一行副本，watch: false）
  executor_argv 追加：--patch <run_dir>/model.patch.yml
```

- 全局文件全程只读 → 无锁、无备份、无恢复，"修改全局配置实现模型切换"这一被方案 §6 点名的危险行为**从机制上消失**；
- 两会话各自副本、各自模型，互不可见（`--patch` 是 CLI 参数，天然按进程生效）；
- `modelswap.py` 的 swap/restore/lock/maybe_restore 链在派发路径整体退役，dispatch.py:402-414 的"同轮同模型"降级与竞态注释一并作废；
- 方案 §6 的两条测试要求（A/B 双模型互不污染、全局基线不变）可直接复用本探针方法放大为正式验证。

附带发现（均已在 §6 风险表登记）：R1b 热发布危害、R1c 派发默认模型免费档已下线、以及另一条与本案无关的既有问题——headless profile 的 cordis.patch.yml 中 `mcp-codebase-memory` 条目在组合时报 "entry not found"（dump-config 实测，TASK-041 的 MCP 接线实际未加载，与 lessons [skills-mcp] "尚未端到端调通"记录一致）。此问题不在本方案边界内，仅登记上报。

## 8. 验收与治理一致性核对

| 方案要求 | 与本仓规则的一致性 |
|---|---|
| Gate A-G + 最终报告格式（§19/§20） | 符合铁律 3（状态只有完成/部分完成/阻塞 + 证据）、铁律 11（可验证要素） |
| §17 五段提交、每段可构建可测试 | 符合铁律 13（feature 分支 + PR + 架构师审核）与 lessons [TASK-024]（pathspec 限定提交面） |
| §18 ADR | 符合铁律 10；目录矛盾见 B6 |
| P6 真实并发验证 | 符合铁律 15 精神（真 headless 派发留证）；V7 崩溃恢复与现有 pid_alive/stale-lock 能力对接，复用而非重做 |
| 边界纪律 §15/§16 | 与经验库多条教训互证（[parallel-sessions]、[TASK-013]、[Phase2]） |

---

## 9. 结论与建议

1. **判定**：方案合理、必要、边界纪律优秀——批准作为施工契约的**底稿**。原唯一的可行性疑点（P4 模型会话覆盖）已实证为可行（§7），五处修订（A1-A5）中 A2 已升级为设计定案。
2. **冻结状态**：v1.1 冻结版已按架构师决定产出——`docs/superpowers/plans/2026-09-20-parallel-session-isolation-plan-v1.1.md`（A1-A5 + B1-B7 全部并入，修订处带版本标记，与 v1.0 差异可审计）。后续施工以 v1.1 为准。
3. **P4 实现照 §7.3 的机制落地**：per-attempt 设置副本 + `--patch` 重定向，全局文件零写入；modelswap 派发路径退役。
4. **待架构师处理的边界外挂账（开工前置）**：①**紧急**——现行派发默认模型的免费档上游已下线（§6 R1c，实测 404），今天派发即失败，改 dispatch.yaml 的 model 行即可（付费 slug 或换探针已验证可用的 `cohere/north-mini-code:free`），此为 P6 验证起跑的前置条件；②headless profile 的 MCP 接线未实际加载（§7 附带发现）；③ADR 目录规则矛盾（B6）。三项均已在 v1.1 附录挂账，不属本方案施工边界。

---

## 附：本报告的边界自查

- 未修改任何生产代码与任何配置文件（含全局 `~/.dsh/settings.yaml`——SHA256 前后比对一致）；仅产出本评审文档与一条经验沉淀。
- 未执行 dispatch/poll/loop（未跑 `--once` 类有副作用命令——遵照 lessons [Phase2] 对 `loop --once` 副作用的警告）。
- P4 可行性验证用的两轮探针为**直接调用执行器 CLI 的独立进程**（不占派发槽位、不改卡状态、不动主仓索引），产物（探针设置副本/patch 文件）已全部清理；会话日志落入用户级目录属执行器正常行为。
- 评审中发现的规则矛盾（ADR 目录，见 B6）与边界外问题（派发默认模型免费档下线、MCP 接线未加载）均已按 AGENTS.md 原则 1 上报，未擅自改动。
