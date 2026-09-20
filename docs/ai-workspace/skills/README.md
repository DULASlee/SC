# skills

AI 工具 skills（按场景组织的可复用能力描述）。唯一源目录；agent 目录（如 `.agents/skills/`）只允许 Junction 符号链接指向此处。

## 技能发现路由规则（2026-09-19）

两个"找技能" meta-skill 并存，按用户意图路由，触发词重叠时级联：

| 用户意图 | 路由到 |
|---|---|
| 盘点本地资产（"我们有什么技能"/"browse skills"） | `skill-find`（本地：project + personal + corporate 私有库，只读） |
| 远程采购（"帮我找/装一个新技能"） | `find-skills`（skills.sh 生态 + `npx skills add` 安装） |
| 歧义（"is there a skill for X"） | **级联**：先 `skill-find` 查本地，无匹配再 `find-skills` 远程 |

安装落地铁律：外部 CLI 安装的技能，实体必须在 `docs/ai-workspace/skills/<name>/`（SKILL.md + LICENSE + ORIGIN.md 含字节比对），agent 目录只放 Junction。

## 已装清单

| Skill | 来源 | 用途 |
|---|---|---|
| `find-skills` | vercel-labs/skills（skills.sh #1） | 远程技能发现与安装引导 |
| `skill-find` | artemrudenko/skill-governance-toolkit | 本地技能盘点（detect-only） |
| `skill-evaluate` | artemrudenko/skill-governance-toolkit | 单 skill 9 维评分（0-100） |
| `discernment-nudge` | Anthropic 官方示例 | 回答后辨析推动（每会话最多一次） |
