# superpowers — 项目 harness 执行层技能集（落地）

> **定位**：本目录是 JQKJ 项目 harness **执行层方法论** 的唯一实体源。
> 实体从全局 `~/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/`
> 一次性落地铁律迁移而来；全局插件目录不再作为本项目的技能实体源。

## 铁律 14 合规

- 实体文件：`docs/ai-workspace/skills/superpowers/<skill-name>/`
- agent 目录 `.agents/skills/` 只放 Junction 指向本目录
- 每个技能目录含 `SKILL.md` + `ORIGIN.md`（字节比对），LICENSE 见本目录 `LICENSE`

## 技能清单（14 个，全部实体化落地）

### 执行核心（harness 执行层必载）

| 技能 | 用途 | 在执行层的角色 |
|---|---|---|
| `using-superpowers` | 元技能：如何发现/调用技能 | 每次会话开场 |
| `writing-plans` | 写实施计划（bite-sized tasks + TDD） | 计划阶段 |
| `executing-plans` | 按计划逐任务执行 + 检查点 | 执行阶段 |
| `subagent-driven-development` | 每任务派新 subagent + 双阶段评审 | 并行执行 |
| `test-driven-development` | 先红后绿，铁律 | 每个功能 |
| `verification-before-completion` | 无证据不得报完成 | 每个完成声明 |
| `systematic-debugging` | 根因优先四阶段 | 每个 bug |

### 交付与协作

| 技能 | 用途 |
|---|---|
| `finishing-a-development-branch` | 分支收尾：merge/PR/保留/丢弃 |
| `requesting-code-review` | 派 reviewer subagent |
| `receiving-code-review` | 验证后采纳，禁止表演性同意 |
| `dispatching-parallel-agents` | 独立问题并行 subagent |
| `using-git-worktrees` | 隔离工作区 |

### 设计层（执行前置）

| 技能 | 用途 |
|---|---|
| `brainstorming` | 创意→设计→spec，硬门禁 |
| `writing-skills` | 用 TDD 方法写技能 |

## 与 JQKJ 既有体系的映射

| 既有 L0–L3 harness | 本技能集角色 |
|---|---|
| 任务卡 `.harness/tasks/active/TASK-XXX.yaml` | 由 `writing-plans` 产出，由 `executing-plans`/`subagent-driven-development` 执行 |
| CI 门禁（build/test/coverage/mutation） | `verification-before-completion` 要求每个 done 附新鲜证据 |
| `docs/superpowers/spec/` + `docs/superpowers/splan/` | `brainstorming` 写 spec，`writing-plans` 写 splan |

## 字节比对来源（详见各 ORIGIN.md）

- 源目录：`~/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/skills/`
- License：MIT（Copyright (c) 2025 Jesse Vincent），完整文本见本目录 `LICENSE`
- 落地日期：2026-09-19
- 版本：superpowers 5.1.0
