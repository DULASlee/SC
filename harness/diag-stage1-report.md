# 阶段 1 诊断报告 · 项目结构事实采集

> **执行人**：MiniMax-M3 编程代理
> **执行时间**：2026-09-18 06:24 → 06:45（约 21 分钟）
> **架构师指令**：结构诊断（不改代码、不创建文件、不 commit、只采集事实）
> **状态**：✅ 全部 6 项诊断完成；按架构师 §四 要求立即停止

---

## 阶段 1：环境检查原始输出

```
=== 1. Git / bash ===
git version 2.47.1.windows.2
wsl: ...

=== 2. hooks content ===
-rw-r--r-- .githooks/commit-msg
-rw-r--r-- .githooks/lib/common.sh
-rw-r--r-- .githooks/pre-commit
-rw-r--r-- .githooks/pre-push

=== 3. .harness/scripts/ ===
archive-task.py       check-local-scope.py   check-pr-scope.py
check-protected-paths.py   start-task.py    validate-task-card.py
verify-all.py

=== 4. .github/workflows/ ===
ci.yml

=== 5. git remote / branch ===
local-verify  ../JQKJ-verify.git
origin       https://github.com/DULASlee/SC.git
* main
HEAD = e505067
```

---

## 表 A：项目清单（11 个 csproj + 1 个 sln）

| # | 项目名 | 当前路径 | OutputType | TargetFramework |
|---|---|---|---|---|
| 1 | GenCollector | `GenCollector/GenCollector.csproj` | **Exe** | net8.0 |
| 2 | GenDashboard | `GenDashboard/GenDashboard.csproj` | **WinExe** | net8.0-windows |
| 3 | GenCollector.Tests | `GenCollector.Tests/GenCollector.Tests.csproj` | Library | net8.0 |
| 4 | GenDashboard.Tests | `GenDashboard.Tests/GenDashboard.Tests.csproj` | Library | net8.0-windows |
| 5 | LnkCollector_src | `LnkCollector_src/LnkCollector.csproj` | **Exe** | **netcoreapp3.1** |
| 6 | IoTPlatform.Core | `source/IoTPlatform/src/IoTPlatform.Core/IoTPlatform.Core.csproj` | Library | net8.0 |
| 7 | IoTPlatform.Adapters | `source/IoTPlatform/src/IoTPlatform.Adapters/IoTPlatform.Adapters.csproj` | Library | net8.0 |
| 8 | IoTPlatform.Host | `source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj` | **Exe** | net8.0 |
| 9 | IoTPlatform.UI.Wpf | `source/IoTPlatform/samples/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj` | **WinExe** | net8.0-windows |
| 10 | IoTPlatform.Core.Tests | `source/IoTPlatform/tests/IoTPlatform.Core.Tests/IoTPlatform.Core.Tests.csproj` | Library | net8.0 |
| 11 | ReliabilityTests | `tests/ReliabilityTests/ReliabilityTests.csproj` | Library | net8.0 |

**.sln**：`source/IoTPlatform/IoTPlatform.sln`（仅含 IoTPlatform.* 系列，**不含** GenCollector/GenDashboard/LnkCollector_src/ReliabilityTests）

---

## 表 B：项目引用关系

| 项目 | 直接引用的项目 | 关键包 |
|---|---|---|
| GenCollector | （无 ProjectReference） | HslCommunication, Newtonsoft.Json |
| GenDashboard | （无 ProjectReference） | HslCommunication, Newtonsoft.Json |
| **GenCollector.Tests** | → `..\GenCollector\` | xunit, Newtonsoft.Json, CodePages |
| **GenDashboard.Tests** | → `..\GenDashboard\` | xunit, Newtonsoft.Json |
| LnkCollector_src | （无 ProjectReference） | （无） |
| **IoTPlatform.Core** | （无 ProjectReference） | HslCommunication, Config.Json, Hosting, Logging, MQTTnet |
| **IoTPlatform.Adapters** | → `..\IoTPlatform.Core\` | HslCommunication, MQTTnet |
| **IoTPlatform.Host** | → `..\IoTPlatform.Core\`, `..\IoTPlatform.Adapters\` | Config.Json, DI, Logging.Console |
| **IoTPlatform.UI.Wpf** | → `..\..\src\IoTPlatform.Core\`, `..\..\src\IoTPlatform.Adapters\` | Config.Json |
| **IoTPlatform.Core.Tests** | → `..\..\src\IoTPlatform.Core\` | coverlet.collector, xunit |
| **ReliabilityTests** | （无 ProjectReference） | coverlet, FluentAssertions, Testcontainers, Mosquitto, Toxiproxy, xunit |

**图谱**：
```
GenCollector ---test---> GenCollector.Tests
GenDashboard ---test---> GenDashboard.Tests

IoTPlatform.Core <-- Adapters <-- Host
              ^                 ^
              |                 |
              +- UI.Wpf(samples) |
              |                  |
              +- Core.Tests(test)-+

ReliabilityTests (孤立)
LnkCollector_src (孤立)
```

---

## 表 C：Directory.Build 文件清单

| 路径 | 作用范围 | 关键内容 |
|---|---|---|
| `F:\JQKJ\Directory.Build.props` | 整个仓库 | TargetFramework=net8.0, Nullable=disable, TreatWarningsAsErrors=true, x86 条件 `Contains('Collector')`, BannedSymbols 条件 `!Contains('LnkCollector')`, coverlet 条件 `EndsWith('.Tests')` |

**没有 Directory.Build.targets，没有子目录 props/targets。**

---

## 表 D：CI 中引用的路径（`.github/workflows/ci.yml`）

| CI 行 | 引用路径 | 用途 |
|---|---|---|
| 45-52 | `GenCollector/`, `GenDashboard/`, `GenCollector.Tests/`, `GenDashboard.Tests/`, `source/IoTPlatform/src/IoTPlatform.Core/`, `Adapters/`, `Host/`, `samples/IoTPlatform.UI.Wpf/` | restore |
| 57-64 | 同上 8 个 | build |
| 68-69 | `GenCollector.Tests/`, `GenDashboard.Tests/` | test |
| 109-110 | `GenCollector/`, `GenCollector.Tests/` | mutation-test |
| 194-200 | `tests/ReliabilityTests/` | reliability |

**CI 漏掉**：`source/IoTPlatform/tests/IoTPlatform.Core.Tests/`（项目存在但 0 个 .cs 源）

---

## 表 E：迁移风险点（重组后是否失效——仅事实）

| # | 风险点 | 当前实现 | 重组后失效？ |
|---|---|---|---|
| 1 | Directory.Build.props 的 x86 条件 `$(MSBuildProjectName.Contains('Collector'))` | 匹配项目**名字** | **不失效** |
| 2 | BannedSymbols 豁免 `!$(MSBuildProjectName.Contains('LnkCollector'))` | 匹配项目名字 | **不失效** |
| 3 | coverlet 条件 `$(MSBuildProjectName.EndsWith('.Tests'))` | 匹配项目名字 | **不失效** |
| 4 | `BannedSymbols.txt` 引用 `$(MSBuildThisFileDirectory)`（根 Directory.Build.props 同目录） | 依赖 props 所在目录 = 仓库根 | 不失效（props 在根） |
| 5 | `IoTPlatform.UI.Wpf.csproj` ProjectReference `..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj` | 硬编码相对路径 `..\..\src\` | **会失效** |
| 6 | `IoTPlatform.Core.Tests.csproj` ProjectReference `..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj` | 硬编码相对路径 `..\..\src\` | **会失效** |
| 7 | `ci.yml` line 49-52, 61-64 硬编码 `source/IoTPlatform/src/...`, `samples/...` | 硬编码路径 | **会失效** |
| 8 | `ci.yml` line 194-200 硬编码 `tests/ReliabilityTests/` | 硬编码路径 | **会失效** |
| 9 | `BannedSymbols.txt`（仓库根） | 依赖根 Directory.Build.props | 不失效 |
| 10 | `IoTPlatform.sln`（在 `source/IoTPlatform/`）只含 IoTPlatform.* 系列 | 依赖 .sln 路径与项目相对位置 | **会失效**（重组后路径变） |
| 11 | 根目录项目（GenCollector, GenDashboard, GenCollector.Tests, GenDashboard.Tests）**不在任何 .sln 中** | 手动 build | **会失效**（重组后路径变） |
| 12 | `.githooks/pre-commit:31-47` 硬编码 8 个工程路径（PROJECTS 数组） | 硬编码 | **会失效** |
| 13 | `.githooks/pre-push:31-39` 硬编码 3 个测试工程路径 | 硬编码 | **会失效** |
| 14 | `.harness/scripts/verify-all.py:67-79` 硬编码 4 个工程路径 | 硬编码 | **会失效** |
| 15 | `.harness/scripts/check-local-scope.py` 不依赖工程路径 | — | — |
| 16 | `tests/` 不在 `.gitignore` | 不依赖路径 | 不失效 |
| 17 | `tests/ReliabilityTests/ReliabilityTests.csproj` 不含路径依赖 | SDK + 包 | 不失效 |
| 18 | ADR-001~005 引用路径示例 | 文本性文档 | 不失效 |
| 19 | `docs/architecture/` OpenAPI / AsyncAPI 等示例路径 | 示例性 | 不失效 |

---

## 表 F：测试项目详情

| 测试项目 | .cs 数 | 主项目引用 | 备注 |
|---|---|---|---|
| GenCollector.Tests | 5 | GenCollector | BackupManager/ConfigIntegration/ConfigMigrator/JsonConfigLoader/AssemblyInit |
| GenDashboard.Tests | 1 | GenDashboard | DashboardModel |
| **IoTPlatform.Core.Tests** | **0**（仅 obj/ 自动生成） | IoTPlatform.Core | **空项目** |
| ReliabilityTests | 2 | （无） | MqttBrokerFixture + ToolchainSmokeTests |

---

## 诊断 6：git 状态

- HEAD: `e505067`（Round 3 报告）
- Branch: `main`（唯一本地分支）
- Remotes: `origin` (GitHub) + `local-verify` (本地裸仓库)
- Working tree: clean

---

## 等架构师决策（基于上述事实）

1. `src/Backend/` `src/Frontend/` 具体划分？
2. `Directory.Build.props` 条件是否需调？
3. 根目录 vs 移动的项目列表？
4. 测试项目归类？
5. 分阶段 vs 一次性？

按架构师 §四 "输出完整诊断报告后立即停止会话"——**当前会话立即停止**。

---

# 补充原始数据（架构师要求 · 只输出事实，不做分析）

> 补充时间：2026-09-18 06:50
> 边界：未改任何代码、未创建新文件（仅更新本报告）、未 commit、未给建议

---

## 补充 1：项目完整清单（11 个 csproj，含绝对路径）

| # | 项目名 | 完整路径 | OutputType | TargetFramework |
|---|---|---|---|---|
| 1 | GenCollector | `F:\JQKJ\GenCollector\GenCollector.csproj` | Exe | net8.0 |
| 2 | GenDashboard | `F:\JQKJ\GenDashboard\GenDashboard.csproj` | WinExe | net8.0-windows |
| 3 | GenCollector.Tests | `F:\JQKJ\GenCollector.Tests\GenCollector.Tests.csproj` | Library（默认） | net8.0 |
| 4 | GenDashboard.Tests | `F:\JQKJ\GenDashboard.Tests\GenDashboard.Tests.csproj` | Library（默认） | net8.0-windows |
| 5 | LnkCollector_src | `F:\JQKJ\LnkCollector_src\LnkCollector.csproj` | Exe | netcoreapp3.1 |
| 6 | IoTPlatform.Core | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Core\IoTPlatform.Core.csproj` | Library（默认） | net8.0 |
| 7 | IoTPlatform.Adapters | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj` | Library（默认） | net8.0 |
| 8 | IoTPlatform.Host | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Host\IoTPlatform.Host.csproj` | Exe | net8.0 |
| 9 | IoTPlatform.UI.Wpf | `F:\JQKJ\source\IoTPlatform\samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj` | WinExe | net8.0-windows |
| 10 | IoTPlatform.Core.Tests | `F:\JQKJ\source\IoTPlatform\tests\IoTPlatform.Core.Tests\IoTPlatform.Core.Tests.csproj` | Library（默认） | net8.0 |
| 11 | ReliabilityTests | `F:\JQKJ\tests\ReliabilityTests\ReliabilityTests.csproj` | Library（默认） | net8.0 |

---

## 补充 2：每个项目的完整引用（原始 ProjectReference 行）

```
=== GenCollector (F:\JQKJ\GenCollector\GenCollector.csproj) ===
ProjectReferences:
  （无）
PackageReferences:
  - HslCommunication
  - Newtonsoft.Json
Non-package path items:
  L19: <None Include="RemoteComm.dll" CopyToOutputDirectory="PreserveNewest" />
  L20: <None Include="config\**\*" CopyToOutputDirectory="PreserveNewest" />

=== GenDashboard (F:\JQKJ\GenDashboard\GenDashboard.csproj) ===
ProjectReferences:
  （无）
PackageReferences:
  - HslCommunication
  - Newtonsoft.Json
Non-package path items:
  L15: <EmbeddedResource Include="addrMap.csv" />

=== GenCollector.Tests (F:\JQKJ\GenCollector.Tests\GenCollector.Tests.csproj) ===
ProjectReferences:
  L18: <ProjectReference Include="..\GenCollector\GenCollector.csproj" />
PackageReferences:
  - Microsoft.NET.Test.Sdk
  - xunit
  - xunit.runner.visualstudio
  - Newtonsoft.Json
  - System.Text.Encoding.CodePages

=== GenDashboard.Tests (F:\JQKJ\GenDashboard.Tests\GenDashboard.Tests.csproj) ===
ProjectReferences:
  L16: <ProjectReference Include="..\GenDashboard\GenDashboard.csproj" />
PackageReferences:
  - Microsoft.NET.Test.Sdk
  - xunit
  - xunit.runner.visualstudio
  - Newtonsoft.Json
Non-package path items:
  L17: <Content Include="telemetry.jsonl" CopyToOutputDirectory="PreserveNewest" />

=== LnkCollector_src (F:\JQKJ\LnkCollector_src\LnkCollector.csproj) ===
ProjectReferences:
  （无）
PackageReferences:
  （无）
Non-package path items（HintPath）:
  L18: <HintPath>..\CNC04\HslCommunication.dll</HintPath>
  L21: <HintPath>..\CNC04\Newtonsoft.Json.dll</HintPath>

=== IoTPlatform.Core (F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Core\IoTPlatform.Core.csproj) ===
ProjectReferences:
  （无）
PackageReferences:
  - HslCommunication
  - Microsoft.Extensions.Configuration.Json
  - Microsoft.Extensions.Hosting
  - Microsoft.Extensions.Logging
  - MQTTnet

=== IoTPlatform.Adapters (F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj) ===
ProjectReferences:
  L4: <ProjectReference Include="..\IoTPlatform.Core\IoTPlatform.Core.csproj" />
PackageReferences:
  - HslCommunication
  - MQTTnet

=== IoTPlatform.Host (F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Host\IoTPlatform.Host.csproj) ===
ProjectReferences:
  L11: <ProjectReference Include="..\IoTPlatform.Core\IoTPlatform.Core.csproj" />
  L12: <ProjectReference Include="..\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj" />
PackageReferences:
  - Microsoft.Extensions.Configuration.Json
  - Microsoft.Extensions.DependencyInjection
  - Microsoft.Extensions.Logging.Console

=== IoTPlatform.UI.Wpf (F:\JQKJ\source\IoTPlatform\samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj) ===
ProjectReferences:
  L4: <ProjectReference Include="..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj" />
  L5: <ProjectReference Include="..\..\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj" />
PackageReferences:
  - Microsoft.Extensions.Configuration.Json

=== IoTPlatform.Core.Tests (F:\JQKJ\source\IoTPlatform\tests\IoTPlatform.Core.Tests\IoTPlatform.Core.Tests.csproj) ===
ProjectReferences:
  L24: <ProjectReference Include="..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj" />
PackageReferences:
  - coverlet.collector
  - Microsoft.NET.Test.Sdk
  - xunit
  - xunit.runner.visualstudio

=== ReliabilityTests (F:\JQKJ\tests\ReliabilityTests\ReliabilityTests.csproj) ===
ProjectReferences:
  （无）
PackageReferences:
  - coverlet.collector
  - FluentAssertions
  - Testcontainers
  - Testcontainers.Mosquitto
  - Testcontainers.Toxiproxy
  - xunit
  - xunit.runner.visualstudio
```

---

## 补充 3：硬编码路径的完整清单（文件 + 行号 + 原始内容）

### 3.1 csproj 内部 ProjectReference（相对路径）

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 1 | `GenCollector.Tests\GenCollector.Tests.csproj` | L18 | `<ProjectReference Include="..\GenCollector\GenCollector.csproj" />` |
| 2 | `GenDashboard.Tests\GenDashboard.Tests.csproj` | L16 | `<ProjectReference Include="..\GenDashboard\GenDashboard.csproj" />` |
| 3 | `LnkCollector_src\LnkCollector.csproj` | L18 | `<HintPath>..\CNC04\HslCommunication.dll</HintPath>` |
| 4 | `LnkCollector_src\LnkCollector.csproj` | L21 | `<HintPath>..\CNC04\Newtonsoft.Json.dll</HintPath>` |
| 5 | `source\IoTPlatform\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj` | L4 | `<ProjectReference Include="..\IoTPlatform.Core\IoTPlatform.Core.csproj" />` |
| 6 | `source\IoTPlatform\src\IoTPlatform.Host\IoTPlatform.Host.csproj` | L11 | `<ProjectReference Include="..\IoTPlatform.Core\IoTPlatform.Core.csproj" />` |
| 7 | `source\IoTPlatform\src\IoTPlatform.Host\IoTPlatform.Host.csproj` | L12 | `<ProjectReference Include="..\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj" />` |
| 8 | `source\IoTPlatform\samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj` | L4 | `<ProjectReference Include="..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj" />` |
| 9 | `source\IoTPlatform\samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj` | L5 | `<ProjectReference Include="..\..\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj" />` |
| 10 | `source\IoTPlatform\tests\IoTPlatform.Core.Tests\IoTPlatform.Core.Tests.csproj` | L24 | `<ProjectReference Include="..\..\src\IoTPlatform.Core\IoTPlatform.Core.csproj" />` |

### 3.2 csproj 内部非 ProjectReference 路径项

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 11 | `GenCollector\GenCollector.csproj` | L19 | `<None Include="RemoteComm.dll" CopyToOutputDirectory="PreserveNewest" />` |
| 12 | `GenCollector\GenCollector.csproj` | L20 | `<None Include="config\**\*" CopyToOutputDirectory="PreserveNewest" />` |
| 13 | `GenDashboard\GenDashboard.csproj` | L15 | `<EmbeddedResource Include="addrMap.csv" />` |
| 14 | `GenDashboard.Tests\GenDashboard.Tests.csproj` | L17 | `<Content Include="telemetry.jsonl" CopyToOutputDirectory="PreserveNewest" />` |

### 3.3 `.githooks/pre-commit`（PROJECTS 数组 + 架构测试路径）

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 15 | `.githooks/pre-commit` | L30 | `"GenCollector/GenCollector.csproj"` |
| 16 | `.githooks/pre-commit` | L31 | `"GenDashboard/GenDashboard.csproj"` |
| 17 | `.githooks/pre-commit` | L32 | `"GenCollector.Tests/GenCollector.Tests.csproj"` |
| 18 | `.githooks/pre-commit` | L33 | `"GenDashboard.Tests/GenDashboard.Tests.csproj"` |
| 19 | `.githooks/pre-commit` | L34 | `"source/IoTPlatform/src/IoTPlatform.Core/IoTPlatform.Core.csproj"` |
| 20 | `.githooks/pre-commit` | L35 | `"source/IoTPlatform/src/IoTPlatform.Adapters/IoTPlatform.Adapters.csproj"` |
| 21 | `.githooks/pre-commit` | L36 | `"source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj"` |
| 22 | `.githooks/pre-commit` | L37 | `"source/IoTPlatform/samples/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj"` |
| 23 | `.githooks/pre-commit` | L50 | `if [ -f "tests/ArchitectureTests/ArchitectureTests.csproj" ]; then` |
| 24 | `.githooks/pre-commit` | L51 | `dotnet test tests/ArchitectureTests/ArchitectureTests.csproj -c Release --no-build --nologo -v quiet \|\| fail "架构测试失败"` |

### 3.4 `.githooks/pre-push`

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 25 | `.githooks/pre-push` | L38 | `for proj in GenCollector.Tests/GenCollector.Tests.csproj GenDashboard.Tests/GenDashboard.Tests.csproj tests/ReliabilityTests/ReliabilityTests.csproj; do` |
| 26 | `.githooks/pre-push` | L65 | `dotnet test tests/ReliabilityTests/ReliabilityTests.csproj -c Release --no-build --nologo -v quiet \` |

### 3.5 `.harness/scripts/verify-all.py`

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 27 | `.harness/scripts/verify-all.py` | L75 | `proj_main="GenCollector/GenCollector.csproj"` |
| 28 | `.harness/scripts/verify-all.py` | L78 | `proj_tests="GenCollector.Tests/GenCollector.Tests.csproj"` |
| 29 | `.harness/scripts/verify-all.py` | L79 | `proj_other_tests="GenDashboard.Tests/GenDashboard.Tests.csproj"` |
| 30 | `.harness/scripts/verify-all.py` | L80 | `proj_reliability="tests/ReliabilityTests/ReliabilityTests.csproj"` |
| 31 | `.harness/scripts/verify-all.py` | L81 | `proj_iot="source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj"` |
| 32 | `.harness/scripts/verify-all.py` | L90 | `"[ -f tests/ArchitectureTests/ArchitectureTests.csproj ] && "` |
| 33 | `.harness/scripts/verify-all.py` | L91 | `"dotnet test tests/ArchitectureTests/ArchitectureTests.csproj -c Release --no-build --nologo -v quiet "` |

### 3.6 `.github/workflows/ci.yml`

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 34 | `.github/workflows/ci.yml` | L45 | `dotnet restore GenCollector/GenCollector.csproj -r win-x86` |
| 35 | `.github/workflows/ci.yml` | L46 | `dotnet restore GenDashboard/GenDashboard.csproj` |
| 36 | `.github/workflows/ci.yml` | L47 | `dotnet restore GenCollector.Tests/GenCollector.Tests.csproj` |
| 37 | `.github/workflows/ci.yml` | L48 | `dotnet restore GenDashboard.Tests/GenDashboard.Tests.csproj` |
| 38 | `.github/workflows/ci.yml` | L49 | `dotnet restore source/IoTPlatform/src/IoTPlatform.Core/IoTPlatform.Core.csproj` |
| 39 | `.github/workflows/ci.yml` | L50 | `dotnet restore source/IoTPlatform/src/IoTPlatform.Adapters/IoTPlatform.Adapters.csproj` |
| 40 | `.github/workflows/ci.yml` | L51 | `dotnet restore source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj` |
| 41 | `.github/workflows/ci.yml` | L52 | `dotnet restore source/IoTPlatform/samples/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj` |
| 42 | `.github/workflows/ci.yml` | L57 | `dotnet build GenCollector/GenCollector.csproj -c Release -r win-x86 --self-contained true -p:PlatformTarget=x86 --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 43 | `.github/workflows/ci.yml` | L58 | `dotnet build GenDashboard/GenDashboard.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 44 | `.github/workflows/ci.yml` | L59 | `dotnet build GenCollector.Tests/GenCollector.Tests.csproj -c Release -p:PlatformTarget=x86 --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 45 | `.github/workflows/ci.yml` | L60 | `dotnet build GenDashboard.Tests/GenDashboard.Tests.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 46 | `.github/workflows/ci.yml` | L61 | `dotnet build source/IoTPlatform/src/IoTPlatform.Core/IoTPlatform.Core.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 47 | `.github/workflows/ci.yml` | L62 | `dotnet build source/IoTPlatform/src/IoTPlatform.Adapters/IoTPlatform.Adapters.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 48 | `.github/workflows/ci.yml` | L63 | `dotnet build source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 49 | `.github/workflows/ci.yml` | L64 | `dotnet build source/IoTPlatform/samples/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 50 | `.github/workflows/ci.yml` | L68 | `dotnet test GenCollector.Tests/GenCollector.Tests.csproj -c Release --no-build -p:PlatformTarget=x86` |
| 51 | `.github/workflows/ci.yml` | L69 | `dotnet test GenDashboard.Tests/GenDashboard.Tests.csproj -c Release --no-build` |
| 52 | `.github/workflows/ci.yml` | L109 | `dotnet restore GenCollector/GenCollector.csproj` |
| 53 | `.github/workflows/ci.yml` | L110 | `dotnet restore GenCollector.Tests/GenCollector.Tests.csproj` |
| 54 | `.github/workflows/ci.yml` | L194 | `run: dotnet restore tests/ReliabilityTests/ReliabilityTests.csproj` |
| 55 | `.github/workflows/ci.yml` | L197 | `run: dotnet build tests/ReliabilityTests/ReliabilityTests.csproj -c Release --no-restore /p:TreatWarningsAsErrors=true /p:EnforceCodeStyleInBuild=true` |
| 56 | `.github/workflows/ci.yml` | L200 | `run: dotnet test tests/ReliabilityTests/ReliabilityTests.csproj -c Release --no-build --logger "trx;LogFileName=reliability-toolchain.trx"` |

### 3.7 `source/IoTPlatform/IoTPlatform.sln`

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 57 | `source/IoTPlatform/IoTPlatform.sln` | L8 | `Project("{FAE04EC0-...}") = "IoTPlatform.Core", "src\IoTPlatform.Core\IoTPlatform.Core.csproj", "{E18AD65A-...}"` |
| 58 | `source/IoTPlatform/IoTPlatform.sln` | L10 | `Project("{FAE04EC0-...}") = "IoTPlatform.Adapters", "src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj", "{B1637938-...}"` |
| 59 | `source/IoTPlatform/IoTPlatform.sln` | L12 | `Project("{FAE04EC0-...}") = "IoTPlatform.Host", "src\IoTPlatform.Host\IoTPlatform.Host.csproj", "{0FDEECA0-...}"` |
| 60 | `source/IoTPlatform/IoTPlatform.sln` | L16 | `Project("{FAE04EC0-...}") = "IoTPlatform.UI.Wpf", "samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj", "{958BBC22-...}"` |
| 61 | `source/IoTPlatform/IoTPlatform.sln` | L20 | `Project("{FAE04EC0-...}") = "IoTPlatform.Core.Tests", "tests\IoTPlatform.Core.Tests\IoTPlatform.Core.Tests.csproj", "{26D7CBAB-...}"` |

### 3.8 Directory.Build.props（路径依赖）

| # | 文件 | 行号 | 原始内容 |
|---|---|---|---|
| 62 | `Directory.Build.props` | L51 | `<AdditionalFiles Include="$(MSBuildThisFileDirectory)BannedSymbols.txt" />` |

---

## 补充 4：`IoTPlatform.sln` 项目列表（原始内容）

```
L6  Project("{2150E333-8FDC-42A3-9474-1A3956D46DE8}") = "src", "src", "{827E0CD3-B72D-47B6-A68D-7590B98EB39B}"
L8  Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "IoTPlatform.Core", "src\IoTPlatform.Core\IoTPlatform.Core.csproj", "{E18AD65A-54BA-4BA3-95F8-403E52BEA655}"
L10 Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "IoTPlatform.Adapters", "src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj", "{B1637938-D8EE-47B7-9DBF-DC0D54A2B521}"
L12 Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "IoTPlatform.Host", "src\IoTPlatform.Host\IoTPlatform.Host.csproj", "{0FDEECA0-204C-45DB-8EA4-58EAE7666381}"
L14 Project("{2150E333-8FDC-42A3-9474-1A3956D46DE8}") = "samples", "samples", "{5D20AA90-6969-D8BD-9DCD-8634F4692FDA}"
L16 Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "IoTPlatform.UI.Wpf", "samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj", "{958BBC22-D3F3-46B6-950A-56BDDE60B27F}"
L18 Project("{2150E333-8FDC-42A3-9474-1A3956D46DE8}") = "tests", "tests", "{0AB3BF05-4346-4AA6-1389-037BE0695223}"
L20 Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "IoTPlatform.Core.Tests", "tests\IoTPlatform.Core.Tests\IoTPlatform.Core.Tests.csproj", "{26D7CBAB-2014-4C82-9B68-EC7742319D2F}"
```

**含 5 个真实项目**（3 个 solution folder "src"/"samples"/"tests" 是虚拟节点）：
- IoTPlatform.Core
- IoTPlatform.Adapters
- IoTPlatform.Host
- IoTPlatform.UI.Wpf
- IoTPlatform.Core.Tests

**构建配置**（`GlobalSection` 内的 `Build.0` 条目）未列出——若需可补。

---

## 补充 5：不在任何 `.sln` 中的 csproj

全仓库**只有 1 个 .sln**：`F:\JQKJ\source\IoTPlatform\IoTPlatform.sln`（不含 `.tools/ghidra` 下的第三方示例）。

**不在该 .sln 中的 csproj（位于仓库 depth-1，共 5 个）**：

| # | 项目名 | 完整路径 |
|---|---|---|
| 1 | GenCollector | `F:\JQKJ\GenCollector\GenCollector.csproj` |
| 2 | GenCollector.Tests | `F:\JQKJ\GenCollector.Tests\GenCollector.Tests.csproj` |
| 3 | GenDashboard | `F:\JQKJ\GenDashboard\GenDashboard.csproj` |
| 4 | GenDashboard.Tests | `F:\JQKJ\GenDashboard.Tests\GenDashboard.Tests.csproj` |
| 5 | LnkCollector_src | `F:\JQKJ\LnkCollector_src\LnkCollector.csproj` |

**另 2 个不在 sln 中的**（位于 `tests/`）：
| 6 | ReliabilityTests | `F:\JQKJ\tests\ReliabilityTests\ReliabilityTests.csproj` |

**汇总**：11 个 csproj 中，**5 个在 `IoTPlatform.sln` 中**（IoTPlatform.* 系列），**6 个不在任何 .sln 中**（GenCollector / GenDashboard / GenCollector.Tests / GenDashboard.Tests / LnkCollector_src / ReliabilityTests）。

---

## 补充 6：hooks 中的 PROJECTS 数组（原始内容）

### 6.1 `.githooks/pre-commit` L27-L47

```bash
# 注：本仓库无 .sln 文件，逐个工程 build。
#     用 bash 数组传参（避免行末 \ 续行吞参数）。
PROJECTS=(
    "GenCollector/GenCollector.csproj"
    "GenDashboard/GenDashboard.csproj"
    "GenCollector.Tests/GenCollector.Tests.csproj"
    "GenDashboard.Tests/GenDashboard.Tests.csproj"
    "source/IoTPlatform/src/IoTPlatform.Core/IoTPlatform.Core.csproj"
    "source/IoTPlatform/src/IoTPlatform.Adapters/IoTPlatform.Adapters.csproj"
    "source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj"
    "source/IoTPlatform/samples/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj"
)
for proj in "${PROJECTS[@]}"; do
    [ -f "$proj" ] || continue
    if [[ "$proj" == GenCollector* ]]; then
        args=( "$proj" -c Release -r win-x86 --self-contained true "-p:PlatformTarget=x86" "-p:TreatWarningsAsErrors=true" --nologo -v quiet )
    else
        args=( "$proj" -c Release "-p:TreatWarningsAsErrors=true" --nologo -v quiet )
    fi
    dotnet build "${args[@]}" || fail "编译失败：$proj"
done
```

### 6.2 `.githooks/pre-push` L37-L46

```bash
# 1. 全测试（仓库无 .sln，逐个工程）
for proj in GenCollector.Tests/GenCollector.Tests.csproj GenDashboard.Tests/GenDashboard.Tests.csproj tests/ReliabilityTests/ReliabilityTests.csproj; do
    [ -f "$proj" ] || continue
    if [[ "$proj" == GenCollector* ]]; then
        args=( "$proj" -c Release "-p:PlatformTarget=x86" --no-build --nologo -v quiet )
    else
        args=( "$proj" -c Release --no-build --nologo -v quiet )
    fi
    dotnet test "${args[@]}" || fail "全测试失败：$proj"
done
```

### 6.3 `.githooks/pre-push` L63-L67

```bash
    dotnet test tests/ReliabilityTests/ReliabilityTests.csproj -c Release --no-build --nologo -v quiet \
        || warn "可靠性工具链未通过（观察期）"
```

---

## 补充 7：`verify-all.py` 中的所有路径引用（原始内容）

```python
L73:    # 注：本仓库无 .sln 文件，逐个工程 build/test。
L74:    # GenCollector 必须 x86（ADR-0003）；其它工程直接 default platform。
L75:    proj_main="GenCollector/GenCollector.csproj"
L76:    proj_main_args="-c Release -r win-x86 --self-contained true -p:PlatformTarget=x86"
L77:    test_main_args="-c Release -p:PlatformTarget=x86"
L78:    proj_tests="GenCollector.Tests/GenCollector.Tests.csproj"
L79:    proj_other_tests="GenDashboard.Tests/GenDashboard.Tests.csproj"
L80:    proj_reliability="tests/ReliabilityTests/ReliabilityTests.csproj"
L81:    proj_iot="source/IoTPlatform/src/IoTPlatform.Host/IoTPlatform.Host.csproj"
L82:    proj_iot_args="-c Release"
...
L90:            "[ -f tests/ArchitectureTests/ArchitectureTests.csproj ] && "
L91:            "dotnet test tests/ArchitectureTests/ArchitectureTests.csproj -c Release --no-build --nologo -v quiet "
```

---

## 补充说明（事实，非建议）

1. **`tests/ArchitectureTests/` 目录当前不存在**（`pre-commit` L50、`verify-all.py` L90 引用它，但以 `[ -f ... ]` 条件保护）。
2. **`F:\JQKJ\CNC04\` 目录存在**（`LnkCollector_src.csproj` 的 `HintPath ..\CNC04\` 是有效路径）。
3. **`.editorconfig` 无显式路径依赖**（只用 `[*]`、`[*.{cs,...}]`、`[*.sh]`、`[*.ini]` 模式）。
4. **`IoTPlatform.sln` 未包含 `DotNetSolutionItems` 或 `Build.0` 之外的项目**——上述 5 个项目是完整列表。

按架构师 §三 边界：**未改任何代码、未创建新文件（除更新本报告）、未 commit、未给建议**。

补充完成，停止会话。
