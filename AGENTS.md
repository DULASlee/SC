# AGENTS.md — GenCollector 项目 AI 助手统一入口

> 所有 AI 工具执行本仓库任务前，必须先阅读本文件及引用的所有规则。

## 必读文件（每次任务前加载）

| 文件 | 用途 |
|---|---|
| `docs/ai-workspace/rules/engineering-rules.mdc` | 工程铁律 1-14 |
| `docs/ai-workspace/rules/governance.md` | 治理规则（如已建立） |
| `docs/ai-workspace/rules/lessons-learned.md` | 经验库 |
| `docs/README.md` | 文档目录结构总览 |

## 工作原则

1. 发现指令矛盾 → 停下来报告，不盲从
2. 任务完成 → 提炼经验写入 `docs/ai-workspace/rules/lessons-learned.md`
3. 涉及 Windows 环境 → 所有 subprocess 调用显式指定 `encoding='utf-8'`
4. hook 脚本输出 → 只用 ASCII，不用 emoji
5. 文档/配置新增 → 必须放 `docs/` 对应子目录，禁止散落
6. 所有 AI 配置唯一源在 `docs/ai-workspace/`，禁止在 IDE 私有目录维护副本

## 文档目录速查

| 我要放的东西 | 放哪里 |
|---|---|
| 设计规格 | `docs/superpowers/spec/` |
| 实施计划 | `docs/superpowers/splan/` |
| 架构文档/ADR | `docs/architecture/adr/` |
| 部署文档 | `docs/deployment/` |
| 工作汇报 | `docs/reports/` |
| 红态证据 | `docs/testing/red/TASK-XXX/` |
| 规则/铁律 | `docs/ai-workspace/rules/` |
| Hooks | `docs/ai-workspace/hooks/` |
| Skills | `docs/ai-workspace/skills/` |
| MCP 配置 | `docs/ai-workspace/mcp/` |
| 提示词 | `docs/ai-workspace/prompts/` |
