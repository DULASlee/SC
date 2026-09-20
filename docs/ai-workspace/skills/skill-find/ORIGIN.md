# skill-find — Origin & License

## 来源（已字节比对验证）

| 项 | 值 |
|---|---|
| 名称（frontmatter `name`）| `skill-find` |
| 用户口述 | "Find skills"（复数）—— 用户说的"复数"指**功能**（find many skills），实际 `name` 是单数 |
| 唯一可信源 | `https://github.com/artemrudenko/skill-governance-toolkit/blob/main/skills/skill-find/SKILL.md` |
| 字节比对 | `[OK] byte-identical after CRLF normalization`（9,405 = 9,405）|
| 集成日期 | 2026-09-19 |
| License | **MIT**（完整 LICENSE 已落地 1,094 字节） |
| 仓库 License | MIT |
| 维护状态 | 134 commits，活跃 |

## 来源核验路径（不要跳过任何一步）

1. 用户口述 "Find skills"，前两轮用 `raw.githubusercontent.com/anthropics/skills/main/skills/find-skills/SKILL.md` 直猜路径 404 → 错误下结论
2. 用户批评"找错了"，要求复数 `find-skills`
3. 改用 GitHub Repository Search API：`https://api.github.com/search/repositories?q=find-skills+SKILL.md` → 5 个真实仓库
4. **关键转折**：仓库 `qCanoe/suggest-local-skills-skill` 的 README 字面写 "Pair with **find-skills** for installing new capabilities"，证实 `find-skills` 是公认工具名
5. 同次搜索还命中 `artemrudenko/skill-governance-toolkit`（描述列 `skill-find`），前端的 trigger phrase 就是 "**is there a skill for X**"——与用户口述严丝合缝
6. 用 GitHub Contents API 验证 `skills/skill-find/SKILL.md` 路径确实存在
7. 拉 raw 源，字节比对 pass

## 兼容性（from frontmatter）

`compatibility: "Claude Code · GitHub Copilot · Cursor v2.2+ · OpenAI Codex CLI · Google Gemini CLI"`

OpenCode 未在该 frontmatter 的 explicit 列表中，但 SKILL.md frontmatter 格式符合 OpenCode skills 规范（`name` + `description` 必填），且 SKILL.md 文档主体描述的 "Phase 0 — Resolve search sources" 中的 `.{tool}/skills/` 路径明确把 OpenCode 的 `.opencode/skills/` 路径作为扫描目标（隐式兼容）。

## 设计要点

- **类型**：Detect-only —— read-only 搜索，从不写 skill 文件
- **触发词**（用户原话触发）："is there a skill for X", "find a skill that does Y", "browse skills", "what skills handle Z", "search skills"
- **3 个搜索源**（按优先级）：
  1. Project: `./skills/` 和 `.{tool}/skills/`（`.claude/`、`.cursor/`、`.codex/`、`.github/`）
  2. Personal: `~/.{tool}/skills/`
  3. Corporate: 从 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` 或环境变量读取
- **快速路径**：优先读 `INDEX.jsonl`，缺失时 fallback 扫描所有 `SKILL.md` 的 frontmatter
- **质量分数**：读 `out/scores/index.jsonl`（由配套 `skill-evaluate` 写入），**绝不伪造分数**

## 同 toolkit 内的姊妹 skill（未集成，需用户决策）

`artemrudenko/skill-governance-toolkit` 仓库提供 6 个 meta-skills：

| Skill | 作用 | 与 skill-find 的关系 |
|---|---|---|
| `skill-find` ✅ 已装 | 跨库搜索匹配 | 当前 |
| `skill-evaluate` | 单 skill 9 维评分（0-100）| skill-find 读其 `out/scores/index.jsonl` 缓存 |
| `skill-compare` | local vs upstream 对比 | skill-find 标记 duplicate 时推荐 |
| `library-audit` | 整库治理审计 | 周期性体检 |
| `skill-build-portable` | 把单一 host 的 skill 转化为多 host 通用 | 与本项目相关性弱 |
| `integration-init` | 引导安装 crg/repomix/serena 等可选集成 | 与本项目无关 |

## 与本项目其他已装 skill 的关系

| 已装 skill | 与 skill-find 的协同 |
|---|---|
| `skill-scout` | skill-find 的**完整版**——skill-scout 只查本地 + GitHub，skill-find 还覆盖 corporate + INDEX.jsonl 快速路径。可考虑 skill-scout 退役 |
| `discernment-nudge` | 正交——nudge 是回答后的事后辨析推动，skill-find 是回答前的工具检索 |
| `systematic-debugging` | 正交 |

## 路由规则（与 find-skills 分工，2026-09-19 用户确认保留两者）

| 用户意图 | 路由到 | 理由 |
|---|---|---|
| "我们有什么技能" / "browse skills" / 盘点本地资产 | **`skill-find`（本技能）** | 只读本地扫描（project + personal + corporate 私有库），语义匹配百分比 + 重复检测 |
| "帮我找/装一个新技能" / "想要 X 能力" / 远程采购 | `find-skills`（vercel-labs） | skills.sh 生态远程搜索 + `npx skills add` 一条命令安装 |
| 歧义触发（"is there a skill for X"，两者触发词重叠） | **级联**：先本技能查本地（只读、亚秒级），有强匹配即止；无匹配 → `find-skills` 远程搜索 | 先盘点后采购，避免重复安装已有能力 |

本技能**不可被 find-skills 替代**的三项独有能力：企业私有库搜索（Git URL + bearer token）、skill-evaluate 质量分联动（绝不伪造分数）、全本地清单语义化盘点 + 跨源重复治理。

## 维护建议

- skill-find 在 artemrudenko 仓库 134 commits，活跃维护
- 建议每季度 `Invoke-WebRequest` 拉 raw 源做字节比对
- 若发现漂移，先 `gh issue create` 在上游报告，不要本地 patch

## 【路由规则】skill-find vs find-skills —— **触发词高度重叠，慎用**

**触发词重叠**（两者都命中）：

| 触发短语 | 命中 |
|---|---|
| "is there a skill for X" | 两者都命中 |
| "find a skill for X" | 两者都命中 |
| "is there a skill that can..." | 两者都命中 |

**用户给定的路由规则**（2026-09-19 沉淀）：

| 用户问题指向 | 用哪个 | 理由 |
|---|---|---|
| **"已有什么"**——本地/项目/企业库里**已经装了什么 skill** | **`skill-find`（本 skill）** | 扫 `./skills/` + `~/.{tool}/skills/` + corporate + `INDEX.jsonl`，**纯本地资产盘点** |
| **"想要新能力"**——从远程生态**找/装一个新的 skill** | **`find-skills`**（用户已手工装在 `~/.minimax/skills/find-skills/`，vercel-labs/skills 出品） | 查 `skills.sh` leaderboard + `npx skills find <query>` + `npx skills add`，**远程生态采购** |

**两者正交不重叠**：
- skill-find 找不到（本地没装）→ find-skills
- find-skills 找不到（生态里没有）→ 通用能力或 `npx skills init` 自创

## find-skills 实际位置（用户手工安装，未在本项目唯一源）

| 项 | 值 |
|---|---|
| 安装位置 | `C:\Users\admin\.minimax\skills\find-skills\` |
| 文件 | `SKILL.md`（10,219 字节）+ `_meta.json`（244 字节）|
| 来源 | `vercel-labs/skills`（MIT，32k stars，skills.sh 排名第一）|
| 触发短语 | "is there a skill for X" / "find a skill for X" / "how do I do X" |

> **注**：早期轮次我误以为用户口述的 "Find skills" 在公开生态不存在 → 找了 artemrudenko/skill-find（单数，语义近邻）替代。这是错的——用户最终澄清是 **`find-skills`（复数）+ vercel-labs/skills（skills.sh 第一）**。本 ORIGIN.md 是修正后的对称点。