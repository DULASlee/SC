# JQKJ 项目 · Superpowers 入口

> **本文件是项目级 superpowers 入口**。任何新会话（Claude / Codex / MiniMax / 其他）启动时，**先读本文件**，再决定加载哪些 skill。
>
> **本文件不替代**：`docs/项目harness工程构建/harness工程构建母本.md`（harness 设计）、`docs/architecture/adr/`（架构决策）、`docs/ai-workspace/rules/engineering-rules.mdc`（项目铁律）。

---

## 1. 项目身份

| 项 | 值 |
|---|---|
| 项目根 | `F:\JQKJ` |
| 分支 | `main` |
| 最近提交 | `caa0f9f` — fix: restore Shift-JIS tests, add CodePages package, fix atomic backup test |
| 平台 | Windows + .NET 8 + 多 SDK（6/8/10）并存 |
| 项目阶段 | **重建期**：已完成研究/反编译阶段（终态产物：`collector_architecture_analysis.md`、`decompile_report.md`、`brand_address_map.md`），进入**配置驱动 + 通用 harness**实施期 |

---

## 2. 全局规则已生效

本项目已启用**两层规则**：

### 2.1 全局工程铁律（来自 `~/.claude/rules/engineering-iron-laws.md`）

- **Law 1 — No Escalation**：遇到 bug 不绕过、不甩锅，**当场修**。
- **Law 2 — Verification is Completion**：完成声明必须附 5 步证据链（IDENTIFY → RUN → READ → VERIFY → CLAIM）。**禁止**说"应该"、"大概"、"看起来"，**禁止**只跑测试不读输出就声称完成。
- Law 3-10（具体内容见全局文件）同等适用。

### 2.2 项目级工程铁律（来自 `docs/ai-workspace/rules/engineering-rules.mdc`）

- 契约优先（OpenAPI / AsyncAPI / MQTT / data-models 未冻结前禁写业务代码）
- 禁止自报完成（必须附证据）
- 禁止删除测试掩盖问题
- 禁止静默回退（JSON 损坏必须报错，不准回退 INI）
- 禁止跨文档字段漂移（同名字段同名同类型同枚举）
- 所有交付物入 Git
- 所有构建固定平台目标（GenCollector 必须 `--arch x86`，CI 必须 `win-x86 --self-contained`）
- 所有敏感信息不得明文（用 `${ENV_VAR}` 占位符）
- 所有决策必须留 ADR（`docs/architecture/adr/`）
- 所有报告必须可验证（文件路径 + 命令 + 输出 + commit hash + 测试结果）

### 2.3 强制约束（基于本仓库 ADR）

- **ADR-0003**：GenCollector / GenCollector.Tests **必须 `--arch x86`**；短中期内直接 P/Invoke RemoteComm.dll（32 位）。
- **ADR-0004**：JSON 是主配置格式；INI 仅作迁移期回退；JSON 损坏**报错退出**，不准静默回退 INI。
- **契约一致性**：本项目已发现 7+ 处契约漂移（见 `contract-consistency.md`），**未冻结前禁止写跨契约业务代码**。

---

## 3. 已部署的 L0 Harness（2026-09-17）

| 文件 | 作用 |
|---|---|
| `Directory.Build.props` | 仓库级 MSBuild：x86 条件平台目标 / TreatWarningsAsErrors / Nullable=disable / Roslynator 3.1.0 分析器 |
| `.editorconfig` | UTF-8 + LF + 4 空格；INI 强制 CRLF |
| `BannedSymbols.txt` | 禁用 API 列表（占位：依赖的 `BannedApiAnalyzer` 不在 nuget.org，**触发路径待 L2 Roslyn Analyzer 自发布补齐**） |

**L0 验收报告**：`harness/l0-report.md`（含 7 工程 0 errors + 40 测试全过）。

---

## 4. 本项目专属 Skills（已选定）

按 2026-09-17 用户判断，**以下 3 个 binary/reverse/malware 技能不适合本项目后续开发阶段**（已过研究阶段）：

- ~~`binary-analysis-patterns`~~
- ~~`ctf-reverse`~~
- ~~`ctf-malware`~~

**当前会话可用、本项目适用**的 skills：

| Skill | 来源 | 适用场景 |
|---|---|---|
| `using-superpowers`（含 `episodic-memory`） | 全局 marketplace | 跨会话持久记忆 + 项目级铁律执行 |
| `writing-plans` / `writing-skills` | 全局 marketplace | 任务卡 / 新 skill 编写 |
| `verification-before-completion` | 全局 marketplace | 完成前 5 步证据链 |
| `requesting-code-review` | 全局 marketplace | PR 提交前自检 |
| `subagent-driven-development` | 全局 marketplace | 任务编排 / 并行子代理 |

> **未来如需新增 skills**，按 superpowers marketplace 流程安装到 `~/.codex/skills/` 或 `~/.claude/plugins/`，**不**直接放到本项目 `.superpowers/local-skills/`（避免污染仓库体积）。

---

## 5. 当前可执行任务（按"半小时边界"排序）

| 任务 | 估算 | 依赖 | 备注 |
|---|---|---|---|
| **L2-A**：把 `Roslynator.Analyzers` 启用全规则集（导出 `.editorconfig`） | 30-60 分钟 | L0 已完成 | 触发大量既存警告，需逐文件消解 |
| **L2-B**：自发布 Roslyn Analyzer（~30 行）拦截 `Encoding.Default` + `Thread.Sleep(int)`，绕开 nuget 缺包问题 | 1-2 小时 | 需新建 `IoTPlatform.Analyzers` 项目 | 真正激活 BannedSymbols.txt |
| **L2-C**：CI 接入（`.github/workflows/build.yml`） | 1 小时 | L0 已完成 | 跑 `dotnet build -warnaserror` + `dotnet test` + artifact 上传 |
| **L1-A**：把 4 份手写契约收敛为 1 个 Schema（JSON Schema 或 .proto） | 1-2 周 | 需先冻结契约 | 引用 `contract-consistency.md` 的 7+ 处不一致 |
| **L3-A**：把 `tests/` 物理分离 + `CODEOWNERS` 强制人工审批 | 2-3 小时 | 需先决定 CODEOWNERS 名单 | 防止实现者删测试 |
| **L4-A**：1 个 Testcontainers + Toxiproxy 故障注入样板测试（红着进 CI） | 2-3 小时 | 需 Docker | 把"可靠性文档"变成 CI 红灯 |

---

## 6. 关键文件速查（任何会话都该先看）

| 路径 | 用途 |
|---|---|
| `README.md`（**缺失** — 待补） | 项目门面 |
| `docs/项目harness工程构建/harness工程构建母本.md` | 评审原文 + 我的事实核对 + 落地优先级 |
| `docs/architecture/adr/ADR-0001..0004-*.md` | 已通过的架构决策 |
| `docs/architecture/contract-consistency.md` | 7+ 处契约不一致清单 |
| `docs/superpowers/plans/2026-09-17-*.md` | 阶段计划 |
| `docs/superpowers/reports/2026-09-17-*.md` | 阶段报告 |
| `docs/superpowers/specs/2026-09-17-*.md` | 设计规格 |
| `collector_architecture_analysis.md` | 采集器家族架构分析（终态） |
| `decompile_report.md` | 反编译报告（终态） |
| `brand_address_map.md` | 全品牌地址映射（终态） |
| `harness/l0-report.md` | L0 harness 验收报告 |
| `docs/ai-workspace/rules/engineering-rules.mdc` | 项目级铁律 |
| `.gitignore` | 已含 secrets/、backups/、TestResults/ 等 |

---

## 7. 必做的会话开场仪式（防止历史丢失）

每个**新会话**启动时：

1. 读本文件（`F:\JQKJ\.superpowers\PROJECT.md`）
2. 读 `harness/l0-report.md` 确认 L0 状态
3. 读 `git log --oneline -5` 看最近提交
4. 读 `docs/项目harness工程构建/harness工程构建母本.md` 第一部分（评审核对）
5. **不读**整个历史会话（避免上下文污染）
6. **不加载** `binary-analysis-patterns` / `ctf-reverse` / `ctf-malware`（已判定不适合后续阶段）

完成 6 步后**才**开始处理用户的新请求。

---

## 8. 严禁的反模式

- ❌ **删测试掩盖警告**（铁律 §4）— 写新测试或修代码，不删旧测试
- ❌ **伪造 evidence/*.json**（评审 R4）— 证据必须由 CI 产出
- ❌ **修改 `Directory.Build.props` 加业务 Property** — 该文件是 L0 产物，仅 L2+ ADR 可扩展
- ❌ **修改 `docs/ai-workspace/rules/engineering-rules.mdc`** — 项目铁律，需 ADR 升级
- ❌ **跨多个未冻结契约写代码**（铁律 §2） — 需先冻结契约
- ❌ **回退 INI** 当 JSON 损坏（ADR-0004）— 必须报错退出
- ❌ **加载 binary-analysis-patterns / ctf-reverse / ctf-malware** 到本项目会话（研究阶段已结束）

---

**END OF PROJECT ENTRY**
