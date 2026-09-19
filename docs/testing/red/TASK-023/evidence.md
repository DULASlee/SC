# TASK-023 红绿证据（commit-msg E1 移除 + 纯 path 判定）

生成：临时 git 仓 + 真实 hook（docs/ai-workspace/hooks/commit-msg）
+ 真实 check_approval.py；staged 文件为 .harness/tasks/active/ 卡文件。

## R1：conventional 前缀 + 无 TASK 引用 → 拒绝
期望 PASS → 实际 PASS

```
[FAIL] commit message 必须引用 TASK-XXX
       当前消息首行：chore: bump dependency
       示例：TASK-042 feat: implement edge buffer
       （TASK-023 起 E1 豁免移除，conventional 前缀不再免卡引用）
```

## R2：TASK 引用 + 保护路径无覆盖卡 → 拒绝
期望 PASS → 实际 PASS

```
[FAIL] 触碰受保护路径，但无覆盖 active 卡（含非空 approver 字段）：.harness/tasks/active/TASK-999.yaml
[FAIL] 触碰受保护路径，但无覆盖 active 卡（含非空 approver 字段）
       修复方式：找覆盖该文件的 active 卡并请架构师填 approver 字段
       或架构师本人设 SKIP_PROTECTED_CHECK=1

       ⚠  .github/workflows/ 修改需架构师批准（CI 配置不能自改）
```

## G1：覆盖卡（ready+approver+自覆盖）→ 放行
期望 PASS → 实际 PASS

```
[OK] 受保护路径已有覆盖卡批准
```

## G2：自生命周期：done 卡覆盖自身卡文件提交 → 放行
期望 PASS → 实际 PASS

```
[OK] 受保护路径已有覆盖卡批准
```

## G3：SKIP_PROTECTED_CHECK=1 跳过路径判定（TASK 引用仍在）
期望 PASS → 实际 PASS

```

```

## G3b：SKIP 不跳 TASK 引用（最小特权）
期望 PASS → 实际 PASS

```
[FAIL] commit message 必须引用 TASK-XXX
       当前消息首行：chore: no task ref
       示例：TASK-042 feat: implement edge buffer
       （TASK-023 起 E1 豁免移除，conventional 前缀不再免卡引用）
```

总体：ALL PASS
## R4（真实案例，非生成脚本）：首个 023 提交被新门禁拦截

- 首次 git commit -- <23 paths> 被 commit-msg 拒：暂存区遗留前会话 9 个受保护文件
  （dispatch.yaml/schema/canary.py/modelswap.py/poll.py/replan.py/runs.py/PILOT-CHECKLIST.md/test_gates.py）无覆盖卡。
- 处置：git reset -- 移出暂存（工作树内容保留，未丢失），重跑 check_approval --staged → [OK]，重提交通过。
- 证明：纯 path 判定对「索引里夹带的未授权保护路径提交」真实生效（R2 在真实仓库的实例）。
