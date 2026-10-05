# TASK-024 C5 证据：deny_write 四执行点复核

| 执行点 | 证据 |
|---|---|
| check_approval.py:97-98 | 既有单测 test_check_approval.test_deny_hit_rejects / test_lifecycle_deny_hit_rejects（unittest discover 运行） |
| poll.py:132-135 | 既有单测 test_poll.test_scope_check_rejects_deny_write |
| check-pr-scope.py:237-250 | 本脚本 P1/P2（CLI 冒烟，临时卡 TASK-999，不污染 active/） |
| check-local-scope.py:105-119 | 本脚本 P3/P4（同法） |

## P1：check-pr-scope：deny 命中 → [DENY] 拒绝
结果：PASS

```
[INFO] Task IDs: TASK-999

[FAIL] 发现 1 处 scope 违规：
  - [DENY] tests/b.txt 触碰了 deny_write(TASK-999: tests/**)

修复方式：将变更限制在任务卡 allow_write 范围内，或申请新任务卡。
```

## P2：check-pr-scope：allow 命中 → 放行
结果：PASS

```
[INFO] Task IDs: TASK-999
[OK] scope 检查通过：1 张卡，1 文件，1 行变更
```

## P3：check-local-scope：deny 命中 → [DENY] 拒绝
结果：PASS

```
[INFO] using task card: TASK-999.yaml (status: ready)

[FAIL] 1 scope violation(s):
  - [DENY] tests/b.txt touches deny_write

Fix: limit changes to the card allow_write, or open a new task card.
Note: protected paths (.github/, tests/, .harness/, ...) are enforced by the commit-msg hook + check_approval.py: an active card whose allow_write covers the file with a non-empty approver field, or architect sets SKIP_PROTECTED_CHECK=1.
```

## P4：check-local-scope：allow 命中 → 放行
结果：PASS

```
[INFO] using task card: TASK-999.yaml (status: ready)
[OK] scope check passed: 1 file(s), 2 line(s)
```

C5 结论：四执行点 deny 约束全部在位，销项 CLOSED