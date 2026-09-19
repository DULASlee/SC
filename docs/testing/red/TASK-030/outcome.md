# TASK-030 改后证据（ASCII 归零 + 拦截仍触发）

## P1：validate-task-card --all 绿路径
结果：PASS

```
exit=0 ascii=True
e-url-domain-error.yaml
[OK]   TASK-022-harness-scripts-cover.yaml
[OK]   TASK-023.yaml
[OK]   TASK-024.yaml
[OK]   TASK-029.yaml
[OK]   TASK-030.yaml
[OK]   TASK-031.yaml

all task cards validated OK
```

## P2：check-contract-consistency 绿路径
结果：PASS

```
exit=0 ascii=True
[OK] L1-alpha check passed: all $ref resolvable, all schemas non-empty.
```

## P3：pre-push 输出字面量零非ASCII + 故意违规仍拦截
结果：PASS

```
residual_literals=none exit=1 ascii=True
=== pre-push gate ===
stub: forced fail
[FAIL] full test run failed: tests/GenCollector.Tests/GenCollector.Tests.csproj
```

## P4：validate-task-card 坏卡仍拦截
结果：PASS

```
exit=1
[FAIL] bad-card.yaml
       - Schema validation failed: 'scope' is a required property (path: [])

1 error(s) total
```

## P5：contract-consistency 注入非法 JSON 仍拦截
结果：PASS

```
exit=1 (注入文件已删)
[FAIL] L1-alpha check failed (1 error(s)):
  - JSON invalid: zz-030-evidence.json - Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
```

总体：ALL PASS