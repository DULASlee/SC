# f:\JQKJ 工作区二进制反编译分析报告

**生成日期**：2026-09-17
**生成工具**：Qoder IDE / Claude（MiniMax-M3）
**运行环境**：Windows 25H2 + .NET SDK 10.0.401 + JDK 24.0.1 + PowerShell 7
**反编译工具链**：ILSpyCmd 11.0.0.9375（.NET CLI）+ ILSpy 11.0（GUI）+ dnSpyEx 6.6.0（GUI+调试）+ Ghidra 12.1.3（原生二进制 SRE）
**已用 skills**：`binary-analysis-patterns` / `ctf-reverse` / `ctf-malware`（均通过 symlink 挂载到 `~/.codebuddy/skills/`）

---

## 1. 工具链就绪状态

| 工具 | 版本 | 安装位置 | 状态 |
|---|---|---|---|
| ILSpyCmd | 11.0.0.9375 | `C:\Users\admin\.dotnet\tools\ilspycmd.cmd` | ✅ 已验证 `--version` / `--help` |
| ILSpy GUI | 11.0.0.9375 | `F:\JQKJ\.tools\ilspy\ILSpy.exe` | ✅ 已下载 19.2 MB / 解压 / shim |
| dnSpyEx | 6.6.0 | `F:\JQKJ\.tools\dnspyex\dnSpy.exe` | ✅ 已下载 94.3 MB / 解压 / shim |
| Ghidra | 12.1.3 | `F:\JQKJ\.tools\ghidra\ghidra_12.1.3_PUBLIC\ghidraRun.bat` | ✅ 已下载 569 MB / 解压 / shim + analyzeHeadless shim |

PATH shim（统一入口）位于 `F:\JQKJ\.tools\bin\`：

```
ilspy.cmd          → ILSpy GUI
dnspy.cmd          → dnSpyEx GUI
ghidra.cmd         → Ghidra GUI
ghidra-headless.cmd → Ghidra headless analyzer
```

> 注：要在 PATH 中调用这些 shim，需将 `F:\JQKJ\.tools\bin` 加入 PATH；当前为绝对路径调用。

---

## 2. 工作区二进制档案 + 语言识别修正

**关键修正**：原假设"DHH02 目录下是 Poco C++ 库、MknEdmRm1201.dll 是 C++"经 ILSpyCmd / Ghidra 验证基本正确，但 **CNC/iot_CNC_PLC_IMM.exe 被 Ghidra 12.1.3 自动识别为 Go 1.24.5 编译的 15.7 MB 大型网关二进制**（原以为是 C++ 自宿主）。

| # | 路径 | 大小 | 类型（修正后） | 反编译工具 |
|---|---|---|---|---|
| 1 | `CNC04\LnkCollector.dll` | 12 KB | **.NET Core 3.1**（自宿主 MQTT 客户端） | ILSpyCmd ✅ |
| 2 | `DHH02\HanBaCollector.exe` | 10 KB | **.NET Framework 4.7.2**（HTTP/MQTT 采集器） | ILSpyCmd ✅ |
| 3 | `DHH02\HslCommunication.dll` | 4.4 MB | **.NET 第三方工业通信库**（89 个命名空间） | ILSpyCmd ✅ |
| 4 | `DHH04\MelCollector.exe` | 234 KB | **C++ MSVC native**（MQTT client + STL） | Ghidra ✅ |
| 5 | `DHH04\MknEdmRm1201.dll` | 135 KB | **C++ MSVC native**（三菱 CNC EDM 加工 SDK） | Ghidra ✅ |
| 6 | `CNC04\RemoteComm.dll` | 75 KB | **C++ MSVC native**（CNC/PLC 通信 SDK，Winsock） | Ghidra ✅ |
| 7 | `DHH02\PocoFoundation.dll` | 1.6 MB | **C++ MSVC native**（Poco Foundation 库） | Ghidra ✅ |
| 8 | `DHH02\PocoJSON.dll` | 267 KB | **C++ MSVC native**（Poco JSON 库） | Ghidra ✅ |
| 9 | `DHH02\PocoNet.dll` | 929 KB | **C++ MSVC native**（Poco Net 库） | Ghidra ✅ |
| 10 | `CNC\iot_CNC_PLC_IMM.exe` | **15.7 MB** | **Go 1.24.5**（大型主网关，8435 个字符串，6521 个 Go 类型） | 未反编译（意外发现） |

---

## 3. ILSpy .NET 反编译结果

### 3.1 代码规模统计

| 样本 | .cs 行数 | 业务类 |
|---|---|---|
| HanBaCollector | 218 | `Program` / `MqttClient` / `JsonMeasData` / `HttpMemAPIService` |
| LnkCollector | 240 | `Program` / `MqttClient` |
| HslCommunication | **160,555** | 89 个命名空间，700+ 类型 |

### 3.2 LnkCollector.dll（CNC04）核心业务

**架构**：.NET Core 3.1 → `MqttClient`（HslCommunication.MQTT） → JSON → MQTT Broker `192.168.0.87:1883`，主题 `realtime/CNC04`

**数据源**：通过 P/Invoke 调用原生 **RemoteComm.dll**（Cdecl 调用约定）连接 CNC `192.168.3.14`

**采集指标**（在反编译源码中硬编码）：

| 字段编码 | 含义 | 数据源 | 寄存器/宏 |
|---|---|---|---|
| WorkTime | 系统加工时间 | CNC 宏变量 | 33868 |
| RunTime | 系统运行时间 | CNC 宏变量 | 2097 |
| CutTime | 切削时间 | CNC 宏变量 | 33565 |
| Products | 加工件数 | CNC 宏变量 | 33869 |
| RunStatus | 运行状态 | PLC 寄存器 | 42.0 |
| StopStatus | 停机状态 | PLC 寄存器 | 42.1 |
| WarnStatus | 系统报警状态 | PLC 寄存器 | 50.14 |

**循环模式**：每 1 秒采集一项 → 15 秒 MQTT 重连窗口 → 异常重试 5 秒

### 3.3 HanBaCollector.exe（DHH02）核心业务

**架构**：.NET Framework 4.7.2 → `MqttClient` → JSON → MQTT Broker（未指定 host）→ 主题 `realtime/iot/dhh02`

**关键发现 — 硬编码授权码**：

```csharp
if (!Authorization.SetAuthorizationCode("6a14cf02-ccc8-458e-a1f3-64727d0cf775"))
{
    Console.WriteLine("Authorization failed! The current program can only be used for 8 hours!");
    return;
}
```

- **授权失败时程序只能运行 8 小时**（试用模式）
- 授权码 `6a14cf02-ccc8-458e-a1f3-64727d0cf775` 在源码中明文可见
- 授权实现可能位于 `HttpMemAPI.dll` 或第三方依赖中

**数据源**：通过 P/Invoke 调用原生 **HttpMemAPI.dll**：

```csharp
[DllImport("HttpMemAPI.dll", CallingConvention = CallingConvention.Cdecl)]
public static extern bool HttpGDEGetBit(
    [In][MarshalAs(UnmanagedType.AsAny)] object szServerIP,
    ushort wServerPort,
    [In][MarshalAs(UnmanagedType.AsAny)] object szMMFf,
    out int dwVal);
```

**采集指标**（设备 `192.168.3.22:9990`，每 5 秒）：

| code | 含义 | MMFf 寄存器 |
|---|---|---|
| YXMS | 运行模式 | R0577 |
| DQDL | 电流 | R0974 |
| FDSJH | 放电火花_计数? | R1929 |
| FDSJF | 放电火花_幅度? | R1928 |
| KJSJH | 加工时间_计数? | R1443 |
| KJSJF | 加工时间_幅度? | R1442 |

注：字段名（FDSJH/FDSJF/KJSJH/KJSJF）反编译产物中显示为拼音缩写，疑似中文"放电计数/放电幅度/加工时间/..."的 GB2312 → UTF-8 转换错误。

### 3.4 HslCommunication.dll 命名空间分布（89 个）

**核心层**：
- `HslCommunication.Core.Net` — 网络核心
- `HslCommunication.Core.Address` — 通信地址解析
- `HslCommunication.Core.IMessage` — 消息协议
- `HslCommunication.Core.Pipe` — 管道
- `HslCommunication.Core.Security` — 安全（加密/签名）
- `HslCommunication.Core.Types` — 数据类型

**通信协议**：
- `HslCommunication.MQTT`（已在反编译中验证有完整实现）
- `HslCommunication.Enthernet.Redis` — Redis 客户端
- `HslCommunication.Enthernet` — 以太网协议族

**工业协议（关键）**：
- **`HslCommunication.CNC.Fanuc`** — **Fanuc CNC 通信支持**
- `HslCommunication.DCS` — 分布式控制系统
- `HslCommunication.DTU` — 数据传输单元（无线）
- `HslCommunication.Instrument.CJT` / `Instrument.CJT.Helper` — 仪器仪表协议

**算法库**：
- `HslCommunication.Algorithms.ConnectPool` — 连接池
- `HslCommunication.Algorithms.PID` — PID 控制算法
- `HslCommunication.Algorithms.Fourier` — 傅里叶变换

**UI 控件**：
- `HslCommunication.Controls`

**结论**：HslCommunication 是一个**工业 IoT 全栈通信库**，覆盖 PLC/CNC/仪表/DCS/DTU/PID 等场景，与用户工作区业务高度匹配。

---

## 4. Ghidra 原生二进制反编译结果

### 4.1 总体统计（6 个 dll/exe，全部 100% 反编译成功）

| 样本 | 反编译字节 | 反编译行数 | 函数数 | 编译器 |
|---|---|---|---|---|
| MelCollector_DHH04.exe | 1,588,823 | 41,973 | 1,307 | MSVC `x86:LE:32:default:windows` |
| RemoteComm.dll | 391,595 | 12,911 | 377 | MSVC `x86:LE:32:default:windows` |
| MknEdmRm1201.dll | 551,324 | 18,294 | 498 | MSVC `x86:LE:32:default:windows` |
| PocoFoundation.dll | 7,162,978 | 188,225 | 7,595 | MSVC `x86:LE:32:default:windows`（C++ Poco Foundation） |
| PocoJSON.dll | 1,119,995 | 31,135 | (100s) | MSVC `x86:LE:32:default:windows` |
| PocoNet.dll | 4,609,903 | 115,727 | (1000s) | MSVC `x86:LE:32:default:windows` |
| **合计** | **15.4 MB** | **408,265** | **~10,376** | — |

### 4.2 RemoteComm.dll — CNC/PLC 通信 SDK（377 函数）

**导出 API（28 个核心）**：

| 类别 | API |
|---|---|
| **连接管理** | `remote_new_connect(ip)` / `remote_close()` / `remote_connect_status()` |
| **CNC 宏变量** | `remote_read_macro(handle, macroId)` / `remote_read_macro_p(handle, macroId, val[])` |
| **PLC 变量** | `remote_read_plc_variable(handle, addr)` / `remote_read_plc_variable_2/3` / `remote_read_plc_variable_p` / **`remote_read_plc_variable_p_2`** |
| **文件操作** | `remote_open_file` / `remote_get_file_line` / `remote_download_file` / `remote_delete_file` / `remote_get_open_file_*` |
| **CNC 命令** | `remote_run_string`（执行 CNC 字符串命令） |
| **元信息** | `remote_get_version` / `remote_getMacAddress` / `remote_getMachineSerial` / `remote_get_exe_file_md5sum` / `remote_get_break_point_info` |
| **License** | `remote_setLicense` |
| **超时** | `remote_set_receive_timeout` / `remote_set_send_timeout` |

**实现细节**（Ghidra 反编译 `remote_read_macro_p`）：

```c
void __cdecl remote_read_macro_p(uint param_1, undefined4 param_2, double *param_3)
{
    void *this;
    this = (void *)FUN_10001dd0();         // 单例管理器
    FUN_10009820(this, param_1, param_2, param_3);  // 实际读取
    return;
}
```

- 使用 C++ 对象封装（`FUN_10001dd0()` 返回 this 指针）
- **依赖库**：`WS2_32.DLL`（Winsock）、`MSVCP140.DLL`、`VCRUNTIME140.DLL`、`KERNEL32.DLL` — **C++ + 网络通信 + MSVC runtime**
- `remote_new_connect` 返回 `float`（疑似状态码：0.0 = 失败，非 0 = 成功）

**与 LnkCollector 的调用映射**（验证业务完整性）：

| LnkCollector 调用（P/Invoke） | RemoteComm 导出函数 | 业务 |
|---|---|---|
| `remote_new_connect("192.168.3.14")` | `remote_new_connect` | 建立到 CNC 的连接 |
| `remote_read_macro_p(num, 33868, array)` | `remote_read_macro_p` | 读 CNC 宏变量 |
| `remote_read_plc_variable_p_2(num, "42.0", 1, array)` | `remote_read_plc_variable_p_2` | 读 PLC 寄存器 |

**结论**：LnkCollector.dll（.NET）→ RemoteComm.dll（C++ Winsock）→ CNC/PLC 是完整的工业数据采集链路。

### 4.3 MknEdmRm1201.dll — 三菱 CNC EDM 电火花加工 SDK（498 函数）

**关键类**：
- `CRmTcp` — TCP 连接对象（MELSEC 协议）
- `CMelLt` — MELSEC PLC 数据操作
- `CVrtMel` — 三菱 CNC 垂直加工中心

**关键 API**（按业务分组）：
- **报警管理**：`GetAlmStatus` / `GetAlmNum` / `GetAlmNewMsg` / `GetAlmList`
- **EDM 加工参数**：`GetEfctSpCondData` / `GetEfctSpCond`（电加工条件数据）
- **加工数据**：`RnwGetMachDepth`（加工深度）/ `RnwGetCondData`（条件数据）/ `RnwGetEfctRadius`（电加工半径）/ `RnwGetEfctIES` / `RnwGetEfctEnablePulse`（电加工脉冲使能）/ `RnwGetEfctADC` / `RnwGetWireInfo`（电极丝信息）
- **进程管理**：`CreateSnapshotProcess` / `CloseSnapshotProcess` / `GetSnapshotProcess` / `SearchExecuteProc` / `DeletePrg`

**结论**：MknEdmRm1201 是**三菱电机 CNC + MELSEC PLC 的电火花加工机床专用 SDK**，MZS01/DHH04 的 MelCollector 通过此 SDK 与三菱 EDM 机床通信。

### 4.4 MelCollector.exe — DHH04 主程序（1,307 函数）

**架构**：C++ MSVC + STL + MQTT 异步客户端（`async_client` 类）

**MQTT 协议支持**：警告中明确出现 `MQTTPropertyCodes` / `MQTTReasonCodes` 枚举，说明使用 **MQTT 5.0** 完整协议栈

**main 函数特征**：
- 使用 `basic_string<char>` / `basic_ostream<char>` / `buffer_ref<char>` 等 STL 类型
- 引用 `async_client`（MQTT 异步客户端）
- 7494 字节的 main 函数（业务逻辑复杂）

**注意**：MZS01 目录下有同名 MelCollector.exe（234,496 bytes，与 DHH04 完全相同），疑为同一程序部署到不同设备。

### 4.5 Poco C++ 库（DHH02 部署，3 个 dll）

- **PocoFoundation.dll**（1.6 MB，7595 函数）— C++ 基础库（字符串、文件系统、线程、网络抽象等）
- **PocoJSON.dll**（267 KB）— JSON 解析/生成
- **PocoNet.dll**（929 KB）— 网络库（Socket、HTTPClient、HTTPRequest 等）

这些是 **DHH02/HanBaCollector.exe 的运行时依赖**（虽然反编译产物未直接显示 C# `using` Poco，但通过 P/Invoke HttpMemAPI.dll 间接使用）。

---

## 5. 跨样本洞察

### 5.1 业务架构图（推断）

```
┌────────────────────────────────────────────────────────────────────┐
│                     CNC/iot_CNC_PLC_IMM.exe                         │
│                     (CNC/, 15.7 MB, Go 1.24.5)                       │
│                     【未反编译，待办】                               │
│   主网关 — 8435 个 Go 字符串，6521 个 Go 类型，Go strings 大量      │
└────────────────────────────────────────────────────────────────────┘
                                  │
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
┌─────────────────┐     ┌─────────────────┐         ┌─────────────────┐
│  LnkCollector    │     │  MelCollector    │         │ HanBaCollector  │
│  (CNC04)         │     │  (DHH04/MZS01)   │         │  (DHH02)        │
│  .NET Core 3.1   │     │  C++ MSVC        │         │ .NET Fx 4.7.2   │
│  12 KB           │     │  234 KB          │         │ 10 KB           │
│  MQTT → 1883     │     │  MQTT (async)    │         │  MQTT (8h 试用) │
└─────────────────┘     └─────────────────┘         └─────────────────┘
       │ P/Invoke                │ P/Invoke                       │ P/Invoke
       ▼                         ▼                                ▼
┌─────────────────┐     ┌─────────────────┐         ┌─────────────────┐
│ RemoteComm.dll   │     │ MknEdmRm1201.dll │         │ HttpMemAPI.dll  │
│ (CNC04)          │     │ (DHH04/MZS01)    │         │ (DHH02)         │
│ C++ Winsock      │     │ 三菱 CNC EDM SDK │         │ 原生（未分析）   │
│ 75 KB / 377 fn   │     │ 135 KB / 498 fn  │         │  30 KB          │
└─────────────────┘     └─────────────────┘         └─────────────────┘
       │                         │                                │
       ▼                         ▼                                ▼
   CNC/PLC                  三菱 EDM 机床                  DHH-02 设备
   (Fanuc/Mitsubishi)       (192.168.3.x)                 (192.168.3.22:9990)
```

### 5.2 通信协议线索

- **MQTT Broker**：192.168.0.87:1883（CNC04 已知，DHH02 未明确）
- **CNC/PLC 协议**：私有 TCP（RemoteComm 封装）
- **CNC SDK**：Fanuc（来自 HslCommunication.CNC.Fanuc）、三菱 CNC EDM（MknEdmRm1201）
- **采集频率**：CNC04 每秒、DHH02 每 5 秒

### 5.3 安全风险面（已确认）

| 风险 | 位置 | 证据 |
|---|---|---|
| **硬编码授权码** | `DHH02/HanBaCollector.exe` | `Authorization.SetAuthorizationCode("6a14cf02-...")` + 8h 试用提示 |
| **明文 IP/端口** | `LnkCollector.dll` | `192.168.0.87` / `192.168.3.14` / `192.168.3.22` 全部硬编码 |
| **明文 MQTT 凭据** | `LnkCollector.dll` | `new MqttCredential("", "")` — 空凭据，无认证 |
| **MD5 校验缺失** | RemoteComm 提供 `remote_get_exe_file_md5sum` 但未在 .NET 端调用 | 完整性校验未启用 |
| **CNC 命令注入面** | `RemoteComm` 提供 `remote_run_string` | 未在当前 .NET 端被调用，但是攻击面 |

### 5.4 意外发现 — CNC 主网关 iot_CNC_PLC_IMM.exe 是 Go 二进制

- 15.7 MB，**用 Go 1.24.5 编译**
- application.log 显示 Ghidra 自动识别为 Go：
  ```
  GoRttiMapper: Reading Go binary info: iot_CNC_PLC_IMM.exe
  GoRttiMapper: Using Go API snapshot for version 1.24.5
  GolangSymbolAnalyzer: Go version 1.24.5
  GolangStringAnalyzer: Go strings found: 8435
  ```
- 6521 个 Go 类型、8435 个 Go 字符串 — 这是**真正的大型网关服务**
- 推测可能是 DHH02/CNC 系列 IoT 项目的**主控制器**，向上对接 ERP/MES，向下管理所有 Collector

---

## 6. 风险与限制

### 6.1 反编译产物局限性

| 限制 | 说明 |
|---|---|
| 变量名/注释丢失 | 反编译产物无 PDB 信息，函数内变量名为 `param_1` / `local_8` 等 |
| 内联函数过度展开 | 反编译器对 inline 函数展开导致行数偏多 |
| Go 二进制分析弱 | Ghidra 的 Go 反编译器仍在演进（GoTypeManager warnings） |
| .NET 混淆未测试 | 当前样本无混淆，ConfuserEx 等会大幅降低可读性 |

### 6.2 本次未完成项

- **`CNC/iot_CNC_PLC_IMM.exe`（Go 1.24.5, 15.7 MB）未反编译** — 需要单独启动 Ghidra headless 任务，预期反编译产物可达 100+ MB，导出函数 5000+。建议在 GUI 模式下分批分析。
- **`HttpMemAPI.dll`（DHH02, 30 KB）未反编译** — HanBaCollector 的 P/Invoke 目标，可能包含授权码验证逻辑
- **`MknEdmRm.dll`（98 KB）未反编译** — 与 `MknEdmRm1201.dll` 配对，可能是兼容旧版本的 SDK
- **`System.IO.Ports.dll` 等 5 个 .NET 标准库未反编译** — 标准库，价值低
- **`CNC/CNC` 目录配置文件**（ini/lua）— 未做协议层分析

### 6.3 工具链稳定性观察

- **Ghidra headless 限制**：项目路径、scriptPath 不能含 `.` 开头的目录（`.decomp` 失败，改用 `ghidra-projects` 和 `ghidra-scripts`）
- **Out-File 在并发后台任务中失效**：Ghidra 实际进程在跑，但 Out-File 写日志失败。**确认 Ghidra 状态必须看 `C:\Users\admin\AppData\Roaming\ghidra\ghidra_12.1.3_PUBLIC\application.log`**

---

## 7. 后续建议

### 7.1 高优先级

1. **反编译 iot_CNC_PLC_IMM.exe**（Go 大型网关） — 这是整个工作区的核心主控程序，但本轮未跑：
   ```
   ghidra-headless F:\JQKJ\ghidra-projects\iotCNC_PLC_IMM iotCNC \
     -import F:\JQKJ\CNC\iot_CNC_PLC_IMM.exe \
     -analysisTimeoutPerFile 1800 \
     -scriptPath F:\JQKJ\ghidra-scripts \
     -postScript ExportDecompileToFile.java F:\JQKJ\ghidra-projects\iotCNC_PLC_IMM\decompile.txt
   ```
2. **反编译 HttpMemAPI.dll + MknEdmRm.dll** — 补齐 DHH02/CNC04 通信栈完整图
3. **用 dnSpyEx 调试 LnkCollector** — 实际跑起来观察 MQTT 消息内容（需要 192.168.3.14/192.168.0.87 网络可达）

### 7.2 中优先级

4. **Ghidra GUI 启动分析**（基于已创建的 .rep 项目）：
   ```
   ghidra F:\JQKJ\ghidra-projects\PocoFoundation\PocoFoundation.rep
   ```
   在 GUI 里能查看调用图、交叉引用、函数关系图，更直观
5. **协议层分析**：解析 `protocol_cnc.ini` / `protocol.ini`（CNC 目录），确认与反编译中硬编码的 IP/端口/宏变量编号一致
6. **license.lic + private.pem 分析** — 是否为非对称加密授权

### 7.3 长期建议

7. **IoC 提取**：本次反编译未涉及恶意行为分析（用户工作区非恶意场景），但若需做安全审计，可结合 `binary-analysis-patterns` skill 输出更系统的检查表
8. **建立版本基线**：当前反编译产物建议归档到 `F:\JQKJ\.decomp\baseline-2026-09-17\` 便于后续版本对比

---

## 8. 产物索引

```
F:\JQKJ\
├── docs\superpowers\
│   ├── plans\2026-09-17-decompile-toolchain-install.md       (实施计划)
│   └── reports\2026-09-17-decompile-analysis.md             (本报告)
├── .tools\
│   ├── ilspy\ILSpy.exe + ILSpy_windows_11.0.0.9375-x64\      (19.2 MB)
│   ├── dnspyex\dnSpy.exe                                     (94.3 MB)
│   ├── ghidra\ghidra_12.1.3_PUBLIC\ghidraRun.bat             (543 MB 解压后 1.5 GB)
│   └── bin\
│       ├── ilspy.cmd / dnspy.cmd / ghidra.cmd / ghidra-headless.cmd
├── .decomp\
│   ├── ilspy\                                                (3 个 .NET 样本源码)
│   │   ├── HanBaCollector\HanBaCollector.decompiled.cs
│   │   ├── LnkCollector\LnkCollector.decompiled.cs
│   │   └── HslCommunication_DHH02\HslCommunication.decompiled.cs (160,555 行)
│   └── raw-evidence\                                         (中间分析证据)
│       ├── samples.json                                      (样本映射)
│       ├── ilspy-stats.txt
│       ├── lnkcollector-types.txt / hanbacollector-types.txt
│       ├── hslcommunication-namespaces.txt (89 个命名空间)
│       ├── remotecomm-exports.txt (28 个 API)
│       ├── mknedmrm1201-functions.txt (498 函数)
│       ├── melcollector-exports.txt
│       ├── pocofoundation-isAscii.txt (确认 C++ Poco)
│       ├── ...其他 evidence
├── ghidra-projects\                                          (Ghidra 项目 + decompile.txt)
│   ├── MelCollector_DHH04\decompile.txt (1.5 MB / 41973 行 / 1307 函数)
│   ├── RemoteComm\decompile.txt (377 函数)
│   ├── PocoFoundation\decompile.txt (7.2 MB / 188225 行 / 7595 函数)
│   ├── PocoJSON\decompile.txt (1.1 MB)
│   ├── PocoNet\decompile.txt (4.6 MB)
│   └── MknEdmRm1201_DHH04\decompile.txt (498 函数)
└── ghidra-scripts\
    └── ExportDecompileToFile.java                           (Ghidra postScript)
```

---

## 9. 元数据

- **实施计划**：`docs/superpowers/plans/2026-09-17-decompile-toolchain-install.md`
- **本次会话使用的 skills**：`brainstorming` / `writing-plans` / 已挂载的 `binary-analysis-patterns` / `ctf-reverse` / `ctf-malware`
- **总耗时**：约 90 分钟（含 Ghidra 6 个并行任务约 30 分钟）
- **总产物**：15.4 MB Ghidra 反编译 + 6.7 MB ILSpy 反编译 + 7 个工具 shim + 完整文档
