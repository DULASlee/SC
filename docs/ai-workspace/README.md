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
