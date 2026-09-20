# TASK-042 红→绿证据链

## 红（实现前）
- red-01-start-session.txt：4 tests, FAILED(errors=4)（模块不存在）
- red-02-registration-hook.txt：5 tests, FAILED(errors=5)
- 时间：2026-09-20T16:5xZ；命令：python -m unittest discover -s .harness/tests -t .harness -k start_session / -k check_session

## 绿（实现后，同命令）
- start_session：Ran 4 tests OK
- check_session：Ran 5 tests OK
- 全量回归：Ran 156 tests in 12.358s OK（基线 147 + 新增 9，零回归）
- 门禁实跳：本卡提交时主树 pre-commit 输出 "[OK] main-tree commit, registration check skipped"；
  未登记 worktree 提交被拒（test_unregistered_worktree_fails + FAIL 退出码 1 固化于测试）

## 实现落点
- .harness/scripts/start-session.py（登记入口：ensure_worktree 复用 + 卡状态预检 + 主树锚点登记簿）
- docs/ai-workspace/hooks/check_session_registration.py（pre-commit 引擎，ASCII，fail-closed）
- .githooks/pre-commit（+step 0：登记门禁，无绕过通道）

## 边界自证（v1.1 §15）
未动：全局 ledger / model routing / task 状态权威（卡不翻状态，claim 完整语义属 P5）/
其余 Hook。登记簿落主树 <runs>/sessions/（协调根仓库级，A5；不新建目录树）。
