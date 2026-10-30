# 常驻循环启动说明（P4）

循环本体：仓库自带的常驻调度脚本（单实例锁、顺序跑六棒、STOP 文件退出）。

## 手动跑一轮（安全演练）

```text
python .harness/scripts/loop.py --once --no-merge
```

只调度不合入不归档，用于验证接线。

## 常驻（Owner 在本机启一次）

Windows 计划任务示例（每 20 分钟一轮）：

```text
schtasks /create /tn HarnessLoop /tr "python F:\JQKJ\.harness\scripts\loop.py" /sc MINUTE /mo 20
```

停用：`schtasks /delete /tn HarnessLoop /f`，或在账本目录放 STOP 文件。

## 行为

- 空轮（无活）正常退出码 0，各棒均被调用。
- 断点后续跑：锁释放后重进，无重复派发（占坑与认领是原子的）。
