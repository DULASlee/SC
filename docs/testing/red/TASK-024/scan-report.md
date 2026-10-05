# TASK-024 AT-0 扫描报告（声明项证据先于处置）

生成：2026-09-19，TASK-024 施工轮。配套证据：`deny-evidence.md`（C5）、
`run_evidence.py`（可重跑）。

## C4 全仓引用扫描：check-protected-paths.py（零 live 引用证明）

`grep -r "check-protected-paths"` 全仓 17 处命中，逐条分类：

| 命中 | 分类 | 处置 |
|---|---|---|
| `.githooks/pre-commit:15` | **唯一 live 调用**（pre-commit 步骤 1） | 本 commit 随 C4 移除该调用 + 删脚本 |
| `.harness/tasks/active/TASK-022…yaml` allow_write/references/notes | 授权条目（非调用），022 为 in-progress 常驻覆盖卡 | 删脚本后条目悬空但无害（glob 永不命中不存在文件）；随 022 卡下次修订清理（架构师面，非 024 射程） |
| `.harness/tasks/active/TASK-024.yaml` allow_write:11 | 本卡授权条目（覆盖本次删除操作本身） | 保留（删除提交的授权依据） |
| `.harness/tasks/archive/TASK-002.yaml:11` | 历史归档卡 | 不动（历史工件原则） |
| `harness/*.md`（l0-local-ci-report / diag-stage1 / round3 等） | 历史报告 | 不动（历史工件） |
| `.harness/rules/governance.md:24` | 文字陈述：「pre-commit hook（check-protected-paths.py）拦截超 scope」——**与事实不符**（实际拦截者是 check-local-scope.py，步骤 3） | **残留项**：governance.md 不在 024 卡 allow_write，随下次 governance 修订更正（记录在案，非 024 扩面） |
| `.harness/scripts/check-local-scope.py:128` | 提示文字（旧模型「check-protected-paths.py 独立拦截（需 APPROVED-BY）」） | 本 commit C2 已修订为现行模型 |
| `docs/superpowers/spec/TASK-024-spec.md` C1/C4 行 | 本 spec 证据引用 | 保留（施工记录） |

**结论：删除 pre-commit:15 调用后，全仓零 live 引用、零 import、零 CI job、
零测试契约（test_gates.py 等前会话遗留文件亦无引用）。C4 删除成立。**

## C6 引用/契约复核：check_local_scope_compat.py

- 文件存在（14 行）；内容 = importlib 按路径加载 `check-local-scope.py`（文件名含连字符无法直接 import）
  并 re-export `glob_to_regex` 纯函数——**适配器，非重复实现**（docstring 明写「复用不复制」）。
- live 调用方：`poll.py:24` `from check_local_scope_compat import glob_to_regex`。
- 文档契约：`.harness/README.md:255`（scripts 清单表明确该文件唯一职责）+
  `docs/superpowers/plans/2026-09-19-harness-dispatch-mvp.md:885-896`（创建决策记录）。
- **裁定：保留（有 live 调用方 + 文档契约 + 唯一职责明确，不满足「无调用方/无契约」删除条件）。零代码变更。**

## C7 复核：check-local-scope 自动模式 WARN 语义

- `find_active_task()`（check-local-scope.py:69-80）：ready/in-progress 卡数 ≠1（0 或 ≥2）时
  打印 WARN 并跳过 scope 检查（exit 0）——现行事实：active/ 14 张卡（含多张 ready/in-progress）
  → 恒走 ≥2 分支 → WARN 跳过 = 当前实际行为，文案「0 或 >= 2 个 ready/in-progress」与代码一致。
- **裁定：维持 WARN 语义，文案与事实一致，零变更。**

## C1 处置记录

`EXEMPT_PREFIXES`（check-protected-paths.py:34 + docstring 行 5-7/13）为 023 后死声明：
`main()` 从不引用；commit-msg 侧 E1 已随 023 移除。随 C4 整文件删除而彻底清除，
全仓无独立残留（C4 扫描表即 C1 零残留证明）。

## C3 余面（超出 024 卡 allow_write，记录待裁）

本轮 C3 ASCII 化覆盖：`commit-msg`、`check_approval.py`、`.githooks/pre-commit`、
`check-local-scope.py`（均在 024 卡 allow_write 内）+ 输出 ASCII 断言测试
（test_check_approval.TestAsciiOutput，3 用例）。

**余面（未改，需架构师扩 024 卡面或另开卡）**：
- `docs/ai-workspace/hooks/pre-push`（hook，但不在 024 allow_write）：行 12/23/37/42/44/49/51/56/60/63 中文输出
- `validate-task-card.py` / `check-contract-consistency.py`（pre-commit 子步骤，非 024 allow）中文 echo
- `check-pr-scope.py` / `start-task.py` / `dispatch.py` 等 CI/本地工具中文输出（非 hook，属可观察性增强，非 AGENTS 规则 4 射程）

## C5 销项

四执行点证据见 `deny-evidence.md`：
check_approval:97-98（单测 2 例）、poll:132-135（单测 1 例）、
check-pr-scope:237-250（CLI 冒烟 P1/P2）、check-local-scope:105-119（CLI 冒烟 P3/P4）。
**deny_write 约束四点全在位，E2 主张关闭，零新实现代码。**

## 过程缺陷记录（7778f64）

- 缺陷：一次未使用 pathspec 的 index 整提交，混入前会话暂存遗留 2 项
  （TASK-TEMPLATE.yaml +3 行 approver 模板行；engineering-rules.mdc +6 行铁律 15 canary）。
- 核验：内容均与现行治理一致（canary 与已在 HEAD 的 canary.py 配套；approver 模板行与 023 模型一致），
  门禁授权，无越权范围。
- 处置（架构师裁定）：不回滚；后续提交统一 pathspec 限定。本 commit 起已执行。
