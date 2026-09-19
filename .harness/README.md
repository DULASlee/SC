# L3 任务协议

## 概述

L3 用**机器可读的任务卡**替代长对话。每个任务在新会话中执行，只加载任务卡 + allow_write 范围内的文件，不依赖历史对话。

**两个核心机制：**
1. **上下文丢失消失** —— 没有长上下文可丢，因为任务粒度小于模型可靠工作集
2. **自报完成消失** —— Done 只来自 CI checks，模型无"完成"权限

## 完整流程

### 架构师（或强模型）—— 创建任务

1. 复制模板：`cp .harness/tasks/TASK-TEMPLATE.yaml .harness/tasks/active/TASK-001.yaml`
2. 填写所有字段，特别是：
   - `allow_write`：Agent 只能写这里
   - `acceptance_tests`：预先写好、初始为红
   - `done_when`：引用 CI 中的 gate
3. 校验：`python .harness/scripts/validate-task-card.py .harness/tasks/active/TASK-001.yaml`
4. 提交任务卡到 `develop` 分支
5. 生成上下文：`python .harness/scripts/start-task.py TASK-001`

### 执行者（AI 工程师）—— 执行任务

1. **新开会话**（不加载历史对话）
2. 读取 `.harness/context/TASK-001-context.md`
3. 只在 `allow_write` 范围内修改代码
4. 不触碰 `deny_write` 中的任何文件
5. 不发表"完成"声明
6. 提交 PR，PR 描述写 `Closes TASK-001`

### CI —— 判定 Done

CI 自动运行：
- `validate-task-cards`：校验所有 active 任务卡
- `check-pr-scope`：校验 PR 变更未越界（仅 PR 触发）
- `build` / `test` / `coverage_diff` / `mutation_test` / `contract_consistency` 等（已就位）

**所有 gate 全绿 = Done。任一红 = 未完成。**

### 架构师 —— 验收与归档

1. 确认 CI 全绿
2. 检查 PR 描述中的任务 ID 与任务卡一致
3. Merge PR
4. 将任务卡 status 改为 `done`
5. 归档：`python .harness/scripts/archive-task.py TASK-001`

## 目录结构

```
.harness/
├── README.md                    # 本文件
├── schema/
│   └── task-card.schema.json    # 任务卡 JSON Schema
├── scripts/
│   ├── validate-task-card.py    # 校验任务卡
│   ├── check-pr-scope.py        # 校验 PR 未越界
│   ├── start-task.py            # 生成新会话上下文
│   └── archive-task.py          # 归档完成的任务
├── tasks/
│   ├── TASK-TEMPLATE.yaml       # 模板
│   ├── active/                  # 进行中的任务卡
│   └── archive/                 # 已完成的任务卡
└── context/                     # 会话上下文（gitignore，不入仓）
```

## 关键规则

1. **一个任务一个新会话。** 不加载历史对话。
2. **执行者只能写 allow_write。** deny_write 优先级更高。
3. **验收测试由架构师预先写好。** 执行者对 tests/ 无写权限（CODEOWNERS）。
4. **Done 只来自 CI。** 执行者不发表"完成"声明。
5. **单次变更 ≤ 300 行 / 10 文件。** 超了拆分任务。
6. **任务卡只能由架构师创建或修改。** 执行者对 .harness/ 无写权限。

## 任务卡范围设计原则

L3 的核心价值是"最小上下文加载"——**每个任务只加载自己需要的文件，不加载历史或无关内容**。这是 L3 解决"上下文丢失"问题的具体落地。

### 硬性上限

| 指标 | 推荐值 | 硬性上限 |
|---|---|---|
| `start-task.py` 输出的上下文文件数 | ≤ 20 | 50（`start-task.py` 会打印 `[WARN]`） |
| 单任务最大文件数（`constraints.max_files_changed`） | 10 | 300 |
| 单任务最大行数（`constraints.max_lines_changed`） | 100 | 300 |

### 拆分规则

**单个任务卡 allow_write 应覆盖 ≤ 20 个文件**。超过则按以下原则拆分为多个任务卡：

1. **按文件类型拆分**：测试 / 实现 / 配置 拆开
2. **按模块边界拆分**：A 模块一个任务，B 模块另一个任务
3. **按变更范围拆分**：核心改动一个任务，附属清理一个任务
4. **按依赖关系拆分**：被依赖的先做，依赖的后做（用 `depends_on` 字段串联）

### 路径示例

✅ **好**：
```yaml
scope:
  allow_write:
    - GenCollector/Core/EdgeBuffer.cs      # 单文件
  deny_write:
    - GenCollector.Tests/**
```

✅ **可接受**：
```yaml
scope:
  allow_write:
    - GenCollector/Core/EdgeBuffer.cs
    - GenCollector/Core/EdgeBufferExtensions.cs   # 2 文件，紧耦合
    - GenCollector.Tests/Core/EdgeBufferTests.cs
```

❌ **需拆分**：
```yaml
scope:
  allow_write:
    - GenCollector/**        # 整个生产代码项目 → 必须拆分
    - GenCollector.Tests/**   # 整个测试项目 → 必须拆分
    - .harness/**             # 任务协议 → 架构师专属
```

### 路径精度匹配

`allow_write: [GenCollector/Core/**]` 与 `allow_write: [GenCollector/Core/EdgeBuffer.cs]` 粒度不同。架构师应**用最窄粒度**——粒度越窄，Agent 注意力越集中，越不容易越界。

### 防御性检查（start-task.py 内置）

`start-task.py` 在生成上下文时会统计文件数：
- ≤ 20：不警告
- 21-50：`[INFO] 上下文文件数 N > 20，已超过 L3 推荐值。考虑拆分任务卡。`
- \> 50：`[WARN] 上下文文件数 N > 50，可能破坏 L3 最小上下文设计（推荐 ≤ 20）`

**警告不阻断**——架构师决定是否拆分。但当看到 WARN 时，必须严肃考虑拆任务。

### 历史教训：P0 修复

L3 完成后第一次跑 `start-task.py TASK-001` 报告 **295 个文件**——违反"最小上下文加载"原则。

**根因**：脚本遍历文件系统时未排除 `.gitignore` 列表的所有目录（`bin/`、`obj/`、`coverage/`、`StrykerOutput/` 等），导致 `GenCollector.Tests/**` 把测试工程 bin/obj 下 200+ 个 dll/config 文件全收进来。

**修复**：脚本现在读 `.gitignore` 解析 + 硬编码最小集双保险。295 → 6。

## 已知局限

- **CODEOWNERS 占位符**：`@org/architecture-leads` 是占位符，部署到具体仓库时**必须替换为真实 GitHub team 或 user handle**。否则 CODEOWNERS 不生效。
- **CODEOWNERS 不能阻止本地修改**：CODEOWNERS 是 GitHub PR 评审机制。执行者在本地仍可写 .harness/，但 PR 时会被架构师 gate。CI 校验 + 人工审批是最终防线。
- **300 行限制是经验值**：模型可靠工作集约 300 行变更。调大需架构师批准，且必须开 ADR。

## 常见问题

**Q：如果任务卡需要修改怎么办？**
A：架构师修改，重新提交。执行者不能改任务卡。

**Q：如果执行中发现任务卡 scope 不足怎么办？**
A：执行者停止，向架构师报告。不越界，不猜测。

**Q：如果 CI 有一项一直红但认为是误报？**
A：不绕过。报告架构师。门禁的权威性高于单次效率。

**Q：怎么生成下一会话上下文？**
A：`python .harness/scripts/start-task.py TASK-XXX`，产出 `.harness/context/TASK-XXX-context.md`。新会话里让 Agent 读它即可。

---

## 本地 CI 使用说明

本项目使用**本地 git hooks + 人工验收**替代远程 CI（架构师 L5 决策）。

### 一次性配置

```bash
bash scripts/setup-local-ci.sh
```

该脚本会：
1. `git config core.hooksPath .githooks`（让 git 用仓库内 hooks）
2. 给 hooks 加 `+x` 执行权限
3. 创建裸仓库 `../JQKJ-verify.git` 并添加为 `local-verify` remote

### 日常流程

| 动作 | 触发的门禁 |
|---|---|
| `git commit` | pre-commit（编译、契约、架构、scope）+ commit-msg（强制 TASK-XXX） |
| `git push local-verify main` | pre-push（全测试 + 覆盖率） |
| 人类验收 | `python .harness/scripts/verify-all.py --task-id TASK-XXX` |

### 关键约束

1. **受保护路径修改需人工批准**：`tests/`、`contracts/`、`.harness/`、`.githooks/` 的任何变更必须含 `[APPROVED-BY: <name>]`（架构师本人可设 `SKIP_PROTECTED_CHECK=1`）
2. **验收记录是 done 的唯一凭证**：`docs/verification/VERIFY-*.md` 必须存在
3. **报告必须区分本地/验收/远程执行**——见 `docs/engineering/l5-separation-of-roles.md` 规则 1

### 本地新增 vs 远程 CI 的脚本分工

| 脚本 | 用途 | 何时跑 |
|---|---|---|
| `.harness/scripts/check-local-scope.py` | 本地 git hook 用 | `git commit` 前 |
| `.harness/scripts/check-pr-scope.py` | 远程 CI（GitHub Actions）用 | PR 事件 |
| `.harness/scripts/verify-all.py` | 人类验收 | 任务合并前 |

### 后期升级到远程 CI（架构师 L5 文档 §后期升级路径）

1. 保留 `.github/workflows/ci.yml`
2. `git remote add origin <url>`
3. push 到远程，CI 自动生效
4. 本地 hooks 保留作为**快速反馈层**（CI 跑前先本地跑一次）

### 工作流详情

完整工作流见 `docs/engineering/workflow.md`：
- 分支模型（main / develop / feat/* / fix/*）
- 首次推送顺序（架构师在 GitHub 网页配置分支保护）
- 开发者 9 步流程（含 L5 验收环节）
- 受保护路径与豁免前缀列表

### 紧急出口

- `SKIP_PROTECTED_CHECK=1`：架构师本人绕过受保护路径 APPROVED-BY 检查

### 禁止 --no-verify（硬规则）

> **禁止使用 `git commit --no-verify` / `git push --no-verify`。如 hook 报错无法解决，停止并报告架构师，不绕过。**

本地 hooks 是 L0–L3 门禁体系的第一层。用 `--no-verify` 绕过等同于"自己给自己开后门"，会使"通过"不再代表"真通过"，动摇整个 gate 的可信度。详见 `docs/incidents/INC-001-no-verify-usage.md`。

---

## Dispatcher MVP（任务派发与回收）

给 L3 任务卡协议补上"执行/编排半壁"：两个一次性脚本把 ready 卡派发进隔离的 git worktree，交给 headless 会话执行，再回收判定。全程复用既有任务卡协议、scope 规则与 CI 判定权，**不新增常驻进程、不新增第三方依赖**（Python 3.14 标准库 + 仓库已在用的 pyyaml/jsonschema）。

中央配置 `.harness/dispatch.yaml`：**换模型只改 `model` 这一行**。

| 命令 | 作用 | 何时跑 |
|---|---|---|
| `python .harness/scripts/dispatch.py --dry-run` | 只读：列出本轮会派发什么（不改卡、不建 worktree、不起进程） | 每次真派发前先看 |
| `python .harness/scripts/dispatch.py [--max-tasks N]` | 占坑 → worktree 隔离 → headless 派发 → 记 `RUNS.jsonl` | 睡前 / 批量开工 |
| `python .harness/scripts/poll.py` | 回收：判活 → 机器门禁 → 通过等验收 / 失败重试 / 超限 blocked | 早晨 + 中间抽查 |

### 组件

| 文件 | 职责 |
|---|---|
| `scripts/runs.py` | `RUNS.jsonl` 运行记录库（append/get/update/list_running/attempts）；追加用真 append + 覆写用原子 `os.replace`，保障"崩了重跑即可续" |
| `scripts/run-exec.py` | 执行包装器：跑一条 executor 命令，落 `stdout.log/stderr.log/exitcode.txt`；自身退出码恒为 0（把"包装器崩了"与"任务失败"分开） |
| `scripts/dispatch.py` | 派发器（扫 ready 卡 → 占坑 → worktree → 拉起 headless → 记账），只做一轮，不常驻 |
| `scripts/poll.py` | 回收器（查 pid → 读 exitcode → 三层机器门禁 → pass 进 awaiting-review / fail 重试 / 超限 blocked），只做一轮，不常驻 |
| `scripts/check_local_scope_compat.py` | 按路径加载 `check-local-scope.py` 复用其 `glob_to_regex` 纯函数（复用不复制） |

### 判定权边界（不可让渡）

- **dispatcher / poll 永不写 `done`**。卡状态只会被改到 `in-progress`（占坑）或 `blocked`（超重试）；`done` 的唯一来源仍是人类 `verify-all.py` + `archive-task.py`。
- 机器门禁只做**轻量三层**：① 任务卡仍合法（`validate-task-card.py`）；② scope（变更文件必须落 `allow_write`、不触 `deny_write`；未跟踪目录用 `-uall` 逐文件校验，防目录折叠漏判）；③ 规模（`max_files_changed` / `max_lines_changed`）。**dotnet 全量 build/test 仍留在人类验收侧**，不进门禁。
- `pass` 只进 `awaiting-review`，等人类验收。

### 运行约定

- **同一时刻只允许 `dispatch.py` 或 `poll.py` 之一在跑**：`RUNS.jsonl` 无跨进程锁，串行是"崩了重跑即可续"的前提。
- **headless 执行器不得在 worktree 内自行 `git commit`**：机器门禁按 worktree 的**未提交**改动统计 scope/规模；若执行器已提交，porcelain 为空会被判 `fail-gate` 重试（base-commit 口径统计属 Phase 2）。
- 运行记录 `.harness/runs/RUNS.jsonl`、隔离工作区 `.harness/worktrees/` 均已 gitignore，不入仓。

### 跑测试

```
python -m unittest discover -s .harness/tests -t .harness -v
```

> `-t .`（以仓库根为顶层）在 Python 3.14 下会因目录名 `.harness` 以点开头的非法包名报 `ImportError: KeyError: ''`；顶层须用 `-t .harness`。

### 非目标（Phase 2）

超时熔断（per-run timeout）、事件看板 / UI、dotnet 全量进门禁、`depends_on` 跨卡拓扑排序、worktree base-commit 精确规模统计、`RUNS.jsonl` 跨进程锁。

---

## Phase2（真路由常驻循环 / skill / 重规划 / 九阶段管线）

### loop 常驻循环

```bash
python .harness/scripts/loop.py [--once] [--max-cycles N] [--sleep S] [--stop-file PATH] [--max-tasks N]
```

- 每轮顺序 `dispatch → pipeline → poll`（subprocess 调度，复用各脚本 `main` 语义；loop 只做调度，不做业务判定）。
- `--once` 只跑一轮就退出；`--max-cycles N` 跑满 N 轮退出；`--sleep S` 覆盖轮间隔（默认取 `dispatch.yaml` 的 `loop_interval_seconds`）；`--max-tasks N` 透传给 dispatch/pipeline 限本轮派发数。
- **单实例**：启动即原子 `mkdir` 抢 `<runs_dir>/loop.lock`（内写 pid，`finally` 释放）；锁 `mtime` 超 600 秒视为 stale 可打破；第二个实例抢锁超时直接退出——**同一时刻只允许一个 loop 在跑**。
- **STOP**：默认 STOP 文件为 `<runs_dir>/STOP`（`--stop-file` 可改）；轮前轮后检查到 STOP 文件存在即正常退出（码 0）；Ctrl+C 同样正常退出。停常驻循环：建 STOP 文件即可，无需杀进程。

### 常驻接线

loop 本身不做进程守护，**崩溃靠外部拉起**：

- Windows 任务计划程序（登录即跑，崩了由计划程序重启动拉起）：

  ```
  schtasks /create /tn JQKJ-Harness-Loop /tr "python F:\JQKJ\.harness\scripts\loop.py" /sc onlogon
  ```

- cron（每 5 分钟跑一轮 `--once` 即走即退，无需守护）：

  ```
  */5 * * * * python /path/to/.harness/scripts/loop.py --once
  ```

### `pipeline:true` 卡语义

- 卡上写 `pipeline: true` 即管线卡：`dispatch.py` 的 `is_eligible` 直接跳过（`poll.py` 回收时同样跳过，提示"已转管线，poll 跳过"）。
- 管线卡由 `pipeline.py` 按**九阶段**推进：`analysis → spec → plan → execute → check → test → evidence → accept → pr`，一轮只推进一步；运行账本另开 `.harness/runs/PIPELINE.jsonl`（`owner: pipeline`），与 dispatch 的 `RUNS.jsonl` 槽位互通（`running_count` 全量查询防超发）。

### 模型路由真相（modelswap 真路由）

- 换模型只改 `dispatch.yaml` 的 `model` 这一行；DSH 模型唯一来源是 settings（`dsh_settings`，默认 `~/.dsh/settings.yaml`）的 `agent-default-model{provider,model}`——`dispatch.yaml` 的值经 `settings.yaml` 生效（卡自带 `model` 优先，否则回退全局）。
- 有自带 `model` 的卡走派发时 swap：spawning 前持 `modelswap.lock` 锁做"读 + 备份 + 原子写"，只毫秒级；收尾 `maybe_restore` 恢复现场（只看本轮刚收尾的 swapped 记录，全量含 pipeline 查询确认无 running 占用才恢复）。
- 无自带 `model` 的卡要求 DSH 现状（provider+model 全比）与全局 `model` 一致，**不一致 fail-fast 跳过本卡**（不派发，顺延）；同轮多模型只派第一组模型相同的卡，其余顺延下轮。
- `model_fallbacks` 为降级链（失败按 `replan.py` 的 `plan_retry` 顺延下一模型，`failure_note` 带往下一轮针对性修复）。

### 预算数字

| 项 | 值 | 位置 |
|---|---|---|
| `failure_note` 截断 | 2000 字符（只留尾部） | `prompt_budget.failure_note_max_chars` |
| skill 单文件上限 | 12KB（12288 字节，按 UTF-8 字节截断留尾，标"已截断"） | `prompt_budget.skill_max_bytes` |
| skill 加载 | 按卡 opt-in：卡写 `skills:` 字段才内联（`--` 落 `.harness/context/<TASK>-skills.md` 并拼进 prompt） | 卡字段 + `skills_dir` |

### skill opt-in 与 TDD 证据规则（fail-skill）

- skill 内联只读 `skills_dir` 下的 `SKILL.md`，找不到的 skill 名静默跳过；除 `test-driven-development` 外均为 instruction-only（仅 prompt 指令，无机器证据）。
- `test-driven-development` 有机器证据：变更文件必须触碰卡上 `acceptance_tests` 任一文件，否则判 `fail-skill`（poll 侧消耗一次 retry，超 `max_retries` 转 blocked；管线 execute/check 侧直标 blocked，均等人工）。

### 机器自动验收三规则（run_accept）

1. **dispatcher 永不写 `[APPROVED-BY]`**：机器验收提交（`status: done` + 归档）故意不带人工批标记，靠 commit-msg hook 的 done 路径放行。
2. **触碰 `tests/`、`contracts/`、`.harness/`、`.githooks/` 任一受保护路径的卡，必须 `pre_approved: true`，否则直接转人工**（不跑 verify）。
3. **`verify-all` 以 `--operator dispatcher` 运行，且禁传 `--approve-protected-paths`**（机器无权批受保护路径）。

### pr：默认手工、只开不开合、永不 merge（铁律 13）

- `pr_enabled: false`（默认）→ `run_pr` 直接返回 `pr-manual`，按 README 手工开 PR；即使开关打开，`run_pr` 也只做 `push + gh pr create`（只开），**永不 merge**——合并永远是人类的事。

