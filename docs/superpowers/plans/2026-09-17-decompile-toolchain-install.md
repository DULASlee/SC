# 反编译工具链安装与工作区二进制分析 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 25H2 环境下装齐 A+B 双轨反编译工具链（ILSpy + ILSpyCmd + dnSpyEx + Ghidra），对 `f:\JQKJ` 工作区下 5 类代表性二进制做反编译并产出结构化分析报告。

**Architecture:** 分轨安装（A=.NET 工具链 / B=原生二进制工具链）→ 逐工具冒烟测试 → 选取代表性样本 → 反编译并提取关键证据 → 汇总到一份 Markdown 报告。

**Tech Stack:**
- 包管理：`winget` v1.29（dnSpyEx、Ghidra）、`dotnet tool -g`（ilspycmd）
- 反编译：ILSpy 11（GUI）、ILSpyCmd 11（CLI）、dnSpyEx 6.6.0（GUI+调试）、Ghidra 12.1.3（原生二进制）
- 辅助：`file` 命令（PE 头检测）、PowerShell 7（pwsh）

---

## 环境前置（已验证，跳过）

- [x] .NET SDK 10.0.401 + Windows Desktop Runtime 10.0.12 已装（ILSpy 11 需要）
- [x] JDK 24.0.1 已装（Ghidra 12 需要 JDK 21+）
- [x] winget v1.29.290 可用
- [x] PowerShell 7（pwsh）可用

---

## 工作区二进制档案（用于选样本）

| 类型 | 代表样本 | 大小 | 推荐工具 |
|---|---|---|---|
| .NET 自宿主 exe（小型） | `CNC04/LnkCollector.exe` | 129 KB | ILSpy |
| .NET 启动器（极小，< .NET 工具集） | `DHH02/HanBaCollector.exe` | 10 KB | ILSpy |
| .NET 业务 exe | `DHH04/MelCollector.exe` | 234 KB | ILSpy |
| .NET 业务 dll | `CNC04/RemoteComm.dll` | 75 KB | ILSpy |
| .NET 第三方 dll | `DHH02/HslCommunication.dll` | 4.4 MB | ILSpy |
| .NET 自宿主 exe（大型） | `CNC/iot_CNC_PLC_IMM.exe` | 15.7 MB | ILSpy + Ghidra（混合可能） |
| C++ 原生 dll | `DHH02/PocoFoundation.dll` | 1.6 MB | **Ghidra** |
| C++ 原生 dll | `DHH04/MknEdmRm1201.dll` | 135 KB | **Ghidra** |

---

## Task 1：安装 ILSpyCmd（.NET CLI 反编译器）

**Files:**
- Create: `f:\JQKJ\.tools\bin\ilspycmd.cmd`（PATH shim，可选）

- [ ] **Step 1.1：安装 ILSpyCmd 为全局 dotnet 工具**

```powershell
dotnet tool install --global ilspycmd
```

Expected: 工具安装成功，提示 "Tool 'ilspycmd' was successfully installed."，版本 ≥ 11.0.0.9375。

- [ ] **Step 1.2：验证 ilspycmd 可调用**

```powershell
ilspycmd --version
```

Expected: 输出形如 `11.0.0.9375` 或类似版本号。Exit code 0。

- [ ] **Step 1.3：验证 ilspycmd 帮助**

```powershell
ilspycmd --help
```

Expected: 显示 usage，包含 `-il` / `-ilsequence` / `-p` / `-o <directory>` 等参数说明。Exit code 0。

---

## Task 2：安装 ILSpy GUI（.NET 桌面反编译器）

**Files:**
- Install: `%LOCALAPPDATA%\Programs\ILSpy\ILSpy.exe`

- [ ] **Step 2.1：尝试 winget 安装 ILSpy**

```powershell
winget install --id icsharpcode.ILSpy --accept-package-agreements --accept-source-agreements
```

Expected: 找到 `ILSpy` 包并提示安装成功；若失败（如包 ID 不对），fallback 到 GitHub Release 下载。

- [ ] **Step 2.2（fallback）：从 GitHub Release 下载**

```powershell
$ghTag = (Invoke-RestMethod "https://api.github.com/repos/icsharpcode/ILSpy/releases/latest").tag_name
$assetName = "ILSpy-$ghTag-win-x64.zip"
$url = "https://github.com/icsharpcode/ILSpy/releases/download/$ghTag/$assetName"
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.tools\ilspy" | Out-Null
Invoke-WebRequest -Uri $url -OutFile "f:\JQKJ\.tools\ilspy\$assetName"
Expand-Archive -Path "f:\JQKJ\.tools\ilspy\$assetName" -DestinationPath "f:\JQKJ\.tools\ilspy\extracted" -Force
```

Expected: 下载 zip 文件，体积约 80-150 MB，解压后得到 `ILSpy.exe`。

- [ ] **Step 2.3：验证 ILSpy 启动**

```powershell
$ilspyExe = Get-ChildItem "f:\JQKJ\.tools\ilspy" -Recurse -Filter "ILSpy.exe" | Select-Object -First 1
& $ilspyExe.FullName --help
```

Expected: 显示 ILSpy 启动信息或 CLI 帮助（ILSpy 11 支持 `--help`）。Exit code 0。

- [ ] **Step 2.4：创建 PATH shim**

```powershell
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.tools\bin" | Out-Null
$ilspyGui = $ilspyExe.FullName
"@echo off`n`"$ilspyGui`" %*" | Out-File -FilePath "f:\JQKJ\.tools\bin\ilspy.cmd" -Encoding ASCII
```

Expected: `f:\JQKJ\.tools\bin\ilspy.cmd` 存在，调用时启动 ILSpy GUI。

---

## Task 3：安装 dnSpyEx（.NET GUI + 调试器）

**Files:**
- Install: `f:\JQKJ\.tools\dnspyex\dnSpy.exe`

- [ ] **Step 3.1：下载 dnSpyEx 6.6.0**

```powershell
$url = "https://github.com/dnSpyEx/dnSpy/releases/download/v6.6.0/dnSpy-net-win32.zip"
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.tools\dnspyex" | Out-Null
Invoke-WebRequest -Uri $url -OutFile "f:\JQKJ\.tools\dnspyex\dnSpy-net-win32.zip"
Expand-Archive -Path "f:\JQKJ\.tools\dnspyex\dnSpy-net-win32.zip" -DestinationPath "f:\JQKJ\.tools\dnspyex\extracted" -Force
```

Expected: 下载 zip（约 30-60 MB），解压得到 `dnSpy.exe`。

- [ ] **Step 3.2：验证 dnSpy.exe 存在并可启动**

```powershell
$dnSpyExe = Get-ChildItem "f:\JQKJ\.tools\dnspyex" -Recurse -Filter "dnSpy.exe" | Select-Object -First 1
Test-Path $dnSpyExe.FullName
```

Expected: 输出 `True`。

- [ ] **Step 3.3：创建 PATH shim**

```powershell
"@echo off`n`"$($dnSpyExe.FullName)`" %*" | Out-File -FilePath "f:\JQKJ\.tools\bin\dnspy.cmd" -Encoding ASCII
```

Expected: `f:\JQKJ\.tools\bin\dnspy.cmd` 存在。

---

## Task 4：安装 Ghidra（原生二进制 SRE 框架）

**Files:**
- Install: `f:\JQKJ\.tools\ghidra\ghidra_<ver>\ghidraRun.bat`

- [ ] **Step 4.1：查询 Ghidra 最新版本**

```powershell
$ghidraTag = (Invoke-RestMethod "https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest").tag_name
Write-Output $ghidraTag
```

Expected: 输出形如 `Ghidra-12.1.3-build-release`。

- [ ] **Step 4.2：下载 Ghidra**

```powershell
$ver = $ghidraTag -replace "^Ghidra-", "" -replace "-build-release$", ""
$assetName = "ghidra_${ver}_PUBLIC_$($ghidraTag -replace '^Ghidra-','' -replace '-build-release$','').zip"
$url = "https://github.com/NationalSecurityAgency/ghidra/releases/download/$ghidraTag/$assetName"
Write-Output "Download URL: $url"
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.tools\ghidra" | Out-Null
Invoke-WebRequest -Uri $url -OutFile "f:\JQKJ\.tools\ghidra\$assetName"
```

Expected: 下载 zip（约 400-600 MB），文件名含 `PUBLIC` 字样。

- [ ] **Step 4.3：解压 Ghidra**

```powershell
Expand-Archive -Path "f:\JQKJ\.tools\ghidra\$assetName" -DestinationPath "f:\JQKJ\.tools\ghidra\extracted" -Force
Get-ChildItem "f:\JQKJ\.tools\ghidra\extracted" -Filter "ghidraRun.bat" -Recurse | Select-Object FullName
```

Expected: 找到唯一的 `ghidraRun.bat`。

- [ ] **Step 4.4：验证 Java 环境对 Ghidra 可用**

```powershell
& "f:\JQKJ\.tools\ghidra\extracted\ghidraRun.bat" -help
```

Expected: 弹出 Ghidra 图形界面（若在 headless 环境）或输出 help。注：Ghidra 默认启动 GUI，可加 `-headless` 跑分析任务。

- [ ] **Step 4.5：创建 PATH shim + analyzeHeadless 别名**

```powershell
$ghidraRun = Get-ChildItem "f:\JQKJ\.tools\ghidra\extracted" -Recurse -Filter "ghidraRun.bat" | Select-Object -First 1
"@echo off`n`"$($ghidraRun.FullName)`" %*" | Out-File -FilePath "f:\JQKJ\.tools\bin\ghidra.cmd" -Encoding ASCII
"@echo off`n`"$($ghidraRun.DirectoryName)\support\analyzeHeadless.bat`" %*" | Out-File -FilePath "f:\JQKJ\.tools\bin\ghidra-headless.cmd" -Encoding ASCII
```

Expected: 两个 shim 创建成功，`ghidra.cmd` 启动 GUI，`ghidra-headless.cmd` 跑无界面分析。

---

## Task 5：创建工作区反编译输出目录与样本映射

**Files:**
- Create: `f:\JQKJ\.decomp\ilspy\<sample>\`（ILSpy/ILSpyCmd 输出）
- Create: `f:\JQKJ\.decomp\ghidra\<sample>\`（Ghidra headless 项目）

- [ ] **Step 5.1：创建输出目录骨架**

```powershell
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.decomp\ilspy" | Out-Null
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.decomp\ghidra" | Out-Null
New-Item -ItemType Directory -Force -Path "f:\JQKJ\.decomp\raw-evidence" | Out-Null
```

Expected: 三个目录创建成功。

- [ ] **Step 5.2：写入样本映射表（evidence 文件）**

文件 `f:\JQKJ\.decomp\raw-evidence\samples.json`：

```json
{
  "ilspy_targets": [
    {"name": "LnkCollector", "path": "f:\\JQKJ\\CNC04\\LnkCollector.dll", "category": ".NET 主程序集"},
    {"name": "HanBaCollector", "path": "f:\\JQKJ\\DHH02\\HanBaCollector.exe", "category": ".NET 启动器"},
    {"name": "MelCollector_DHH04", "path": "f:\\JQKJ\\DHH04\\MelCollector.exe", "category": ".NET 业务 exe"},
    {"name": "RemoteComm", "path": "f:\\JQKJ\\CNC04\\RemoteComm.dll", "category": ".NET 业务 dll"},
    {"name": "HslCommunication_DHH02", "path": "f:\\JQKJ\\DHH02\\HslCommunication.dll", "category": ".NET 第三方"}
  ],
  "ghidra_targets": [
    {"name": "PocoFoundation", "path": "f:\\JQKJ\\DHH02\\PocoFoundation.dll", "category": "C++ 原生"},
    {"name": "PocoJSON", "path": "f:\\JQKJ\\DHH02\\PocoJSON.dll", "category": "C++ 原生"},
    {"name": "PocoNet", "path": "f:\\JQKJ\\DHH02\\PocoNet.dll", "category": "C++ 原生"},
    {"name": "MknEdmRm1201_DHH04", "path": "f:\\JQKJ\\DHH04\\MknEdmRm1201.dll", "category": "疑似原生"}
  ]
}
```

Expected: JSON 文件写入成功，`Get-Content` 可读。

---

## Task 6：执行 ILSpyCmd 反编译（生成 .NET 源码）

**Files:**
- Create: `f:\JQKJ\.decomp\ilspy\<name>\*.cs`（每个样本一个目录）

- [ ] **Step 6.1：反编译 LnkCollector.dll**

```powershell
ilspycmd "f:\JQKJ\CNC04\LnkCollector.dll" -o "f:\JQKJ\.decomp\ilspy\LnkCollector"
```

Expected: 成功生成 C# 源文件到目标目录，至少包含 1 个 `.cs` 文件。

- [ ] **Step 6.2：反编译 HanBaCollector.exe**

```powershell
ilspycmd "f:\JQKJ\DHH02\HanBaCollector.exe" -o "f:\JQKJ\.decomp\ilspy\HanBaCollector"
```

Expected: 输出 .cs 文件。

- [ ] **Step 6.3：反编译 MelCollector.exe（DHH04）**

```powershell
ilspycmd "f:\JQKJ\DHH04\MelCollector.exe" -o "f:\JQKJ\.decomp\ilspy\MelCollector_DHH04"
```

Expected: 输出 .cs 文件。

- [ ] **Step 6.4：反编译 RemoteComm.dll**

```powershell
ilspycmd "f:\JQKJ\CNC04\RemoteComm.dll" -o "f:\JQKJ\.decomp\ilspy\RemoteComm"
```

Expected: 输出 .cs 文件。

- [ ] **Step 6.5：反编译 HslCommunication.dll（DHH02 副本）**

```powershell
ilspycmd "f:\JQKJ\DHH02\HslCommunication.dll" -o "f:\JQKJ\.decomp\ilspy\HslCommunication_DHH02"
```

Expected: 输出大量 .cs 文件（HslCommunication 是个大型库，会有数百文件），输出目录有内容即可。

---

## Task 7：执行 Ghidra headless 反编译（生成原生二进制 C 伪代码）

**Files:**
- Create: `f:\JQKJ\.decomp\ghidra\<name>\`（Ghidra 项目目录）
- Create: `f:\JQKJ\.decomp\ghidra\<name>\export\<func>.c`（导出伪代码）

- [ ] **Step 7.1：分析 PocoFoundation.dll**

```powershell
$proj = "f:\JQKJ\.decomp\ghidra\PocoFoundation"
$out = "$proj\export"
New-Item -ItemType Directory -Force -Path $proj, $out | Out-Null
& "f:\JQKJ\.tools\bin\ghidra-headless.cmd" $proj PocoFoundation -import "f:\JQKJ\DHH02\PocoFoundation.dll" -analysisTimeoutPerFile 600 -postScript ExportFunctionDecompile.java
```

Expected: Ghidra 项目生成，导入日志显示函数数。若 ExportFunctionDecompile.java 脚本缺失，fallback 用 `-decompile` 选项。

- [ ] **Step 7.2（替代方案）：用 analyzeHeadless + -decompile 导出伪代码**

如果上面失败，用：

```powershell
& "f:\JQKJ\.tools\bin\ghidra-headless.cmd" $proj PocoFoundation -process -decompile -noanalysis | Out-File "$out\decompile-summary.txt"
```

Expected: 输出文件包含至少部分函数的反编译伪代码片段。

- [ ] **Step 7.3：分析 PocoJSON.dll、PocoNet.dll、MknEdmRm1201.dll**

对剩下 3 个原生 dll 重复 Step 7.1/7.2 的流程，目标目录分别为 `PocoJSON`、`PocoNet`、`MknEdmRm1201_DHH04`。

Expected: 4 个 Ghidra 项目目录均有产物（至少分析日志 + 部分伪代码）。

---

## Task 8：提取关键证据 + 写入分析报告

**Files:**
- Create: `f:\JQKJ\docs\superpowers\reports\2026-09-17-decompile-analysis.md`

- [ ] **Step 8.1：收集元数据（PE 头、AssemblyInfo、函数数量）**

```powershell
$targets = Get-Content "f:\JQKJ\.decomp\raw-evidence\samples.json" | ConvertFrom-Json
$report = @()
foreach ($t in $targets.ilspy_targets) {
    $files = Get-ChildItem $t.path | Select-Object Name, Length
    $report += [PSCustomObject]@{Sample = $t.name; Type = ".NET"; Files = ($files | Out-String).Trim() }
}
$report | Format-Table -AutoSize | Out-File "f:\JQKJ\.decomp\raw-evidence\ilspy-meta.txt"
```

Expected: `ilspy-meta.txt` 包含每个 .NET 样本的元数据表。

- [ ] **Step 8.2：统计 ILSpyCmd 输出的代码规模**

```powershell
$stats = foreach ($dir in Get-ChildItem "f:\JQKJ\.decomp\ilspy" -Directory) {
    $csFiles = Get-ChildItem $dir.FullName -Filter "*.cs" -Recurse
    $totalLines = ($csFiles | Get-Content | Measure-Object -Line).Lines
    [PSCustomObject]@{Sample = $dir.Name; Files = $csFiles.Count; TotalLines = $totalLines}
}
$stats | Format-Table -AutoSize | Out-File "f:\JQKJ\.decomp\raw-evidence\ilspy-stats.txt"
```

Expected: 输出每个样本的 .cs 文件数和总行数。

- [ ] **Step 8.3：抽取 LnkCollector.dll 的关键类名（业务理解入口）**

```powershell
Get-ChildItem "f:\JQKJ\.decomp\ilspy\LnkCollector" -Filter "*.cs" -Recurse |
    Select-String -Pattern "^\s*(public|internal|private)?\s*(class|interface|enum|struct)\s+\w+" |
    ForEach-Object { $_.Matches[0].Value.Trim() } |
    Sort-Object -Unique |
    Out-File "f:\JQKJ\.decomp\raw-evidence\lnkcollector-types.txt"
```

Expected: 输出 LnkCollector.dll 的类型清单（class/interface/enum/struct）。

- [ ] **Step 8.4：抽取 HslCommunication.dll 的命名空间（业务理解入口）**

```powershell
Get-ChildItem "f:\JQKJ\.decomp\ilspy\HslCommunication_DHH02" -Filter "*.cs" -Recurse |
    ForEach-Object {
        $firstMatch = $_ | Select-String -Pattern "^namespace\s+[\w\.]+" | Select-Object -First 1
        if ($firstMatch) { $firstMatch.Matches[0].Value }
    } |
    Sort-Object -Unique |
    Out-File "f:\JQKJ\.decomp\raw-evidence\hslcommunication-namespaces.txt"
```

Expected: 输出 HslCommunication 的顶层命名空间列表（如 `HslCommunication.*`）。

- [ ] **Step 8.5：抽取 Ghidra 反编译的导出函数名（PocoFoundation）**

```powershell
# 从 Ghidra 项目日志或导出文件提取函数名
Get-ChildItem "f:\JQKJ\.decomp\ghidra\PocoFoundation" -Recurse -Filter "*.txt" |
    Get-Content |
    Select-String -Pattern "^\s*(FUN_[0-9a-f]+|public|extern)\s+[\w_]+\s*\(" |
    ForEach-Object { $_.Matches[0].Value.Trim() } |
    Select-Object -First 100 |
    Out-File "f:\JQKJ\.decomp\raw-evidence\poco-functions.txt"
```

Expected: 至少 10 个函数名被提取。

- [ ] **Step 8.6：写入结构化分析报告**

按以下结构写入 `f:\JQKJ\docs\superpowers\reports\2026-09-17-decompile-analysis.md`：

```markdown
# f:\JQKJ 工作区二进制反编译分析报告

**生成日期**：2026-09-17
**工具链**：ILSpy 11 + ILSpyCmd 11 + dnSpyEx 6.6.0 + Ghidra 12.1.3
**分析对象**：7 个代表性二进制样本

## 1. 工具链就绪状态
[粘贴 Task 1-4 的验证输出]

## 2. 样本分类与工具匹配
[复制上面的"工作区二进制档案"表]

## 3. .NET 反编译结果
### 3.1 代码规模统计
[粘贴 ilspy-stats.txt 内容]
### 3.2 LnkCollector.dll 类型清单
[粘贴 lnkcollector-types.txt 头部 20 行]
### 3.3 HslCommunication.dll 命名空间
[粘贴 hslcommunication-namespaces.txt 头部 20 行]
### 3.4 关键发现
[人工总结：业务命名、依赖关系、可疑点]

## 4. 原生二进制 Ghidra 分析
### 4.1 PocoFoundation 函数入口
[粘贴 poco-functions.txt 头部 20 行]
### 4.2 函数数量与导出符号
[从 Ghidra 项目日志摘录]
### 4.3 关键发现
[人工总结：导出 API 命名风格、疑似混淆点]

## 5. 跨样本洞察
- 业务架构推断（每个 exe 大致做什么）
- 通信协议线索（HslCommunication 用法、RemoteComm 接口）
- 安全风险面（如 license.lic 校验位置、加密 dll 调用图）

## 6. 风险与限制
- 反编译 ≠ 源码（变量名/注释丢失）
- Ghidra headless 在 Windows 上需要图形子系统（建议本机 GUI 启动）
- ILSpyCmd 对混淆 .NET（如 ConfuserEx）效果差

## 7. 后续建议
- 进一步分析建议（GUI 启动 Ghidra 看完整反编译）
- 可疑函数深入分析
```

Expected: 报告文件创建成功，包含上述 7 个章节。

---

## Task 9：完成验证 + 工作汇报

- [ ] **Step 9.1：执行 verification-before-completion 检查清单**

```powershell
# 工具链验证
ilspycmd --version
Test-Path "f:\JQKJ\.tools\bin\ilspy.cmd"
Test-Path "f:\JQKJ\.tools\bin\dnspy.cmd"
Test-Path "f:\JQKJ\.tools\bin\ghidra.cmd"
Test-Path "f:\JQKJ\.tools\bin\ghidra-headless.cmd"
# 输出产物验证
Get-ChildItem "f:\JQKJ\.decomp\ilspy" -Recurse -Filter "*.cs" | Measure-Object
Get-ChildItem "f:\JQKJ\.decomp\ghidra" -Recurse | Measure-Object
Test-Path "f:\JQKJ\docs\superpowers\reports\2026-09-17-decompile-analysis.md"
```

Expected: 全部 `True`，`.cs` 文件总数 > 50，Ghidra 项目目录有内容，报告存在。

- [ ] **Step 9.2：输出六要素工作汇报**

按用户偏好的六要素格式汇报：事实 / 洞察 / 判断 / 建议 / 证据 / 风险。

---

## Self-Review Checklist（执行前）

- [x] **Spec coverage**：所有用户需求（A+B+分析报告）有对应 Task
- [x] **Placeholder scan**：所有命令具体可执行，无 TBD/TODO
- [x] **Type consistency**：路径、文件名、命令参数前后一致
- [x] **Bite-sized**：每步 < 5 分钟，单独可执行
- [x] **DRY**：样本映射集中在 `samples.json`，避免重复
- [x] **Verification**：每个 Task 都有验证步骤
