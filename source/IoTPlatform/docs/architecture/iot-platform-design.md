# IoTPlatform 架构设计文档

**版本**：v0.1.0-draft
**日期**：2026-09-17
**目标**：基于反编译产物还原为完整可编译源码平台
**范围**：CNC/PLC/工业 IoT 数据采集平台

---

## 1. 背景与目标

### 1.1 原始工作区分析

工作区 `f:\JQKJ` 包含多个 IoT 数据采集相关项目的**预编译二进制产物**：

| 目录 | 二进制 | 类型 | 用途 |
|---|---|---|---|
| `CNC\` | `iot_CNC_PLC_IMM.exe` (15.7MB) | Go 1.24.5 | 主网关（HTTP + Web UI） |
| `CNC04\` | `LnkCollector.exe` + `RemoteComm.dll` | .NET 8 / C++ | CNC04 设备采集 |
| `DHH02\` | `HanBaCollector.exe` + `HttpMemAPI.dll` | .NET 8 / C++ (MFC) | DHH-02 设备采集 |
| `DHH04/`, `MZS01\` | `MelCollector.exe` + `MknEdmRm1201.dll` + `MknEdmRm.dll` | C++ | 三菱 CNC EDM 采集 |

**反编译证据**：12 个二进制全部反编译完成，~14,000 函数，关键业务逻辑已抽取。

### 1.2 重建目标

1. **完整源码可编译**：所有预编译二进制从反编译产物还原为可维护源码
2. **UI 用户自开发**：本平台只提供 UI 接口骨架与示例，具体 UI 由用户实现
3. **协议适配器即插即用**：新增设备/协议只需实现接口
4. **运行时不依赖原 dll**：替换原始 C++ SDK 为 Go 重写 + HslCommunication 协议
5. **开源技术栈**：基于 HslCommunication（MIT）+ MQTTnet（MIT）+ Echo（MIT）

---

## 2. 技术选型

| 层 | 技术 | 版本 | 理由 |
|---|---|---|---|
| 采集层 (.NET) | .NET 8 LTS | 8.0 | 跨平台 LTS，NuGet 生态成熟 |
| 采集层 (Go) | Go | 1.24+ | 与原 iot_CNC_PLC_IMM.exe 一致 |
| 通信 (MQTT) | MQTTnet | 5.2 | 纯 C# MQTT 客户端，支持 5.0 |
| 工业协议 | HslCommunication | 13.0 | MIT 开源，覆盖 Fanuc/Melsec/Modbus |
| Web 框架 (Go) | Echo | 4.x | 与原二进制使用一致 |
| 配置 | Microsoft.Extensions.Configuration | 10.0 | 标准 .NET 配置 |
| 日志 | Microsoft.Extensions.Logging | 10.0 | 标准 .NET 日志 |
| 测试 | xUnit + Moq | latest | .NET 社区标准 |
| UI 示例 | WPF (.NET 8 Windows) | 8.0 | 用户可改 WPF/Avalonia/MAUI |

---

## 3. 解决方案结构

```
f:\JQKJ\source\IoTPlatform\
├── IoTPlatform.sln                         # .NET 解决方案
├── README.md
├── docs\
│   └── architecture\
│       └── iot-platform-design.md           # 本文档
├── src\
│   ├── IoTPlatform.Core\                    # 核心库（接口/基类/通用）
│   │   ├── Abstractions\
│   │   │   ├── ICollector.cs              # 采集器接口
│   │   │   ├── IDeviceAdapter.cs           # 设备协议适配器接口
│   │   │   ├── IDataSink.cs               # 数据汇接口（MQTT/文件/DB）
│   │   │   └── ICollectorView.cs          # UI 视图接口
│   │   ├── Base\
│   │   │   ├── BaseCollector.cs           # 采集器基类
│   │   │   └── BaseAdapter.cs             # 适配器基类
│   │   ├── Models\
│   │   │   ├── DeviceConfig.cs            # 设备配置
│   │   │   ├── TagDefinition.cs           # 数据点定义
│   │   │   └── SampleData.cs              # 采样数据
│   │   ├── Pipelines\
│   │   │   ├── CollectorRegistry.cs       # 采集器注册中心
│   │   │   ├── MqttDataSink.cs            # MQTT 数据汇
│   │   │   └── JsonDataSink.cs            # JSON 文件数据汇
│   │   └── IoTPlatform.Core.csproj
│   │
│   ├── IoTPlatform.Adapters\               # 4 个协议适配器
│   │   ├── FanucCncAdapter.cs             # Fanuc CNC（基于 HslCommunication.CNC.Fanuc）
│   │   ├── HttpMemAdapter.cs              # HTTP Memory 协议（DHH-02 设备）
│   │   ├── MitsubishiEdmAdapter.cs        # 三菱 CNC EDM（MknEdmRm 系列）
│   │   ├── GoGatewayAdapter.cs            # Go 主网关 HTTP API 客户端
│   │   └── IoTPlatform.Adapters.csproj
│   │
│   └── IoTPlatform.Host\                   # 自宿主 console exe
│       ├── Program.cs                      # 入口
│       ├── appsettings.json                # 配置
│       └── IoTPlatform.Host.csproj
│
├── samples\
│   └── IoTPlatform.UI.Wpf\                 # WPF UI 示例（骨架）
│       ├── App.xaml
│       ├── MainWindow.xaml
│       ├── ViewModels\
│       └── IoTPlatform.UI.Wpf.csproj
│
└── tests\
    └── IoTPlatform.Core.Tests\             # 核心库单元测试
        ├── CollectorRegistryTests.cs
        └── IoTPlatform.Core.Tests.csproj
```

**Go 主网关**（独立项目）：

```
f:\JQKJ\source\IoTPlatform-GoGateway\         # 独立 Go module
├── go.mod
├── go.sum
├── main.go                                     # 入口（原 main.main）
├── embed_static.go                             # embed.FS 静态资源
├── embed_sdk.go                                # embed.FS SDK
├── internal/
│   ├── config/
│   │   ├── version.go                          # VersionInit/VersionString
│   │   └── ini.go                              # WriteIni（setting.ini）
│   ├── handlers/
│   │   ├── menu.go                             # 菜单 handler
│   │   ├── protocol.go                         # 协议 handler
│   │   └── frontend.go                         # 前端 handler
│   ├── logger/
│   │   └── log.go                              # LogInfo/Logger.InitLog
│   ├── middleware/
│   │   ├── strip.go                            # StripPrefix
│   │   ├── wrap.go                             # WrapHandler
│   │   └── recover.go                          # Recover/RecoverWithConfig
│   └── protocol/
│       ├── modbus.go                           # Modbus 协议（推断）
│       ├── mqtt.go                             # MQTT 协议（推断）
│       └── opcua.go                            # OPC UA 协议（推断）
└── web/                                         # 嵌入式前端
    ├── static/
    └── sdk/
```

---

## 4. 核心接口设计

### 4.1 `ICollector` — 采集器接口（设备维度）

```csharp
namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 采集器接口：每个设备实例对应一个 Collector
/// 负责周期采集数据并通过 IDataSink 上报
/// </summary>
public interface ICollector : IAsyncDisposable
{
    /// <summary>设备唯一标识（如 "CNC04", "DHH-02", "DHH-04"）</summary>
    string DeviceId { get; }

    /// <summary>采集器状态</summary>
    CollectorStatus Status { get; }

    /// <summary>采集周期</summary>
    TimeSpan SampleInterval { get; }

    /// <summary>启动采集循环</summary>
    Task StartAsync(CancellationToken ct = default);

    /// <summary>停止采集循环</summary>
    Task StopAsync(CancellationToken ct = default);

    /// <summary>手动触发一次采集（UI 测试用）</summary>
    Task<SampleData> SampleOnceAsync(CancellationToken ct = default);

    /// <summary>状态变化事件</summary>
    event EventHandler<CollectorStatusChangedEventArgs>? StatusChanged;
}

public enum CollectorStatus
{
    Stopped,
    Starting,
    Running,
    Degraded,      // 部分数据源失败（如 MQTT 重连中）
    Error,
    Stopping
}
```

### 4.2 `IDeviceAdapter` — 协议适配器接口（协议维度）

```csharp
namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 设备协议适配器：封装具体的工业协议实现
/// 由 Collector 通过 IDeviceAdapterFactory 创建
/// </summary>
public interface IDeviceAdapter : IAsyncDisposable
{
    /// <summary>协议名称（如 "FanucCNC", "HttpMem", "MitsubishiEdm"）</summary>
    string ProtocolName { get; }

    /// <summary>连接设备</summary>
    Task<bool> ConnectAsync(DeviceConnectionConfig config, CancellationToken ct = default);

    /// <summary>断开连接</summary>
    Task DisconnectAsync(CancellationToken ct = default);

    /// <summary>读取标签值（通用接口）</summary>
    Task<TagReadResult> ReadTagAsync(TagDefinition tag, CancellationToken ct = default);

    /// <summary>批量读取多个标签</summary>
    Task<IReadOnlyList<TagReadResult>> ReadTagsAsync(
        IEnumerable<TagDefinition> tags, CancellationToken ct = default);

    /// <summary>写入标签值（如 PLC 写入）</summary>
    Task<bool> WriteTagAsync(TagDefinition tag, object value, CancellationToken ct = default);
}
```

### 4.3 `IDataSink` — 数据汇接口

```csharp
namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// 数据汇：Collector 采集后上报的目标
/// 默认实现：MqttDataSink（MQTT Broker）
/// 扩展：JsonDataSink（本地 JSON 文件）、DbDataSink（InfluxDB）
/// </summary>
public interface IDataSink : IAsyncDisposable
{
    /// <summary>发布采样数据</summary>
    Task PublishAsync(string topic, SampleData data, CancellationToken ct = default);

    /// <summary>批量发布</summary>
    Task PublishBatchAsync(string topic, IEnumerable<SampleData> data, CancellationToken ct = default);
}
```

### 4.4 `ICollectorView` — UI 接口

```csharp
namespace IoTPlatform.Core.Abstractions;

/// <summary>
/// UI 视图接口：UI 层只需实现这个接口即可与采集平台交互
/// 不绑定具体 UI 框架（WPF / Avalonia / MAUI / WinForms 通用）
/// </summary>
public interface ICollectorView
{
    /// <summary>显示采集器列表</summary>
    void RenderCollectors(IEnumerable<ICollector> collectors);

    /// <summary>显示实时数据流</summary>
    void RenderSampleData(SampleData data);

    /// <summary>显示状态变化</summary>
    void RenderStatusChange(CollectorStatusChangedEventArgs args);

    /// <summary>显示错误</summary>
    void RenderError(Exception ex, string context);
}
```

---

## 5. 三个 Collector 的反编译 → 重写映射

### 5.1 LnkCollector.dll → LnkCollectorForCNC04

**反编译关键 API**：
- `MqttClient.Init()` → 连 192.168.0.87:1883
- `MqttClient.ConnectServer()`
- `MqttClient.PublishMessage("realtime/CNC04", json)`
- P/Invoke `remote_new_connect("192.168.3.14")` → handle
- P/Invoke `remote_read_macro_p(handle, macroId, val[])`
- P/Invoke `remote_read_plc_variable_p_2(handle, "42.0", 1, val[])`

**重写策略**（基于 HslCommunication）：
- 替换 RemoteComm.dll → 用 HslCommunication.MelsecFanuc（如果 CNC04 是 Fanuc）
- 或自实现 `FanucCncAdapter`（如果协议私有）
- MQTT 用 MQTTnet 替代 HslCommunication.MQTT

**采集指标表**：
```csharp
new TagDefinition("WorkTime", TagType.CNCMacro, address: 33868)
new TagDefinition("RunTime", TagType.CNCMacro, address: 2097)
new TagDefinition("CutTime", TagType.CNCMacro, address: 33565)
new TagDefinition("Products", TagType.CNCMacro, address: 33869)
new TagDefinition("RunStatus", TagType.PLCRegister, address: "42.0")
new TagDefinition("StopStatus", TagType.PLCRegister, address: "42.1")
new TagDefinition("WarnStatus", TagType.PLCRegister, address: "50.14")
```

### 5.2 HanBaCollector.exe → HanBaCollectorForDHH02

**反编译关键 API**：
- `HttpGDEGetBit(serverIP, port, "R0577", out dwVal)` → HttpMemAPI
- 6 个寄存器：R0577 (YXMS), R0974 (DQDL), R1929, R1928, R1443, R1442
- MQTT 主题：`realtime/iot/dhh02`

**重写策略**：
- `HttpMemAdapter` 直接用 .NET HttpClient（因为协议不复杂）
- 不需要保留 C++ 桥接

### 5.3 MelCollector.exe → MelCollectorForDHH04

**反编译关键**：
- C++ MSVC, MQTT 5.0（async_client + MQTTPropertyCodes）
- 三菱 CNC EDM SDK（MknEdmRm1201.dll）
- 函数：GetAlmStatus, GetEfctSpCondData, RnwGetMachDepth 等

**重写策略**：
- 用 HslCommunication.MelsecA1E（三菱 PLC 协议）
- 自实现 EDM 协议部分（基于已反编译的 C++ 函数映射）

---

## 6. Go 主网关架构（iot_CNC_PLC_IMM 重写）

### 6.1 业务功能（反编译推断）

基于 `E:\workspace\PersonalProject\scada_go\main.go:54` 反编译注释 + `elinks/*` 命名空间推断：

```
iot_CNC_PLC_IMM (主网关服务)
├── HTTP Server (Echo framework)
│   ├── GET  /                    # 嵌入式前端 SPA (embed.FS "static/")
│   ├── GET  /sdk                 # 嵌入式 SDK UI (embed.FS "sdk/")
│   ├── GET  /api/menu           # 菜单 (elinks/handlers/menu.go)
│   ├── GET  /api/protocol/*     # 协议 (elinks/handlers/protocol.go)
│   ├── GET  /api/version        # 版本 (elinks/handlers/version.go)
│   └── POST /api/command/*      # 命令
├── 中间件链
│   ├── StripPrefix   (URL 前缀剥离)
│   ├── WrapHandler   (HTTP handler 包装)
│   └── Recover       (panic 恢复)
├── 初始化
│   ├── Logger.InitLog
│   ├── Logger.LogInfo
│   ├── VersionInit + WriteIni("setting", "appVersion", version)
│   └── getFrontendFS / getSDKFS
└── 协议层
    ├── modbus (推断)
    ├── mqtt  (推断)
    └── opcua (推断)
```

### 6.2 Go 项目重建路径

**阶段 A**：从 35.5MB 反编译产物提取核心类型 + 函数签名
**阶段 B**：用 echo 框架重建 HTTP 路由
**阶段 C**：嵌入式前端用简单的 HTML/JS 占位（最终由 UI 团队提供）
**阶段 D**：协议层先用 Mock，逐步从反编译还原

---

## 7. C++ SDK 重建（RemoteComm / MknEdmRm1201 / HttpMemAPI / MknEdmRm）

### 7.1 重建策略

**问题**：原始 C++ SDK 是私有协议实现（TCP 自定义二进制），无法仅从反编译产物还原为可编译源码（缺协议规范、缺设计文档）。

**两种重建路径**：
1. **路径 A — 完全抛弃 C++，用 HslCommunication + 自实现协议层**
   - 优点：纯托管代码，跨平台，可维护
   - 缺点：私有协议需要时间逆向
2. **路径 B — 用 C++ 重新编译预编译 dll（半源码）**
   - 优点：保留原行为
   - 缺点：仍然是二进制，不是源码

**本平台选择路径 A**（彻底抛弃 C++）。

### 7.2 协议适配器替代映射

| 原 C++ SDK | 替代实现 | 备注 |
|---|---|---|
| RemoteComm.dll (CNC) | HslCommunication.CNC.Fanuc | CNC04 用 Fanuc 协议 |
| MknEdmRm1201.dll (EDM) | HslCommunication.MelsecA1E + 自实现 EDM | EDM 部分需自实现 |
| HttpMemAPI.dll | .NET HttpClient + 自实现协议 | 简单 HTTP 协议 |
| MknEdmRm.dll (旧版) | HslCommunication.MelsecA1E | 旧版 SDK 协议 |

---

## 8. 数据流

```
┌──────────────────┐
│   工业设备        │
│  (CNC/PLC/仪器)  │
└────────┬─────────┘
         │ 私有协议（TCP/RTU/HTTP）
         ▼
┌──────────────────┐  ┌─────────────────┐
│ IDeviceAdapter   │  │ IDeviceAdapter  │
│ FanucCncAdapter  │  │ HttpMemAdapter  │
└────────┬─────────┘  └────────┬────────┘
         └────────┬─────────────┘
                  ▼
┌──────────────────────────────────────┐
│            ICollector               │
│  (周期采样 / 状态管理 / 异常重试)      │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│           IDataSink                  │
│  MqttDataSink / JsonDataSink         │
└────────┬─────────────────────────────┘
         │ MQTT (JSON payload)
         ▼
┌──────────────────┐
│  MQTT Broker     │ 192.168.0.87:1883
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  后端系统 / MES  │
└──────────────────┘
```

---

## 9. 配置驱动

```json
// appsettings.json
{
  "Collectors": [
    {
      "DeviceId": "CNC04",
      "SampleIntervalMs": 1000,
      "Adapter": {
        "Type": "FanucCnc",
        "Endpoint": "192.168.3.14",
        "Port": 8193
      },
      "Mqtt": {
        "Broker": "192.168.0.87",
        "Port": 1883,
        "ClientId": "lnk",
        "Credentials": { "Username": "", "Password": "" }
      },
      "Tags": [
        { "Name": "WorkTime", "Type": "CNCMacro", "Address": "33868" },
        { "Name": "RunTime", "Type": "CNCMacro", "Address": "2097" },
        { "Name": "CutTime", "Type": "CNCMacro", "Address": "33565" },
        { "Name": "Products", "Type": "CNCMacro", "Address": "33869" },
        { "Name": "RunStatus", "Type": "PLCRegister", "Address": "42.0" },
        { "Name": "StopStatus", "Type": "PLCRegister", "Address": "42.1" },
        { "Name": "WarnStatus", "Type": "PLCRegister", "Address": "50.14" }
      ]
    },
    {
      "DeviceId": "DHH-02",
      "SampleIntervalMs": 5000,
      "Adapter": {
        "Type": "HttpMem",
        "Endpoint": "192.168.3.22",
        "Port": 9990
      },
      "Mqtt": {
        "Broker": "192.168.0.87",
        "Port": 1883,
        "ClientId": "hanba",
        "TopicPrefix": "realtime/iot/dhh02"
      },
      "Tags": [
        { "Name": "YXMS", "Address": "R0577" },
        { "Name": "DQDL", "Address": "R0974" },
        { "Name": "FDSJH", "Address": "R1929" },
        { "Name": "FDSJF", "Address": "R1928" },
        { "Name": "KJSJH", "Address": "R1443" },
        { "Name": "KJSJF", "Address": "R1442" }
      ]
    }
  ]
}
```

---

## 10. 风险与限制

| 风险 | 影响 | 缓解 |
|---|---|---|
| Go 主网关反编译产物缺乏类型名称 | 重建时变量命名需推断 | 优先还原 handler/route，命名风格参考 echo 社区 |
| C++ SDK 私有协议规范缺失 | 自实现协议需逆向网络抓包 | 提供 Wireshark 抓包指导 + Mock 实现 |
| HslCommunication 商业功能（如部分 CNC 高级功能）需要授权 | MIT 版可能功能受限 | 仅使用 MIT 版功能 + 自实现扩展 |
| 三菱 EDM 协议无标准实现 | 自实现工作量大 | 提供协议骨架 + 测试用例 |

---

## 11. 后续步骤

1. **C4 — Core 库**：实现 ICollector / IDeviceAdapter / IDataSink / ICollectorView + Base 实现
2. **C5 — 4 个协议适配器**：FanucCnc / HttpMem / MitsubishiEdm / GoGateway
3. **C6 — Host 自宿主**：加载 appsettings.json → 注册 Collector → 启动后台循环
4. **C7 — UI 示例**：WPF 骨架，展示如何订阅 Collector 事件渲染 UI
5. **C9 — Go 主网关**：从 35.5MB 反编译产物还原 main.go + echo 路由
6. **C10 — C++ SDK 重建**（如选 路径 A 则跳过）

---

## 12. 版本规划

| 版本 | 内容 | 时间估计 |
|---|---|---|
| v0.1 | Core 接口 + MqttDataSink + 1 个示例 Collector | 半天 |
| v0.2 | 3 个 .NET Collector 重写完成 | 1-2 天 |
| v0.3 | 4 个协议适配器（基于 HslCommunication） | 2-3 天 |
| v0.4 | Go 主网关源码还原 | 3-5 天 |
| v0.5 | 完整 Host exe + WPF UI 示例 + 集成测试 | 2 天 |
| v1.0 | 用户自定义 UI 接入 + 文档完整 | 持续 |
