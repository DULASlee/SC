# TASK-033 判据 5 故意违规证据

## C：合法基线（无 approver，全字段已声明）
结果：PASS

```
exit=0
[OK]   ghost-card.yaml

all task cards validated OK
```

## A：幽灵字段（未声明）被拒
结果：PASS

```
exit=1
[FAIL] ghost-card.yaml
       - Schema validation failed: Additional properties are not allowed ('ghost_field' was unexpected) (path: [])

1 error(s) total
```

## B：approver 枚举外值被拒（需 033 修复 schema 后才可断言）
结果：PASS

```
exit=1
[FAIL] ghost-card.yaml
       - Schema validation failed: 'Architec' is not one of ['architect'] (path: ['approver'])

1 error(s) total
```

## A2：approver=architect（033 修复 schema 后应 PASS）
结果：PASS

```
exit=0
[OK]   ghost-card.yaml

all task cards validated OK
```

说明：A=检测面闭环证明（幽灵字段被拒）；B/A2=approver 字段 schema 定义前后行为对照。