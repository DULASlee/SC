# L5: 强模型 / 人与弱模型的分工（独立验证者）

## 状态
已接受（架构师裁决 · L5 在本地 CI 场景下的具体化）

## 背景
L5 是 harness 的"独立验证者"层——**验收者必须是确定性工具（编译器、测试、Schema 校验器）或不同能力级别的模型/人**。

在本地 CI 场景下（无远程 Git 服务），L5 的具体落地形式是**人类架构师在验收机运行 `.harness/scripts/verify-all.py`**，产出 `docs/verification/VERIFY-*.md` 作为"任务 done"的唯一权威凭证。

## 本地 CI 下的证据规则

### 规则 1：本地执行 ≠ CI 执行

所有报告中，"CI 通过"的说法**必须附带以下区分**：

- **[LOCAL]**：本机 git hook 跑过（pre-commit / pre-push / commit-msg）
- **[VERIFY]**：人类验收脚本 `verify-all.py` 跑过 + VERIFY-*.md 产出
- **[REMOTE]**：远程 CI（如 GitHub Actions）跑过 + artifact 可下载

**禁止用"CI 通过"掩盖"本地通过"或"未跑"的事实。**

### 规则 2：验收记录是 done 的唯一凭证

任务卡 status 改为 `done` 之前，**必须存在** `docs/verification/VERIFY-<task-id>-*.md` 文件。

没有验收记录的 done 视为无效。

### 规则 3：受保护路径的修改必须人工批准

`tests/**`、`contracts/**`、`.harness/**`、`.githooks/**` 的任何修改，必须由人类架构师在 commit message 中批准（`[APPROVED-BY: <name>]`）。

或由人类架构师本人设 `SKIP_PROTECTED_CHECK=1` 环境变量绕过。

## 本地 CI 流程图

```
Developer / Agent
    │
    │  git commit
    ▼
pre-commit hook ────► L0-L3 机械门禁
    │
    │  commit-msg hook 强制引用 TASK-XXX
    ▼
commit 成功
    │
    │  git push local-verify main
    ▼
pre-push hook ────► 全测试 + 覆盖率
    │
    ▼
push 成功
    │
    │  人类在验收机：
    │  python .harness/scripts/verify-all.py
    ▼
docs/verification/VERIFY-<id>-<ts>.md
    │
    │  人类检查报告 → 批准
    ▼
任务 done
```

## 后期升级路径

当远程 CI（Gitee/GitHub/Gitea）就绪后：
1. 保留 `.github/workflows/ci.yml`（已有 L2-A + L3 jobs）
2. `git remote add origin <url>`
3. push 到远程，CI 自动生效
4. 本地 hooks 可保留作为**快速反馈层**（CI 跑前先本地跑一次）

`.harness/scripts/check-pr-scope.py` 保留作为远程 CI 用，`check-local-scope.py` 是本地版本。
