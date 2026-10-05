# find-skills — Origin & License

> 本文件曾于 2026-09-19 被另一会话误删，已重建（SKILL.md/LICENSE 经 SHA256 复核未受影响）。

## 来源（已字节比对验证）

| 项 | 值 |
|---|---|
| 名称（frontmatter `name`）| `find-skills` |
| 唯一可信源 | `https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md` |
| 字节比对 | SHA256 `C00EEEA0E13E74FE4A9D84BA0A8542205A1B736D65F13134FE1A6647EB14976F`（5,472 = 5,472，完全一致；2026-09-19 恢复后复验仍一致） |
| 集成日期 | 2026-09-19 |
| License | **MIT**（完整 LICENSE 已落地 1,069 字节，Copyright (c) 2026 Vercel, Inc.） |
| 仓库 License | MIT |
| 仓库状态 | 32,001 stars，最近 push 2026-09-18，活跃维护 |
| 市场地位 | skills.sh 排行榜第 1 名（约 3.5M 安装量） |
| 安装方式 | `npx skills add vercel-labs/skills -s find-skills -a opencode -y`（已按铁律迁移到本目录） |

## 安装纠正记录

1. 初次安装时 CLI 默认落地 `.agents\skills\find-skills`（实体副本）→ **违反 AGENTS.md 唯一源铁律**
2. 已迁移：实体文件移至 `docs/ai-workspace/skills/find-skills/`，`.agents\skills\find-skills` 改为 **Junction 符号链接**指向本目录
3. `skills-lock.json`（CLI 锁文件，留在仓库根目录）记录 source/Hash，供 `npx skills update` 使用

## 设计要点

- **类型**：Meta-skill（技能远程发现与安装引导）
- **触发词**（用户原话触发）："how do I do X"、"find a skill for X"、"is there a skill that can..."、"can you do X"
- **核心能力**：引导 agent 使用 Skills CLI（`npx skills find <query>` / `npx skills add <pkg>`）搜索并安装 skills.sh 生态技能
- **质量门槛**（skill 内置）：安装量 1K+ 优先、<100 警惕；官方源（vercel-labs/anthropics/microsoft）优先；仓库 <100 stars 谨慎
- **无脚本**：纯 Markdown 指令，无 shell 命令、无网络调用（除引导用户执行 npx 命令）

## 路由规则（与 skill-find 分工，2026-09-19 用户确认保留两者）

| 用户意图 | 路由到 | 理由 |
|---|---|---|
| "我们有什么技能" / "browse skills" / 盘点本地资产 | `skill-find` | 只读本地扫描（project + personal + corporate），语义匹配百分比 |
| "帮我找/装一个新技能" / "想要 X 能力" / 远程采购 | **`find-skills`（本技能）** | skills.sh 生态远程搜索 + 一条命令安装 |
| 歧义触发（"is there a skill for X"） | **级联**：先 `skill-find` 查本地（只读、亚秒级），有强匹配即止；无匹配 → 本技能远程搜索 | 先盘点后采购，避免重复安装已有能力 |

**安装落地铁律**（本技能引导安装时必须遵守）：任何经 `npx skills add` 安装的技能，实体文件必须迁移到 `docs/ai-workspace/skills/<name>/`（含 ORIGIN.md + LICENSE），agent 目录只保留 Junction 符号链接。

## 与本项目其他 skill 的关系

| 已装 skill | 关系 |
|---|---|
| `skill-find`（artemrudenko） | **互补不替代**：skill-find = 本地资产盘点 + 企业私有库 + skill-evaluate 质量分联动；本技能 = 公共生态远程发现 + 安装。用户已确认两者保留 |
| `skill-scout`（用户级） | 远程候选的深度审查流程（读 SKILL.md、查可疑命令）可补本技能的启发式（安装量≠质量） |
| `skill-evaluate` | 互补——安装前评估技能质量 |

## 维护建议

- 上游活跃（Vercel 官方维护），建议每季度拉 raw 源做 SHA256 字节比对
- **注意**：`npx skills update` 可能会以实体副本覆盖 `.agents\skills\find-skills` Junction——更新后需检查链接类型，若被覆盖则重新迁移到本目录并重建 Junction
- 若发现上游漂移，先在上游仓库报告 issue，不要本地 patch
