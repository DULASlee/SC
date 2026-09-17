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
