# 项目工作流（GitHub 集成 + 本地 CI）

## 概述

本项目使用**本地 git hooks + 人工验收 + GitHub Actions CI** 三层门禁：
- **L0-L3 机械门禁**：pre-commit / pre-push / commit-msg（本地 hooks）
- **L5 人工验收**：`verify-all.py` + `docs/verification/VERIFY-*.md`（本地跑）
- **L2-A/L3/L4-A 远程 CI**：`.github/workflows/ci.yml`（GitHub Actions）

## 分支模型

| 分支 | 用途 | 保护规则 |
|---|---|---|
| `main` | 已发布/稳定的代码 | 架构师 GitHub 网页配置：禁止直接 push（须经 PR） |
| `develop` | 集成分支 | 架构师 GitHub 网页配置：禁止直接 push（须经 PR） |
| `feat/*` | 单个任务分支 | 无保护，可直接 push |
| `fix/*` | 紧急修复 | 无保护，可直接 push |

**首次推送顺序**（架构师 §三 阶段 3）：
1. `git remote add origin https://github.com/DULASlee/SC.git`
2. `git push -u origin main`（此时无保护，能成功）
3. 架构师在 GitHub 网页配置 main 分支保护
4. `git checkout -b develop && git push -u origin develop`
5. 架构师在 GitHub 网页配置 develop 分支保护

## 开发者流程（Agent / 贡献者）

```
1. 创建任务卡 .harness/tasks/active/TASK-XXX.yaml（架构师）
2. git checkout -b feat/TASK-XXX
3. 编写代码（仅在 allow_write 范围内）
4. git add .  → pre-commit 自动跑（编译、scope、契约、任务卡校验）
5. git commit -m "feat(TASK-XXX): ..." → commit-msg 自动跑（强制 TASK-XXX + 受保护路径 APPROVED-BY）
6. git push origin feat/TASK-XXX → pre-push 自动跑（全测试 + 可靠性）
7. 在 GitHub 网页创建 PR → CI 自动跑（5 个 jobs）
8. 架构师人工验收：python .harness/scripts/verify-all.py --task-id TASK-XXX --operator architect-name
   → 生成 docs/verification/VERIFY-TASK-XXX-<ts>.md
9. 架构师 merge → close 任务（archive-task.py）
```

## 受保护路径（需 [APPROVED-BY: name]）

| 路径 | 原因 |
|---|---|
| `tests/**` | 测试代码由架构师预先写好红测试 |
| `contracts/**` | L1 契约收敛后由架构师控制 |
| `.harness/**` | 任务协议 / 验收脚本 |
| `.githooks/**` | git 门禁配置 |
| `.github/**` | CI 配置（修改它会绕过独立验证） |
| `Directory.Build.props` | L2-A 全局约束 |
| `Directory.Build.targets` | L2-A 全局约束 |
| `stryker-config.json` | L2-B 变异测试配置 |

## 豁免前缀（免 APPROVED-BY）

- `chore:` / `chore(scope):`
- `docs:` / `docs(scope):`
- `fix(ci):`
- `feat(l0):` / `feat(l0-*):`
- `feat(l1` / `feat(l2` / `feat(l3` / `feat(l4`
- `feat(local-ci`

豁免前缀匹配 `type` 或 `type(scope):` 形式（regex）。

## 紧急出口

- `SKIP_PROTECTED_CHECK=1`：架构师本人可绕过受保护路径 APPROVED-BY 检查
- `git commit -m "..." --no-verify`：跳过所有 hooks（**不推荐**，会绕过 L5 规则 2）

## L5 验收规则（docs/engineering/l5-separation-of-roles.md）

任务 done 必须有 `docs/verification/VERIFY-<task-id>-*.md`。无验收记录的 done 视为无效。
