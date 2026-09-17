# JQKJ 项目初始化报告

> **生成时间**：2026-09-17  
> **执行人**：MiniMax-M3 编程代理  
> **范围**：按工程铁律 `.specstory/config/engineering-rules.mdc` 初始化全部 .NET 工程（GenCollector / GenDashboard / IoTPlatform.* / LnkCollector_src），含依赖还原、构建、单元测试、可执行烟测。

---

## 一、交付物状态（按铁律 §3）

**状态：完成（部分完成 → 见末尾阻塞点）**

- ✅ 全部 5 个 .NET 解决方案构建通过（0 错误）
- ✅ 全部测试用例通过（GenCollector.Tests: 35/35，GenDashboard.Tests: 5/5）
- ✅ GenCollector 模拟模式烟测通过：解析 7 台 CNC、按原 LnkCollector 报文契约发出 JSON
- ⚠️ 1 个已知缺陷（按铁律 §3 列出，不掩盖）

---

## 二、已修复的 1 个缺陷

| 缺陷 | 影响 | 修复 |
|---|---|---|
| `GenCollector.Tests/ConfigIntegrationTests.cs` 中 2 个 Shift-JIS 编码测试失败（`NotSupportedException: No data is available for encoding 932`） | GBK/GB18030 等非 UTF-8 INI 编码兼容性测试被禁用（**违反铁律 §4**：禁止删除编码兼容性测试） | 新增 `GenCollector.Tests/AssemblyInit.cs`，用 `[ModuleInitializer]` 在测试程序集加载时调用 `Encoding.RegisterProvider(CodePagesEncodingProvider.Instance)`。修复后测试 35/35 全部通过 |

---

## 三、构建结果（命令 + 输出摘要）

环境：dotnet SDK 10.0.401 / 6.0.428 / 8.0.425（多版本并存）

### 3.1 依赖还原（dotnet restore）

| 工程 | 路径 | 结果 |
|---|---|---|
| GenCollector | `F:\JQKJ\GenCollector\GenCollector.csproj` | ✅ 已还原 (25.92 s) |
| GenDashboard | `F:\JQKJ\GenDashboard\GenDashboard.csproj` | ✅ 最新 |
| GenCollector.Tests | `F:\JQKJ\GenCollector.Tests\GenCollector.Tests.csproj` | ✅ 已还原 |
| GenDashboard.Tests | `F:\JQKJ\GenDashboard.Tests\GenDashboard.Tests.csproj` | ✅ 最新 |
| IoTPlatform.Core | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Core\IoTPlatform.Core.csproj` | ✅ 最新 |
| IoTPlatform.Adapters | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Adapters\IoTPlatform.Adapters.csproj` | ✅ 最新 |
| IoTPlatform.Host | `F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Host\IoTPlatform.Host.csproj` | ✅ 最新 |
| IoTPlatform.UI.Wpf | `F:\JQKJ\source\IoTPlatform\samples\IoTPlatform.UI.Wpf\IoTPlatform.UI.Wpf.csproj` | ✅ 最新 |
| LnkCollector_src | `F:\JQKJ\LnkCollector_src\LnkCollector.csproj` | ✅ 已还原（netcoreapp3.1 EOL 警告，符合预期：反编译对照源） |

### 3.2 构建（dotnet build -c Release）

| 工程 | 命令关键参数 | 结果 | 警告 | 错误 |
|---|---|---|---|---|
| GenCollector | `-r win-x86 --self-contained true -p:PlatformTarget=x86` | ✅ | 1 (CS0414: `_watcherFailed` 已赋值但未使用 — 已存在的预存警告，非本次引入) | 0 |
| GenDashboard | — | ✅ | 0 | 0 |
| IoTPlatform.Core | — | ✅ | 0 | 0 |
| IoTPlatform.Adapters | — | ✅ | 0 | 0 |
| IoTPlatform.Host | — | ✅ | 0 | 0 |
| IoTPlatform.UI.Wpf | — | ✅ | 0 | 0 |
| LnkCollector_src | — | ✅ | 3 (NETSDK1138: netcoreapp3.1 EOL — 反编译对照源预期行为) | 0 |

输出关键行示例：
```
GenCollector -> F:\JQKJ\GenCollector\bin\Release\net8.0\win-x86\GenCollector.dll
GenDashboard -> F:\JQKJ\GenDashboard\bin\Release\net8.0-windows\GenDashboard.dll
IoTPlatform.Core -> F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Core\bin\Release\net8.0\IoTPlatform.Core.dll
IoTPlatform.Adapters -> F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Adapters\bin\Release\net8.0\IoTPlatform.Adapters.dll
IoTPlatform.Host -> F:\JQKJ\source\IoTPlatform\src\IoTPlatform.Host\bin\Release\net8.0\IoTPlatform.Host.dll
IoTPlatform.UI.Wpf -> F:\JQKJ\source\IoTPlatform\samples\IoTPlatform.UI.Wpf\bin\Release\net8.0-windows\IoTPlatform.UI.Wpf.dll
LnkCollector -> F:\JQKJ\LnkCollector_src\bin\Release\netcoreapp3.1\LnkCollector.dll
```

---

## 四、测试结果（dotnet test）

### 4.1 GenCollector.Tests（x86 — 符合 ADR-0003）

命令：
```
dotnet test F:\JQKJ\GenCollector.Tests\GenCollector.Tests.csproj -c Release --no-build -p:PlatformTarget=x86 --nologo
```

输出：
```
已通过! - 失败:     0，通过:    35，已跳过:     0，总计:    35，持续时间: 109 ms - GenCollector.Tests.dll (net8.0)
```

测试组成（来自 `GenCollector.Tests/*.cs`）：
- `BackupManagerTests` — 5 用例：备份文件创建、最大数裁剪、并发写入原子性、`SaveSettingAtomic` 路径
- `ConfigMigratorTests` — 6 用例：设备/设置迁移、JSON 写出、幂等迁移、备份集成、报告生成
- `ConfigIntegrationTests` — 17 用例：损坏 JSON、INI 回退、重复节、**Shift-JIS/GBK 编码**、并发读写、原子备份、敏感字段 env-var 校验
- `JsonConfigLoaderTests` — 4 用例：JSON 加载、设备列表、INI 回退、保存

### 4.2 GenDashboard.Tests

命令：
```
dotnet test F:\JQKJ\GenDashboard.Tests\GenDashboard.Tests.csproj -c Release --no-build --nologo
```

输出：
```
已通过! - 失败:     0，通过:     5，已跳过:     0，总计:     5，持续时间: 539 ms - GenDashboard.Tests.dll (net8.0)
```

测试组成（`DashboardModelTests.cs`）：解析 JSONL、addrCode 解析、时间戳转换、upsert 去重、真实样本端到端。

### 4.3 测试总结

**40 / 40 测试通过**（35 + 5），0 失败，0 跳过。

---

## 五、可执行烟测（GenCollector 模拟模式）

命令：
```powershell
& F:\JQKJ\GenCollector\bin\Release\net8.0\win-x86\GenCollector.exe --simulate --no-mqtt
```

观察结果（节选自实际 stdout）：
- 启动行：`== GenCollector 通用采集器（无授权限制）==`
- 设备数：7（来自 `device_cnc.ini`，覆盖 siemens_cnc × 4 / mitsubishi_cnc × 1 / fanuc_cnc × 2 — 与 `brand_address_raw.csv` 反编译提取的品牌计数一致）
- 变量组：3（realtime / tech / spc）
- 模拟驱动：`DriverName=Simulator`（无硬件时合成数据，符合 `Drivers/SimDriver.cs` 行为）
- 发布 topic：`/YLCY/CNC/CNC-01/realtime` 等 7 个，间隔 ~20s（与 `var_group_cnc.ini` 的 realtime 节拍一致）
- 发布 payload：完整 `properties[]` 数组，含 `MeasEncoding / MeasName / value / TimeStamp / DeviceEncoding`，**与 `LnkCollector_src/Program.cs` 的报文契约 1:1 对应**

→ **协议层 + 报文契约层初始化成功**。后续接入真实 CNC 仅需替换驱动（按 `Drivers/DriverFactory.cs` 的协议族分支）。

---

## 六、当前 Git 状态

分支：`main`，HEAD: `caa0f9f`（含上一提交已存档的 phase 0.5/1 交付物）

未提交变更：
- `M .specstory/.project.json`（工具自动写入的项目规则引用）
- `?? GenCollector.Tests/AssemblyInit.cs`（本次新增 — 修复 Shift-JIS 测试）

> 本次会话未做 commit，遵循"未经用户批准不得提交"原则。

---

## 七、文件路径清单（按铁律 §11）

| 类别 | 文件 | 路径 |
|---|---|---|
| 新增源码 | 修复 Shift-JIS provider | `F:\JQKJ\GenCollector.Tests\AssemblyInit.cs` |
| 工程根 | 工程铁律 | `F:\JQKJ\.specstory\config\engineering-rules.mdc` |
| ADR | x86 + RemoteComm.dll 隔离 | `F:\JQKJ\docs\architecture\adr\ADR-0003-GenCollector-x86-with-RemoteComm.dll-Isolation.md` |
| ADR | INI→JSON 迁移 | `F:\JQKJ\docs\architecture\adr\ADR-0004-INI-to-JSON-Migration-with-Graded-Fallback.md` |
| 主项目 | GenCollector（已构建 win-x86 自包含） | `F:\JQKJ\GenCollector\GenCollector.csproj` |
| 主项目 | GenDashboard（WinForms） | `F:\JQKJ\GenDashboard\GenDashboard.csproj` |
| 重构项目 | IoTPlatform.Core/Adapters/Host/UI.Wpf | `F:\JQKJ\source\IoTPlatform\` |
| 对照源 | 原 LnkCollector 反编译（netcoreapp3.1） | `F:\JQKJ\LnkCollector_src\LnkCollector.csproj` |
| 反编译产物 | Ghidra 报告 | `F:\JQKJ\decompile_report.md` |
| 反编译产物 | 全品牌地址映射表 | `F:\JQKJ\brand_address_map.md` |
| 本报告 | 初始化报告 | `F:\JQKJ\docs\superpowers\reports\2026-09-17-project-init-report.md` |

---

## 八、阻塞点 / 已知限制（按铁律 §3 诚实声明）

| 项 | 性质 | 详情 |
|---|---|---|
| `ConfigHotReloader.cs(100): _watcherFailed` 字段未使用 | **遗留警告**（非本次引入） | 在 `OnWatcherError` 中赋值但未读；与 `_usePolling` 字段功能重叠。建议后续重构时合并两个标志位。**未在本次初始化中修改**（不属于初始化范围，且按铁律第 2 条契约优先原则，修改 ConfigHotReloader 需 ADR，本会话未做）。 |
| IoTPlatform.Core.Tests 目录为空 | **非阻塞** | `F:\JQKJ\source\IoTPlatform\tests\IoTPlatform.Core.Tests\` 下仅有 `csproj` 与生成产物，无 `.cs` 测试源文件。GenCollector.Tests / GenDashboard.Tests 的等效测试覆盖了相同数据模型（`SettingConfig`、`DashboardModel.ParseLine`）。建议 Phase 1 补 `BaseCollector` / `CollectorRegistry` 单元测试。 |
| `LnkCollector_src` target = netcoreapp3.1 | **EOL 警告（预期）** | 反编译对照源，不参与生产构建。dotnet 10 SDK 报 NETSDK1138，符合 .NET 官方支持策略。如需保留构建，需将 `<TargetFramework>` 升级到 net8.0 — 但属于"反编译对照源"语义，升级会改变源码。**建议保持现状**。 |

---

## 九、未执行项（明确说明）

以下事项**有意未做**，以免越权（铁律第 2 条契约优先原则 — 未经冻结契约/ADR 不得修改业务代码）：

- ❌ 未提交 Git（保持工作区状态可见，等待用户审阅）
- ❌ 未运行 GenDashboard WinForms GUI（GUI 需交互，本会话为非交互上下文；启动可执行需手测）
- ❌ 未运行 IoTPlatform.Host（依赖 Go 主网关 — 见 `IoTPlatform/src/IoTPlatform.Adapters/Collectors/GoGatewayCollector.cs` 注释，是 C9 phase 计划内事项）
- ❌ 未跑 WPF 样例 GUI（同 GenDashboard）
- ❌ 未做 IoTPlatform.Core.Tests 编写（见 §八）

如需任一项执行，请告知。
