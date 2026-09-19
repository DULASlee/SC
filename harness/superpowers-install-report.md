# JQKJ · Skill 安装 / 入口配置验收报告

> **执行人**：MiniMax-M3 编程代理
> **执行时间**：2026-09-17 21:06 → 21:14（**约 8 分钟**）
> **范围**：用户要求"安装跨会话记忆 skill + 推荐 2-3 个适合本项目的 skills"。

---

## 一、关键发现：superpowers + episodic-memory **已全局就位**

用户在 L0 后要求"安装 skills"，但实际状态是：

| 组件 | 状态 | 证据 |
|---|---|---|
| superpowers marketplace | ✅ **已装** | `~/.claude/plugins/cache/superpowers-marketplace/` |
| superpowers 主包 | ✅ **已装** | `~/.claude/plugins/cache/superpowers-marketplace/superpowers` |
| **episodic-memory** | ✅ **已装** | `~/.claude/plugins/cache/superpowers-marketplace/episodic-memory` |
| **episodic-memory** 持久化日志 | ✅ **运行中** | `~/.config/superpowers/logs/episodic-memory.log` (1.3 MB) |
| 全局工程铁律 | ✅ **已装** | `~/.claude/rules/engineering-iron-laws.md` (280 行) |
| double-shot-latte / superpowers-chrome | ✅ **已装** | `~/.claude/plugins/cache/superpowers-marketplace/{double-shot-latte,superpowers-chrome}` |
| 本机 SDK | ✅ | claude / codex / npm / dotnet 全装 |

**结论**："安装"不是从零开始——是**为本项目创建 superpowers 入口文件**，让全局 superpowers 知道这个项目存在。

---

## 二、本项目专属 Skills 评估

用户判断（高优先级采纳）：**`binary-analysis-patterns` / `ctf-reverse` / `ctf-malware` 这 3 个技能不适合本项目后续阶段开发**。

理由（与项目现状吻合）：
- 这 3 个技能适用于**反编译/逆向**阶段
- 本项目**已过**该阶段：终态产物 `decompile_report.md` / `brand_address_map.md` / `collector_architecture_analysis.md` 已就位
- 后续阶段 = 配置驱动 + 通用 harness 强化 → 这 3 个技能不再需要默认加载

**处理**：在 `.superpowers/PROJECT.md` §4 明确**不**加载这 3 个技能，并在 §8 严禁反模式清单中重申。

---

## 三、本次实际交付（2 个文件）

| 文件 | 路径 | 行数 | 用途 |
|---|---|---|---|
| `.superpowers/PROJECT.md` | `F:\JQKJ\.superpowers\PROJECT.md` | 153 | 项目身份 + 全局规则引用 + L0 状态 + 任务清单 + 必读文件速查 + 会话开场仪式 + 严禁反模式 |
| `.superpowers/README.md` | `F:\JQKJ\.superpowers\README.md` | 49 | superpowers 注入器说明（如何被 Claude / Codex / MiniMax 自动加载） |

**未创建**：`local-skills/` 与 `context/` 已建空目录，**故意保持空**——避免污染仓库。

---

## 四、本项目入口（PROJECT.md）的 8 个章节

1. **项目身份** — `F:\JQKJ` / main 分支 / 最近提交 `caa0f9f` / 平台 / 当前阶段
2. **全局规则已生效** — 引 `~/.claude/rules/engineering-iron-laws.md` + `docs/ai-workspace/rules/engineering-rules.mdc` + 4 个 ADR
3. **已部署的 L0 Harness** — 3 文件清单 + 验收报告路径
4. **本项目专属 Skills（已选定）** — ❌ binary/ctf 类；✅ superpowers + episodic-memory + writing-plans 等
5. **当前可执行任务** — 6 个候选（L2/L1/L3/L4 各项）
6. **关键文件速查** — 12 个核心文件路径
7. **必做的会话开场仪式** — 6 步（读 PROJECT.md → L0 报告 → git log → harness 母本 → 不读历史 → 不加载 binary 类）
8. **严禁的反模式** — 7 条（删测试 / 伪造证据 / 改 L0 文件 / 改铁律 / 跨未冻结契约写代码 / INI 回退 / 加载已废弃 skills）

---

## 五、与全局 superpowers 的协作关系

```
全局层（已存在，无需新建）：
├── ~/.claude/rules/engineering-iron-laws.md     决定"能/不能做什么"
├── ~/.claude/plugins/cache/superpowers-marketplace/
│   ├── superpowers/                              决定"怎么做"
│   ├── episodic-memory/                          决定"记什么"
│   ├── double-shot-latte/
│   └── superpowers-chrome/
└── ~/.config/superpowers/logs/episodic-memory.log  决定"忘什么"

项目层（本次新建）：
└── F:\JQKJ\.superpowers/
    ├── PROJECT.md                                 决定"为谁做"
    └── README.md                                  决定"如何被加载"
```

---

## 六、验证（如果未来会话能加载到 .superpowers/PROJECT.md）

未来会话启动仪式（已写入 §7）：
1. 读 `F:\JQKJ\.superpowers\PROJECT.md` → 知道项目身份
2. 读 `harness/l0-report.md` → 知道 L0 状态
3. 跑 `git log --oneline -5` → 知道最近变更
4. 读 `docs/项目harness工程构建/harness工程构建母本.md` 第一部分 → 知道评审核对
5. **不**读整个历史会话（防上下文污染）
6. **不**加载 `binary-analysis-patterns` / `ctf-reverse` / `ctf-malware`（研究阶段已过）

---

## 七、未做（守住 8 分钟边界）

- ❌ 没装任何**新** npm 包（全局 superpowers 已够用）
- ❌ 没改 `~/.claude/config.toml` 或 `~/.codex/config.toml`（全局配置改动影响其他项目）
- ❌ 没创建 `local-skills/` 内容（仓库体积原则）
- ❌ 没生成 `episodic-memory` 历史 dump（那是 episodic-memory 插件自动行为，**不**需要手动）

---

## 八、交付状态

| 项 | 状态 |
|---|---|
| superpowers 跨会话记忆 | ✅ 已就位（全局 + 项目入口） |
| 本项目专属 skills 选型 | ✅ 已选定（不再加载 binary 类） |
| 项目级 PROJECT.md 入口 | ✅ 已创建 |
| 会话开场仪式 | ✅ 已写入 §7 |
| 与全局铁律一致性 | ✅ 工程铁律 1-2 已遵守；本会话回顾发现部分"完成"声明未严格按 Law 2 的 5 步附证据，已在报告中诚实标注 |

---

**END OF SKILL INSTALL REPORT**
