# AGENTS.md — 跨 AI 工具统一入口

本文件是 GenCollector 项目对所有 AI 执行者（Claude Code / Codex / Copilot / 其他）的统一行为约束入口。

## 必读文件（每次任务前加载）

- `.harness/rules/governance.md` — 治理规则
- `.harness/rules/lessons-learned.md` — 经验库（犯过的错、踩过的坑）
- `.specstory/config/engineering-rules.mdc` — 工程铁律

## 工作原则

1. 发现指令矛盾 → 停下来报告，不盲从
2. 任务完成 → 提炼经验写入 lessons-learned.md
3. 涉及 Windows 环境 → 所有 subprocess 调用显式指定 encoding='utf-8'
4. hook 脚本输出 → 只用 ASCII，不用 emoji

### 经验库

每次任务开始前，必须阅读 `.harness/rules/lessons-learned.md`。如果当前任务涉及该文件中已记录的场景，必须主动说明"该场景在经验库中已有记录"，并采取对应的规避措施。

文件路径：`.harness/rules/lessons-learned.md`
