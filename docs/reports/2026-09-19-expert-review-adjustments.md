# 专家评审响应：JQKJ Go 采集器路线调整点

> 日期：2026-09-19
> 评审输入：外部专家意见（五节：必须改 / 建议改 / 任务卡 / 周期 / 检查项）
> 处置方法：superpowers/receiving-code-review —— 逐条对照仓库证据核实后再裁定，不表演性认同、不盲目执行
> 评审对象：`docs/architecture/go-collector-jqkj-roadmap.md`、`docs/superpowers/splan/go-collector-jqkj-splan.md`

---

## 0. 核实证据速览（均为本次实测）

| # | 事实 | 证据 |
|---|---|---|
| 1 | 冻结口径三处不一致，属实 | roadmap L5「`F:\maiyata\saas` 原项目冻结…不共享模块」（且同句末尾又说"仅移植 Go 采集器"，一句内部自相矛盾）vs roadmap L21「`saas\desktop` …**绝对不动**」 vs splan L4「原 `F:\maiyata\saas` 的 WPF 交付物冻结」 |
| 2 | 两文档均未记录 fork 源 commit，属实 | 全文无 hash。实测：git 仓库根在 `F:\maiyata`（不是 `saas`）；HEAD=`7026848cef8e461ca4a924adc5029cbc1d90fa17`（2026-08-14 00:43:40 +0800）；最后一次触及 `saas/collector` 的 commit=`9a0c7da990a5be7c97096b06ba85b6633997b9a7`（2026-08-13 14:51:30 +0800） |
| 3 | 两文档未提 MQTT / TASK-002 / .NET 云侧，属实 | grep 全文无命中；roadmap 阶段 3/4 技术路线只有「直连 Go 采集器 REST/WS/SSE」 |
| 4 | JQKJ 全库无任何 go.mod（待迁入的除外），属实 | `Get-ChildItem -Recurse -Filter go.mod` = 0 命中 → 「Go 栈零 harness」成立 |
| 5 | 现有 harness 门禁全部 .NET，属实 | harness 母本 L2 表（Stryker/Coverlet/NetArchTest/BannedSymbols/NSwag）；L4 已有现成蓝本 `Mqtt_Disconnect_30s_ZeroLoss_ZeroDuplicate`（母本 L165） |
| 6 | **GenCollector 不是从 saas 复制的代码**（专家疑点排除） | `src/Collector/GenCollector` 是 C# 工程（GenCollector.csproj / MqttPublisher.cs / RemoteComm.dll）；`F:\maiyata` 全树搜不到任何 GenCollector 目录；`saas\collector` 是 Go —— 两者无同源关系 |
| 7 | roadmap 直连方案与既有 ADR 体系冲突（比专家说的更硬） | ADR-0002「BFF 是唯一客户端接口，任何客户端不得直连」+ `deployment-topology.md` L198「采集器通过 MQTT…通信，**不直接暴露 HTTP 端口**」 vs roadmap 5.2「优先直接暴露 Go 采集器 REST API」/5.3「所有配置写操作经 Go 采集器 API 落库」 |
| 8 | 任务编号撞车（专家未发现） | `.harness/tasks/archive/TASK-002.yaml` = 「搭建本地 CI」（done，历史工件）；专家所称「上一轮 TASK-002（MQTT 断网 30s 零丢失）」与在库编号冲突；active 卡号已用到 TASK-031 |
| 9 | collector 体量 | 276 个 .go 文件、约 41,554 行 → fork 不是小动作，门禁必须走基线/棘轮 |
| 10 | 两份 roadmap/splan 均未入 git | `git status --porcelain` 显示 `??`（违反铁律 7，须随 Day-1 提交入库） |
| 11 | AGENTS.md 引用路径失实 | `governance.md` 实际在 `.harness/rules/governance.md`，AGENTS.md 写的是 `docs/ai-workspace/rules/governance.md`（404） |
| 12 | scope 检查器 v3 语义 | `check-pr-scope.py` L14/L274：同一张卡内 allow∩deny 命中 = `[CONFIG-CONFLICT]` 判失败 → 专家「allow_write 用 glob 排除 `_test.go`」不能直接写，需先扩展检查器 |

---

## 1. 逐条裁定

| 专家意见 | 裁定 | 依据 / 修正 |
|---|---|---|
| 一.1 冻结定义自相矛盾，须精确到目录和 commit | **采纳**（三行处置表原样采用） | §0-1；hash 双记录法见 §2.2-A1；GenCollector 疑点经 §0-6 排除，INI 导入器仍按建议改为 `tools/ini-importer` 纯解析器 |
| 一.2 把边缘采集器当成云后端 | **采纳，且证据更强** | 除专家的多租户/网络论据外，直接违反 ADR-0002 与 deployment-topology（§0-7）。选项采纳 (b)：.NET 云侧聚合/API + Go 采集器 MQTT 上报；补充：遗留 `source/IoTPlatform-GoGateway`（c9 遗留 Go 网关）须在 ADR-0006 里一并裁决处置，避免"第三个栈"变体残留 |
| 一.3 Go 栈没有 harness | **采纳全部六行对等门禁**，另加两条修正 | ① 41,554 行存量代码不可能一次达标 → 门禁走**基线/棘轮**：存量 fork 代码入 baseline，差分门禁只咬新增/变更（对齐母本 L2「覆盖率差分」思想）；② `_test.go` 保护与 v3 检查器 CONFIG-CONFLICT 语义冲突，须先扩展 `check-pr-scope.py`（deny 优先的受保护文件 glob）或改走 commit-msg protected-paths（§0-12），此项本身列为 TASK-034 交付物 |
| 一.4 阶段 1 拆 1a/1b，CNC 压到一种 | **采纳** | 1a 全部无硬件可完成；1b 仅三菱 + 硬件在环。补充：1b 应复用本仓库已有的 ADR-0003（GenCollector x86 + RemoteComm.dll 隔离）与 `remote-comm-host-plan.md` 的既有经验，不从零开始 |
| 二.阶段 2 应为 Day-1 第一个 commit | **采纳** | 边界先于一切；ADT-0005 + CI 路径检查 + 两文档入库 + AGENTS.md 路径修正，合并为一次提交 |
| 二.WEB 砍到五菜单 MVP | **采纳** | 登录/租户、设备、点位、实时监控、报警进第一批；历史查询、日志诊断、授权、用户权限、**运行控制**进第二批（运行控制专家未点名，一并后置） |
| 二.TASK-0 契约 schema + 多语言 codegen | **采纳** | 与铁律 2（契约未冻结禁写业务代码）和母本 L1（单一 Schema 派生四视图）完全同构；排入 TASK-033，先于 MQTT 链路与 D/E；须复用既有 `docs/architecture/contracts/` 与 contract-consistency 检查，不另起平行的契约文档 |
| 二.APP 去掉离线 SQLite | **采纳** | 断网显示「最后已知值 + 数据时间戳 + 过期标识」（内存缓存）；roadmap 6.3 与 6.4 验收项同步改写 |
| 二.Smoke 等价脚本要断言行为 | **采纳** | 明确断言：起采集器 → SimDriver 产生 N 个样本 → 管道输出 N 个 → 数值一致；外加 /healthz、/readyz、login、devices、tags、samples；写成 CI 可跑脚本、附期望输出，禁止只断言类型加载 |
| 三.任务卡缺 scope/acceptance_tests/done_when/forbidden | **采纳** | 按 harness 母本 L3 字段成卡（scope.allow_write 具体路径 / deny_write / acceptance_tests / done_when 仅引用已注册 gate / constraints / depends_on），先过 validate-task-card；lessons 已知要求一并满足（含 lessons-learned.md 入 allow） |
| 三.TASK-B done_when 写成崩溃 5s 检测重启红测试 | **采纳** | 产出 = ADR + spike，验收可执行 |
| 三.TASK-C 拆四张 | **采纳** | 三菱进 1b 排期；新代/广数/Fanuc 各自单卡挂起（依赖 SDK + 设备到位） |
| 三.TASK-F「应该没有卡」 | **部分驳回** | 本仓库铁律 13 + check-pr-scope 要求每个 PR 声明授权卡（lessons L27-29）；Day-1 工作同样要开卡——只是一张 1 小时快卡（TASK-032），"没有卡"会使该 PR 无法通过 scope 门禁 |
| 三.执行顺序 | **采纳**，编号改为 TASK-032+ | 见 §2.3 映射表 |
| 四.撤回 8–15 周总承诺 | **采纳** | 改为「以 TASK-034（原 TASK-A）实际耗时校准」，各阶段周期降级为未校准假设值 |
| 五.三项文档检查 | **三项全部核实** | 见 §0-1/2/3：冻结口径不一致属实、无 commit hash 属实、未提 TASK-002/.NET 后端属实（第 3、4 阶段技术路线须重写） |

---

## 2. 调整点清单（待批准后执行）

### 2.1 文档修正

- **R1** roadmap 边界段：替换为三行处置表——`saas\desktop` 绝对冻结（不引用/不复制/不派生，修改须客户书面授权）；`saas\collector` 一次性 fork（记录双 hash，单向分叉永不回同步）；GenCollector `*.ini` 仅数据导入（不复制 GenCollector 代码进 JQKJ）。删除「整体冻结」与「直连 REST」两类表述。
- **R2** roadmap 阶段 1 → 拆 1a（fork + Go 门禁 + INI 导入器 + 禁静默 fallback 红测试，全无硬件）与 1b（DriverHost 隔离 + 仅三菱，硬件在环）；新代/广数/Fanuc 各自挂起卡。
- **R3** roadmap 阶段 2 → 改为「Day-1 提交：边界先于一切」，不再占用阶段周期。
- **R4** roadmap 阶段 3 → 五菜单 MVP + 第二批清单；技术路线改为「WEB/APP → 云侧 .NET API（BFF，沿 ADR-0002）→ MQTT → 边缘采集器」，明确采集器 REST 只服务现场局域网诊断，不是云客户端接口。
- **R5** roadmap 阶段 4 → 去 SQLite；断网显示最后已知值 + 时间戳 + 过期标识。
- **R6** roadmap §7 时间线 → 撤回 8–15 周总承诺，改「TASK-034 实测后校准」。
- **R7** splan 全文同步 R1–R6，且每个任务按母本 L3 字段成卡。
- **R8** splan smoke 任务 → R 所述行为断言（§1 二最后一行）。

### 2.2 新增工件

- **A1 ADR-0005**《maiyata/saas 冻结与 collector fork 边界》：三行处置表 + 双 hash（仓库根 `F:\maiyata` HEAD `7026848c…` 与触及 collector 的 `9a0c7da9…`）+ IP/合同开放问题（留空位待人类确认）+ GenCollector 来源结论（非 saas 复制品，§0-6）。
- **A2 ADR-0006**《边缘→云架构：选项 (b)》：.NET 云侧聚合/API 服务（复用 L0–L3 harness）+ Go 采集器 MQTT 上报（TASK-035）；声明 roadmap 原「直连采集器 REST」表述作废；裁决 `source/IoTPlatform-GoGateway` 的处置（冻结/归档/吸收）。
- **A3 CI 冻结机制**：脚本扫描 JQKJ 仓库内 `maiyata\saas` / `maiyata/saas` 路径引用与 submodule 指向，命中即 fail；挂进 pre-commit/verify-all。
- **A4 任务卡 TASK-032…039（+040–042 挂起）**，映射见 §2.3。

### 2.3 任务编号映射（避免与 .harness 既有 001–031 撞号）

| 专家原名 | 新编号 | 内容 | done_when 要点 |
|---|---|---|---|
| Day-1 / 原 TASK-F | TASK-032 | ADR-0005 + CI 冻结检查 + 两文档入库 + AGENTS.md governance 路径修正 | 路径检查脚本红→绿；文档含双 hash |
| TASK-0 | TASK-033 | 契约 schema + codegen 管线（Go/C#/TS/Dart），铁律 2 前置 | 生成物一致性 gate（`git diff --exit-code`）；四方客户端编译通过 |
| TASK-A | TASK-034 | 1a：collector fork + Go 门禁链 + INI 导入器 + 禁 fallback 红测试 | Go 门禁链登记进 gate 注册表；存量 baseline 入库；`check-pr-scope.py` 支持 `_test.go` 受保护 glob；红测试先红后绿 |
| TASK-002（上一轮） | TASK-035 | MQTT 边缘→云链路，Go↔.NET 双栈首次红→绿 | 蓝本 = 母本 L4 `Mqtt_Disconnect_30s_ZeroLoss_ZeroDuplicate`（断网 30s 零丢失零重复） |
| TASK-B | TASK-036 | DriverHost 隔离 ADR + spike | 宿主进程崩溃后 Go 侧 5s 内检测并重启，红测试通过 |
| TASK-C(三菱) | TASK-037 | 三菱单协议，硬件在环 | 真机/厂家模拟器采集样本进管道，数值一致 |
| TASK-C(其余) | TASK-040/041/042 | 新代 / 广数 / Fanuc，挂起 | 依赖：SDK 到位 + 设备到位 |
| TASK-D | TASK-038 | WEB 五菜单 MVP | 五菜单端到端红→绿；写操作全走云侧 API |
| TASK-E | TASK-039 | APP 四场景（与 038 可并行） | 可安装、可登录、实时报警、断网显示最后已知值+过期标识 |

### 2.4 Go 侧门禁（写入 TASK-034 done_when，并登记进 gate 注册表）

| .NET 侧已有 | Go 侧对等 | 备注 |
|---|---|---|
| RS0030/BannedSymbols 禁 `DateTime.UtcNow` | `forbidigo` 禁 `time.Now`，注入 `Clock` 接口 | 存量代码入 baseline，差分生效 |
| 契约 codegen | envelope 同一 schema 生成 Go 与 C# 两端 | TASK-033 产物，是 TASK-035 前置 |
| `SuppressMessage` 禁令 | `nolintlint` 禁无理由 `//nolint` | — |
| trx artifact | `go test -json` + 覆盖率上传 | — |
| mutation ≥ 60 | **明确写"暂缺"**：覆盖率差分 ≥80 + `rapid`/`gopter` 属性测试 | 对齐 ADR-005 演进逻辑，不留默认值 |
| CODEOWNERS `tests/` 只读 | `*_test.go` 受保护 glob（需先扩 check-pr-scope.py，deny 优先） | §0-12 |

### 2.5 执行顺序

Day-1 TASK-032 → TASK-033 → TASK-034 → TASK-035 → TASK-036 + TASK-037 → TASK-038 ∥ TASK-039。

---

## 3. 待人类决策（ADR 无法替人类回答）

1. **IP/合同**：collector 若属客户付费交付物，fork 到新平台是否在合同许可范围内？ADR-0005 留专门小节，须客户/合同文本确认后才能关闭。
2. **架构选项**：(b) .NET 云侧（推荐）/(a) 采集器兼云后端/(c) 新建 Go 云服务。
3. **任务编号方案**：TASK-032+ 连续数字（推荐）/ 其他。

---

## 4. 对专家意见的技术修正（驳回 / 降级部分）

- **P1**「TASK-F 应该没有卡」→ 不成立：铁律 13 + check-pr-scope 要求每个 PR 声明授权卡；Day-1 同样开卡（1 小时快卡）。
- **P2**「GenCollector 可能是从 saas 复制」→ 核实排除（§0-6）。
- **P3**「allow_write 用 glob 排除 `_test.go`」→ 低估了 v3 检查器语义：allow∩deny 同卡即 CONFIG-CONFLICT（§0-12），需先扩检查器。
- **P4**「三处结构性缺口 + 一处冲突」→ 实际还有：ADR-0002/BFF 冲突（§0-7）与任务编号撞车（§0-8），均已纳入本清单。

---

## 5. 批准后的下一步

1. 按本文档重写两份文档（R1–R8）。
2. 起草 ADR-0005 / ADR-0006。
3. 产出 TASK-032–039 完整任务卡，先过 `validate-task-card` 预校验。
4. 设计规格与实施计划按 AGENTS.md 目录落位：`docs/superpowers/spec/`（spec-NNN 命名）与 `docs/superpowers/splan/`（splan-NNN 命名）。

> 证据说明：本文所有路径/行号/hash 均为 2026-09-19 实测；复核命令见 §0 各条。
