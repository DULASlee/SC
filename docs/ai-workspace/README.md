# AI Workspace

本目录是 GenCollector 项目所有 AI 工具配置（rules / hooks / skills / MCP / prompts）的**唯一源**，遵循铁律 14。

## 符号链接建立说明

多数 IDE 与 AI 工具会从固定路径读取规则（如 `.cursor/rules/`、`.vscode/prompts/`、`.claude/skills/` 等），但本仓库规定所有 AI 配置**只允许在此目录下维护**。在仓库根或其他位置维护独立副本视为违反铁律 14。

### 跨平台链接命令（按 IDE 选用）

#### Windows（PowerShell，管理员权限或 Developer Mode 启用）

```powershell
# Cursor
New-Item -ItemType SymbolicLink -Path .cursor\rules -Target (Resolve-Path docs\ai-workspace\rules) -Force

# VS Code (GitHub Copilot / Continue)
New-Item -ItemType SymbolicLink -Path .vscode\rules -Target (Resolve-Path docs\ai-workspace\rules) -Force

# Claude Code
New-Item -ItemType SymbolicLink -Path .claude\rules -Target (Resolve-Path docs\ai-workspace\rules) -Force
```

#### Linux / macOS

```bash
ln -s ../docs/ai-workspace/rules .cursor/rules
ln -s ../docs/ai-workspace/rules .vscode/rules
ln -s ../docs/ai-workspace/rules .claude/rules
```

### 链接对象

| IDE / 工具 | 链接源 | 链接目标 |
|---|---|---|
| Cursor | `.cursor/rules/` | `docs/ai-workspace/rules/` |
| VS Code | `.vscode/rules/` | `docs/ai-workspace/rules/` |
| Claude Code | `.claude/rules/` | `docs/ai-workspace/rules/` |
| 通用 | `<tool>/rules/` | `docs/ai-workspace/rules/` |

### 注意事项

- 符号链接应当加入 `.gitignore`（避免 IDE 私有目录被 commit）
- 修改链接源 = 修改本目录 = 修改 git tracked 文件，**遵循铁律 13 通过 PR 流程**
- 本 README 是符号链接流程的单一说明文档；具体 IDE 行为以 IDE 官方文档为准

## 目录结构

| 目录 | 用途 |
|---|---|
| `rules/` | 规则文件（governance / lessons-learned / engineering-rules） |
| `hooks/` | Git hooks（pre-push / commit-msg 等） |
| `hooks/scripts/` | hook 引用的脚本（Python / Bash） |
| `skills/` | AI skills（按场景组织的可复用能力描述） |
| `mcp/` | MCP（Model Context Protocol）配置 |
| `prompts/` | 提示词模板 |

## 已集成 Skills

按"用户口述名称 → 真实集成"的映射表。每个 skill 都附**安装来源 + 验证方式**。

| 名称 | 用户原口述 | 真实集成 | 来源 | 用途 |
|---|---|---|---|---|
| `discernment-nudge` | "self-improving"（用户口述，但该名称不存在） | `skills/discernment-nudge/SKILL.md` | Anthropic 官方 `anthropics/skills`（Apache-2.0） | 防止 AI 答案被照单全收；实质性答复后追加 2-3 条具体反问，每会话最多一次 |
| `skill-find` | "Find skills"（第 3 轮用户澄清"复数"） | `skills/skill-find/SKILL.md` | `artemrudenko/skill-governance-toolkit`（MIT，134 commits）——通过 GitHub Repo Search API 命中 | 跨 project/personal/corporate 库搜索匹配自然语言需求；触发词 "is there a skill for X" |
| `skill-evaluate` | "加装 skill-evaluate" | `skills/skill-evaluate/SKILL.md` | `artemrudenko/skill-governance-toolkit` 同 toolkit（MIT） | 单 SKILL.md 9 维（D1-D9）评分 0-100，含 Safety 硬门；触发词 "evaluate skill X"、"is this skill production-ready" |

> **已退役**（2026-09-19）：`skill-scout` —— 经三处全查审计（仓库/全局/system prompt），无任何依赖方；自报来源 PR #1232 验证为假；License 不透明；功能被 `skill-find` 覆盖。全局副本 `~/.config/opencode/skills/skill-scout/` 保留作应急回滚源。

### 安装验证（trust-but-verify）

集成第三方 skill 后，**不要只读自己刚写入的文件**——直接拉 raw 源做归一化字节比对：

```powershell
$src = "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>/SKILL.md"
$remote = (Invoke-WebRequest -Uri $src -UseBasicParsing).Content
$local  = Get-Content -LiteralPath "<local>/SKILL.md" -Raw -Encoding UTF8
# Windows 下 Write 工具写 CRLF，规范化到 LF 后再比较
$rn = ($remote -replace "`r`n","`n").TrimEnd("`n")
$ln = ($local  -replace "`r`n","`n").TrimEnd("`n")
if ($rn -ceq $ln) { "MATCH" } else { "DIFF" }
```
