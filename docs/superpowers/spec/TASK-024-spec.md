# TASK-024 Spec — 声明项 AT-0 扫描（实现或删除）+ 编码一致性

> 状态：工程师起草，待架构师对裁定清单逐项签发后开工。
> 架构师裁定：023 保持 CLOSED；「Windows/Git Bash/Python stdout-stderr 编码一致性」归入 024。

## 背景

- 024 的 AT-0 = 扫描所有**声明了但不执行**的项，二元处置：**实现或删除**。
  装饰性防护比没有更危险（制造虚假信心）。
- 023 已移除 E1 豁免并实现 SKIP_PROTECTED_CHECK=1，扫描基线为 023 后状态。
- 022 保留 deny_write 扫描（原 E2 病：「声明了但不执行」）——本轮侦察显示
  deny_write 在 4 个执行点均已生效，需 AT-0 复核销项而非加代码。

## 裁定清单（逐项：证据 → 建议处置）

| # | 声明项 | 证据 | 建议处置 |
|---|---|---|---|
| C1 | `EXEMPT_PREFIXES` 声明 | `check-protected-paths.py:34`（`("chore:", "docs:")`）+ docstring 行 5-7/13；`main()` 从不引用（行 49-65 仅 SKIP + 直通）；023 后 commit-msg 亦已无豁免 | **删除**（死声明，E1 同病） |
| C2 | pre-commit 教育性提示 | `.githooks/pre-commit:74-75`：「protected path → commit message 加 [APPROVED-BY] / 或用豁免前缀 (chore:/docs:)」——两通道 023 后均不存在 | **修订**提示为：找覆盖 active 卡（allow_write + 非空 approver），或架构师 SKIP_PROTECTED_CHECK=1 |
| C3 | hook 输出编码 | AGENTS 规则 4「hook 脚本输出只用 ASCII」现行违反：`commit-msg`/`check_approval.py` 中文 echo/print，Windows python 重定向走 GBK、Git Bash 走 UTF-8 → 混合编码（023 红态证据已实证 0xb4 解码失败） | **实现**：全部 hook 面向输出 ASCII 化（[OK]/[FAIL] + ASCII 细节）；不改 023 已关面的授权语义 |
| C4 | `check-protected-paths.py` 定位 | `main()` 为直通 + SKIP 出口（行 57-65）；注释声明「CI 防御层」但 `ci.yml` 无对应 job；其唯一实质功能（APPROVED-BY/豁免）023 后由 commit-msg + check_approval 承担 | **删除脚本** + 移除 `pre-commit:15` 调用（SKIP 通道已在 commit-msg 实现）；或架构师裁定保留为独立 CLI 真接线 CI |
| C5 | deny_write 执行复核 | 执行点：`check_approval.py:97-98`（deny 优先不覆盖）、`check-pr-scope.py:237-250`（allow 先行 + [CONFIG-CONFLICT]）、`check-local-scope.py:105-119`、`poll.py:132-135`（fail-scope） | **复核销项**：4 点均生效 → 关闭 E2 主张，零新代码；缺任一点 → 补齐 |
| C6 | `check_local_scope_compat.py` 存在性与用途 | 022 allow_write 枚举之；需核对文件存在 + 与 check-local-scope 的关系 | 核对后**删除或保留**（重复实现即删） |
| C7 | check-local-scope 自动模式语义 | 前会话 pre-commit 输出：「唯一活动任务卡，0 个 >= 2 个 ready/in-progress」WARN——少卡场景降级 WARN 是否符合设计 | **复核**：维持 WARN 不 FAIL；必要时修文案（不改变降级语义） |

## 方案（依裁定执行，默认取「建议处置」列）

1. C1：删 `check-protected-paths.py:34` + 修订其 docstring（或随 C4 整文件删除）。
2. C2：`.githooks/pre-commit` 修复指南 5-6 行改为卡 + approver / SKIP 双通道。
3. C3：`commit-msg` / `check_approval.py` 面向 stdout/stderr 的输出 ASCII 化
   （中文移入 `notes`/文档，不进 hook 输出）；新增断言测试（hook 输出无非 ASCII 字节）。
4. C4（若裁定删除）：删 `check-protected-paths.py` + `pre-commit:15` 行；
   `check-protected-paths.py` 被 022 allow_write 覆盖，024 卡需自列该文件。
5. C5：跑 4 个执行点现有测试 + 补 deny 优先红态证据（`docs/testing/red/TASK-024/`），
   全绿即销项。
6. 回归：`.harness/tests` 全量 + `validate-task-card --all` + pre-commit 全绿。

## 验收

- AT-0 扫描报告 + 逐项处置证据入 `docs/testing/red/TASK-024/`（删除项：grep 零残留；
  实现项：红态 → 绿态命令输出）。
- 新增/修订输出断言测试绿；`.harness/tests` 全量绿。
- `validate-task-card.py --all` 全 OK；本卡提交经新 commit-msg 纯 path 门禁放行（自宿主回归）。

## 执行前置

- 铁律 15（执行器链路 canary，本轮 7778f64 混入证据已入库）：024 不触 executor_argv/
  执行机器，无需 canary probe；若 024 执行中发现需动 executor 链路，先 canary 留证再动。
