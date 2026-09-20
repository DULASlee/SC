# DSH Shell 沙箱 Runner 故障排障 Runbook（Windows）

- 关联：TASK-018；背景见 `docs/reports/TASK-017-ci-scope-fix-verification.md`
- 适用：DSH（DeepSeek Harness）在 Windows 上的 shell 工具

## 症状

- shell 工具（`pwsh`）每次调用立即退出，退出码 **3221225794（0xC0000142，STATUS_DLL_INIT_FAILED）**
- **stdout / stderr 完全为空**，连最简单的命令（`echo`）都无输出
- 嵌套调用 `cmd.exe`、`powershell.exe`、后台运行、缩短超时——现象完全一致

## 关键判断：先别下"pwsh 没装/损坏"的结论

0xC0000142 是**进程启动期**错误。在 DSH 里，命令实际经过沙箱 runner 包装后再启动，
因此同样的退出码有两种完全不同的根因，必须先区分：

1. 目标 shell（pwsh/powershell）本身缺失或损坏；
2. **沙箱 runner（workspace-write 的 Windows ACL restricted-token runner）自身启动失败**
   —— 此时 shell 本体是好的，只是命令从未被执行。

TASK-017 的实测：pwsh 7.4.5 装在非标准盘（`D:\Program Files\PowerShell\7\pwsh.exe`）、
git / dotnet / python 均健康；故障来自沙箱 runner，与 shell 无关。

## 诊断顺序（从快到慢）

1. **用更高权限档试跑同一命令**：把该次调用提升到 `danger-full-access`（绕过沙箱 runner）。
   - 立刻正常 → 是沙箱 runner 问题（本 runbook 场景），不是 shell 问题。
   - 仍 0xC0000142 → 才去查 shell 本体 / 系统 DLL。
2. 确认 shell 真实位置（别只搜 C 盘标准路径）：
   `where.exe pwsh`、`where.exe powershell.exe`；PowerShell 7 可能装在其他盘或
   `%USERPROFILE%\.dotnet\tools` 垫片下。
3. 确认 Windows PowerShell 5.1 是否存在：
   `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`（系统内置）。
4. 仅当第 1 步证明与沙箱无关时，才查 VC++ Redist / .NET runtime / 事件查看器
   （Application Error、SideBySide）。

## 临时缓解（workaround）

在 runner 修复前，需要执行 shell 的会话显式使用 `danger-full-access` 档。
这是绕过文件系统沙箱，仅应在受信任仓库、受信任任务下使用，并知悉其不再提供写围栏。

## 目标修复（TASK-018 主路径，DSH 宿主侧，运维批次）

- 修复 Windows restricted-token runner 的进程启动（使 workspace-write 下能正常拉起子进程）。
- **预检 + 显式提示**（轻量折中）：workspace-write 会话在首次执行 shell 前做一次活性探测；
  命中 0xC0000142 / runner 不可用时，返回可读错误，明确提示
  「shell 沙箱 runner 启动失败（非命令问题），可将本次会话切到 danger-full-access 继续」，
  而不是让每条命令静默失败、把用户引向错误的 shell 重装方向。

## 验收标准

- workspace-write 下 runner 健康时：命令正常执行。
- runner 不可用时：模型/用户看到明确的切档提示，而非空输出 + 0xC0000142。
- 本 runbook 足以让不了解 TASK-017 经过的工程师独立完成定位。
