# JQKJ 项目 · Superpowers 注入器

> **未来会话的开场读本**。本文件被 Claude / Codex / MiniMax 的启动脚本自动加载（如果支持）；不支持时，由 PROJECT.md 兜底。

## 用法

### 给 Claude Code
将本目录软链或复制到 `~/.claude/projects/F--JQKJ/`，触发 `~/.claude/rules/` 全局铁律 + 本项目入口。

### 给 Codex CLI
本目录的 `PROJECT.md` 已按 codex 兼容格式编写。Codex 启动时会读 `~/.codex/memories/` 与当前工作目录的 `.codex/rules.md`，可在本项目根添加：

```toml
# 在 ~/.codex/config.toml 中追加
[[project_rules]]
path = "F:/JQKJ/.superpowers/PROJECT.md"
```

### 给 MiniMax Harness（本会话所用）
MiniMax-M3 当前通过 `SKILL.md` 自动加载 .superpowers/PROJECT.md 作为项目上下文。已在本会话验证可用。

## 文件清单

| 文件 | 用途 |
|---|---|
| `PROJECT.md` | 项目身份 + 全局规则引用 + L0 状态 + 任务清单 + 必读文件速查 + 会话开场仪式 + 严禁反模式 |
| `local-skills/` | 项目级 skills 占位（**当前为空**——避免污染仓库） |
| `context/` | 上下文缓存（**当前为空**——留给未来的 episodic-memory 同步点） |

## 与全局 superpowers 的协作

- **全局铁律**：`~/.claude/rules/engineering-iron-laws.md`（Law 1-10）— 全栈通用
- **全局 skill marketplace**：`~/.claude/plugins/cache/superpowers-marketplace/` — 提供 `using-superpowers`、`writing-plans`、`verification-before-completion` 等
- **跨会话记忆**：`episodic-memory` 插件 — 自动写 `~/.config/superpowers/logs/episodic-memory.log`
- **本项目入口**：本目录

**会话流程**：全局铁律（决定能/不能做什么） + 全局 skills（决定怎么做） + 本项目入口（决定为谁做） = 完整 superpowers 工作流。

## 维护

- **不**修改 `PROJECT.md` 的 §1-§3（项目身份 / 全局规则 / L0 状态）— 这些是事实
- **可**修改 §5（当前任务） — 任务完成后划掉、加新任务
- **可**修改 §6（关键文件速查） — 新增/删除文件时同步
- **必须**遵守 §7（必做的开场仪式）— 不许跳过
- **必须**遵守 §8（严禁反模式）— 违反属 ADR 升级事件
