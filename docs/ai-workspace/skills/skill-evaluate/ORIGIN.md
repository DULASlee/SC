# skill-evaluate — Origin & License

## 来源（已字节比对验证）

| 项 | 值 |
|---|---|
| 名称（frontmatter `name`）| `skill-evaluate` |
| 唯一可信源 | `https://github.com/artemrudenko/skill-governance-toolkit/blob/main/skills/skill-evaluate/SKILL.md` |
| 字节比对 | `[OK] byte-identical after CRLF normalization`（18,833 = 18,833）|
| 集成日期 | 2026-09-19 |
| License | **MIT**（同 toolkit 共用 LICENSE，2026 Contributors）|
| 仓库 License | MIT |
| 维护状态 | artemrudenko/skill-governance-toolkit 134 commits，活跃 |

## 兼容性

`compatibility: "Claude Code · GitHub Copilot · Cursor v2.2+ · OpenAI Codex CLI · Google Gemini CLI"`（同 skill-find）—— OpenCode 通过 `.opencode/skills/` 隐式兼容。

## 9 维评分框架（D1–D9）

| Dim | 名称 | 衡量 |
|---|---|---|
| D1 | Clarity | 表达清晰度 |
| D2 | Completeness | 完整性 |
| D3 | Specificity | 指令明确度 |
| D4 | Examples | 示例充分性 |
| D5 | Constraints | 边界约束 |
| D6 | Portability | 跨 harness 可移植性 |
| D7 | Testability | 可测性 |
| D8 | Discoverability | 描述触发率（实测 well-formed ~90% vs vague ~20%）|
| D9 | Safety/Risk Awareness | **安全意识**（6 子项：blast radius / prompt injection / sensitive data / authz / rollback / idempotency）|

**总评公式**：`Total = D1..D9 (max 45)` → `Score = round(Total / 45 × 100)`

**4 个风险等级**：🟢 Green 80-100 / 🟡 Yellow 60-79 / 🟠 Orange 40-59 / 🔴 Red 0-39

**硬安全门**：D9 ≤ 1（且 skill 改外部状态）+ 任一 🔴 lexical finding → 强制 🔴 Red（无视数值）

## 与 skill-find 的关系

- `skill-find` 跨库搜索匹配自然语言需求（**路由器**）
- `skill-evaluate` 对单个 SKILL.md 打 0-100 分（**质量门**）
- `skill-find` 读 `skill-evaluate` 写入的 `out/scores/index.jsonl` 作为质量分参考
- 两者**互相独立**——skill-find 是 entry-point，skill-evaluate 也是 entry-point

## 关键设计原则（从 SKILL.md 抽取）

1. **Self-exclusion**：`skills/skill-evaluate/**` 自身豁免 Phase 3.5/3.6/3.7/3.8 自检（否则会自指）
2. **Phase 3.5 dependency**：依赖 `skills/library-audit/references/security-spec.md`——**未装 library-audit 时 Phase 3.5 降级到只标记 inline-obvious secrets 并打印 degradation 日志**
3. **Rewritten version only on demand**：`REWRITE=true` 才生成改进版，**绝不静默覆盖源 skill**
4. **Score 是 SOURCE 的，不是 REWRITE 的**：要给 rewrite 打分需重新 invoke skill-evaluate
5. **Resumable runs**：大 skill 在 P1/P3/P5 写 checkpoint，崩溃可恢复
6. **Lexical security mask**：匹配到的 secret 永远 mask 成 `sk-...REDACTED...XyZ`，永不打印原文

## 与本项目其他 skill 的协同

| 已装 skill | 关系 |
|---|---|
| `discernment-nudge` | 正交——nudge 推动用户回头查答案，evaluate 评估答案生成规则本身 |
| `skill-find` | skill-find 读 evaluate 的 `out/scores/index.jsonl`——但本项目目前**未启用**这个持久化路径（`SAVE_SCORE=true` 默认开） |
| `skill-scout` | 独立——evaluate 不依赖 scout；scout 的未来见 lessons-learned 退役审计 |

## 集成到本项目的实际价值

- **立即可评分的对象**：本项目 `docs/ai-workspace/skills/` 下的 3 个 SKILL.md（`discernment-nudge` / `skill-find` / `skill-evaluate`）
- **建议用法**：每次新装一个第三方 skill 后，跑一次 skill-evaluate 给 D1-D9 评分，作为接受/拒绝的依据
- **潜在升级**：可选装 `library-audit` 让 Phase 3.5 不降级——但 `library-audit` 是整库扫描工具，对 3 个 skill 来说过重

## 维护建议

- 触发词（用户可主动调用）："evaluate skill X", "score this skill", "review SKILL.md", "is this skill production-ready"
- 上游：none（entry-point），可与 skill-find 组合（find 后立刻 evaluate）
- 输出位置：`out/skill-evaluate/{SKILL_TARGET}-{YYYY-MM-DD}.md`