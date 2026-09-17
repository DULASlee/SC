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
- `git commit -m "..." --no-verify`：跳过所有 hooks（**不推荐**，违反 L5 规则 2）

