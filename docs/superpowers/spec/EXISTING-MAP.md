# EXISTING-MAP.md — 并行会话隔离工程 P0 现状映射（v1.1 计划 §8 交付物）

- 日期：2026-09-20
- 方法：真实代码读取与实测命令取证（非目录名猜测）；评审报告 `docs/reports/2026-09-20-parallel-session-plan-review.md` §1-§2 为本映射的证据主体，本文件为正式 P0 记录
- P0 完成标准核验（"Current implementation ≠ assumed implementation"）：**成立**——至少 4 处 v1.0 假设与实现不符（账本位置、模型配置层级、手工会话入口、ownership 判定），全部已核实并回写 v1.1

## 1. 机制映射表

| # | Mechanism | Current File | Current Authority | Current Scope | Used By |
|---|---|---|---|---|---|
| 1 | Worktree 创建 | `.harness/scripts/dispatch.py::ensure_worktree` | git worktree add（主树执行） | 仓库级，根 `.harness/worktrees/`（gitignored） | dispatch、poll 重试 |
| 2 | Branch 创建 | 同上 | `feat/{task_id}`，一任务一分支 | 仓库级 | 同上 |
| 3 | 自动派发入口 | `dispatch.py::main`；编排 `loop.py`（dispatch→pipeline→poll 每轮） | 主树；loop 单实例锁强制 | 仓库级 | 人工启动 loop / 计划任务 |
| 4 | 手工会话入口 | **不存在**（P0 核实：无任何 worktree 分配/登记机制，人工会话直接在主树工作） | 规则约束（lessons [parallel-sessions]） | — | — |
| 5 | 运行账本 | `runs.py::RunsStore` → `.harness/runs/RUNS.jsonl` + `PIPELINE.jsonl` | **主树集中**（非每 worktree；v1.0 假设不成立已修正）；append=fsync 真追加，覆写=os.replace 原子 | 仓库级 | dispatch/poll/pipeline/modelswap |
| 6 | 并发计数 | `dispatch.py::running_count`（owner=None 跨双账本）→ `slots = concurrency - count` | 查询正确但**无锁 check-then-act**（dispatch.py:415）；安全靠串行约定 | 仓库级 | dispatch |
| 7 | 协调锁（现成模式） | `modelswap.py::acquire_lock`、`loop.py::acquire_singleton` | mkdir + pid + 600s stale + 二次确认；Windows 实战验证 ×2 | 仓库级（runs_dir 内） | 模型切换临界区、loop 单实例 |
| 8 | 模型配置写入点 | `modelswap.py::swap_for_run/restore` → `~/.dsh/settings.yaml` `agent-default-model` | **用户机器级全局文件**（跨仓库/跨手工会话）；带文件监视器热发布到运行中会话 | 用户级 | dispatch spawn、poll finalize_restore |
| 8b | 会话级覆盖能力（P4 用） | `dsh --patch <yml>` 叠加层 + `dsh-settings-file` 的 `config.path` 重定向（优先级：文件层>组合层） | 评审报告 §7 双探针实证（成功用例 + 404 阴性对照 + 全局哈希不变） | 按进程 | 待 P4 接线 |
| 9 | 卡状态读写 | 卡 `status:` 字段；`dispatch.py::commit_card_status`（主树 git commit + pathspec + TASK-023 自覆盖契约）| 主树为唯一写入点；卡文件本身随分支 checkout 分叉（见 §3-缺陷 B） | 主树（权威）/ 各树（快照） | dispatch/poll/pipeline/archive/verify |
| 10 | Ownership 判定 | **不存在**（隐式：status 占坑 + 单派发器前提；v1.0 假设不成立已修正） | — | — | — |
| 11 | Hook 链（提交门禁） | `.githooks/pre-commit`（validate-all/scope/契约/dotnet build）→ `commit-msg` → `docs/ai-workspace/hooks/` 真身（check_approval.py：活动卡 allow_write+approver，deny 优先，TASK-023 自生命周期例外） | `core.hooksPath=.githooks`（.git/config 共享，worktree 继承）；但**脚本按 `__file__` 解析 .harness**（见 §3-缺陷 B） | 全仓 | 所有树的 git commit |
| 12 | 不入库 runtime state | `.harness/runs/`、`.harness/worktrees/`、`.harness/context/`（gitignore）；`~/.dsh/settings.yaml`、`~/.dsh/profiles/`、`~/.dsh/sessions/` | gitignore 保证不随 checkout 漂移 | 混合（仓库级 + 用户级） | 派发链全部 |
| 13 | 崩溃恢复 | `poll.py`：`pid_alive`（tasklist）→ exitcode → 三层门禁 → 复位重派/超限 blocked；`pipeline.py::_reap_running`（spawning 超时 stale → error 重派）；锁 stale 600s | 单循环内顺序回收 | 主树账本 | poll/loop |
| 14 | canary 门禁 | `canary.py`：快照 {executor_argv, run-exec 哈希, node 版本, 机器} ↔ `.canary-state.json`，fail-closed 拒整轮派发；真探针 = 经 run-exec 起 dsh 要求 alive-probe | 铁律 15 无逃生口 | 仓库级 | dispatch main 前置 |
| 15 | 人类验收 | `verify-all.py`（六门禁 + 脏态/SHA 记录 → `docs/verification/VERIFY-*.md`）；done 唯一来源 | L5 角色分离 | 主树 | 架构师 |

## 2. P0 补漏项（评审报告未覆盖、本阶段实测补齐）

1. Hook 真身位于 `docs/ai-workspace/hooks/`（`.githooks/` 为转发壳），`git-common-dir` 实测可作 worktree→主树锚点（worktree 内返回 `F:/JQKJ/.git`）。
2. 回收器重试链实测：失败 → `reset_worktree` → `spawn_attempt`（同 worktree 复用）→ 预算 `budget_attempts`（上游故障不计）→ 超限 blocked。A3 语义全部有实现对应。
3. 管线卡派发**不做模型 swap**（pipeline.py 仅把 model 打进 prompt 文本）——模型路由在 dispatch 路径与 pipeline 路径行为不一致，P4 落地时两条路径都要接会话覆盖（登记为 P4 范围事实）。
4. 回归基线（本工作区脏态下）：`python -m unittest discover -s .harness/tests -t .harness` → **147 tests, OK**（2026-09-20）。

## 3. P0 期间发现的既有缺陷（登记，不顺手修——Rule 1）

| ID | 发现 | 证据 | 归属建议 |
|---|---|---|---|
| B | **钩子卡状态分叉（V8 隐患今天已成立）**：`check_approval.py`/`check-local-scope.py`/`validate-task-card.py` 按 `__file__`/`--show-toplevel` 解析 `.harness`，在 worktree 内读的是**分支快照**而非主树实时卡。实测：TASK-008 worktree 内 active 卡 12 张 vs 主树 21 张 | 实测命令输出（本文件提交记录） | P1/P5 施工时以协调根锚点（common-dir 父目录）统一事实源；属本计划面 A/D/E |
| C | **本地 scope 门禁并发失效**：`check-local-scope.py:98`——活动卡非唯一（ready/in-progress ≥2 或 =0）即 `[WARN] skip`，并发>1 时本地门禁静默关闭 | 代码行 | 随 B 一并治理（ownership 化判定），属面 D |
| D | `verify-all.py` 使用 `os.environ`（:56）但**无 `import os`**——`--approve-protected-paths` 必 NameError（该旗为架构师通道，触发面小） | grep 全仓 `import os` 无 verify-all 命中 | OUT-OF-SCOPE → 另开修复卡 |
| E | 派发默认模型上游免费档已下线（404 实测）+ `dsh --profile headless` 组合时 `mcp-codebase-memory` patch 条目 "entry not found"（未加载） | 评审报告 §7 探针、R1c；v1.1 附录挂账 | 架构师处理，先于 P4/P6 |
| F | 陈旧 worktree 残留（TASK-008/009/010 对应任务已归档仍挂分支占用） | `.harness/worktrees/` 目录实测 | P3-B1 回收策略 |
| G | **施工起点脏态**：主树 24 个被跟踪文件有未提交真实内容改动（前会话进行中工作：skills/modelswap/runs/replan/run-exec/dispatch.yaml + 多份文档），另有大批换行翻转；暂存区空；stash@{0} 存留 | `git diff --ignore-cr-at-eol --stat` 实测（2026-09-20） | 架构师处置（提交/分支化/清理）后，本计划各 Commit 方有干净起点 |

## 4. P0 结论

12+2 项机制全部定位到实现级；4 项 v1.0 假设偏差已核实并回写 v1.1；未发现的机制（手工会话入口、ownership）**未发明替代架构**，维持 v1.1 §9/§13 的最小新增定义。P0 通过，P1 可放行——放行前置：脏态 G 处置 +（非阻塞）缺陷 E 的模型行修复。
