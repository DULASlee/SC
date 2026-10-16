# IoT 平台完整源码重建 — 设计文档

> **日期**：2026-09-17
> **状态**：等待用户审查
> **项目目录**：`F:\JQKJ\source\IoTPlatform\`

## 1. 背景与目标

### 1.1 现状

`F:\JQKJ\CNC\`、`F:\JQKJ\DHH*`、`F:\JQKJ\MZS01\` 下 9 个原始二进制已被 Ghidra 反编译（合计 12631 函数）。其中：
- **iot_CNC_PLC_IMM.exe**（35.5 MB Go 主网关）已 99.3% 反编译
- **HslCommunication.dll**（MIT 协议库）已通过 NuGet 直接集成（不再反编译）
- **v0.1**（`.NET 8` IoTPlatform 框架 5 项目）已完成并验证可工作（Host + 4 Collector + NDJSON 输出）

### 1.2 目标

将 iot_CNC_PLC_IMM.exe 从二进制重建为 **可编译运行的 Go 源码项目**（最高还原度），同时完善 .NET 端 Collector 真实协议实现，使其成为**完整可用的工业 IoT 数据采集平台源码**。

### 1.3 成功标准

| 维度 | 成功标准 |
|---|---|
| 编译 | `go build ./...` 0 警告 0 错误 |
| 启动 | `iot_CNC_PLC_IMM.exe` 成功监听 :80 |
| API | 22 个路由 + 5 个 protocol 路由 + 1 个 menu 路由全部 200/401 |
| 静态 | `/sdk/*` 返回嵌入的 SDK 文件；`/*` 返回嵌入的前端 `index.html` |
| 协议 | CNC/IMM/PLC 共 31+ 协议类可枚举（GetAllProtocols 返回非空） |
| .NET 集成 | C# GoGatewayAdapter 通过 HTTP 调用 Go 主网关成功 |
| 端到端 | Go 主网关 + 4 .NET Collector 同时运行，NDJSON 持续输出 |

## 2. 整体架构

```
┌────────────────────────────────────────────────────────────┐
│           浏览器前端 (Vue/React, embed.FS "static/")       │
│           SDK 文件 (第三方 DLL, embed.FS "sdk/")             │
└──────────────────────┬─────────────────────────────────────┘
                       │ HTTP / WebSocket
                       ▼
┌────────────────────────────────────────────────────────────┐
│  Go 主网关 iot_CNC_PLC_IMM (本项目重建目标)                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ echo v4 HTTP server (port 80, from setting.ini)       │  │
│  │ ├─ middleware: Recover, CORS, Gzip, AuthMiddleware    │  │
│  │ └─ handlers (35个)                                    │  │
│  │    ├─ AuthMiddleware                                  │  │
│  │    ├─ LoginHandler / LogoutHandler / GetUserHandler   │  │
│  │    ├─ MenuHandler (GetMenu)                           │  │
│  │    ├─ ProtocolHandler (5 routes)                       │  │
│  │    ├─ 30 个设备/网络/上传/参数 handler                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ services.DeviceManager (后台 goroutine)               │  │
│  │ ├─ 维护设备连接池 (MQTT/TCP)                           │  │
│  │ ├─ 定期 Poll 所有已注册设备                             │  │
│  │ ├─ 发送数据到 MQTT broker                              │  │
│  │ └─ 接收云端命令 (SetPara/GetVarValue)                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ protocols (31+ 协议类，统一接口)                       │  │
│  │ ├─ cnc/   (18 个: Fanuc/Mitsubishi/Brother/...)       │  │
│  │ ├─ imm/   (7 个: Changfeiya/ModbusTcp/OpcUa/...)      │  │
│  │ └─ plc/   (6 个: S7/ModbusTcp/OmronFins/Beckhoff...)  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ utils / config / interfaces / base                     │  │
│  │ ├─ INI 读写 (GetIniStr, WriteIni)                       │  │
│  │ ├─ 日志 (InitLog, LogInfo, LogDebug, LogError)        │  │
│  │ ├─ 网络诊断 (Ping, Traceroute, RouteInfo)              │  │
│  │ ├─ 编码 (GBKToUTF8, EncodeBase64, DecodeBase64)        │  │
│  │ └─ 网络配置 (ArmNetSet, Arm64NetSet, OpenWrtNetSet)   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                       ▲ MQTT/TCP
                       │
┌──────────────────────┴─────────────────────────────────────┐
│  设备层 (CNC/IMM/PLC)                                      │
│  Fanuc Focas | Mitsubishi Melsec | Brother A1E             │
│  Modbus TCP | OPC UA | S7 | Omron FINS | Beckhoff ADS      │
│  Keba | Changfeiya | JswAd/JswAds | ...                    │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  .NET 8 客户端 (F:\JQKJ\source\IoTPlatform\src\)           │
│  ├─ IoTPlatform.Core       (ICollector/IDataSink/...)      │
│  ├─ IoTPlatform.Adapters   (Fanuc/Mitsubishi/HttpMem/...)  │
│  ├─ IoTPlatform.Host       (采集器宿主, --mock --dump-json) │
│  └─ samples/IoTPlatform.UI.Wpf  (WPF UI 骨架)              │
│                                                              │
│  通过 NuGet 集成: HslCommunication 13.0.0 (MIT, 直接使用)   │
│  通过 HTTP 调用: GoGatewayAdapter → Go 主网关                │
└────────────────────────────────────────────────────────────┘
```

## 3. Go 主网关源码项目结构

```
F:\JQKJ\source\IoTPlatform-GoGateway\
├── go.mod                              # 模块名 elinksio/iot-platform
├── go.sum
├── main.go                             # 入口：启动 echo，注册所有路由
├── README.md
├── Dockerfile                          # 多阶段构建
├── docker-compose.yml                  # + MQTT broker (Mosquitto)
├── embed.go                            //go:embed static sdk
├── static/                             # 前端 SPA (Vue/React 简化版)
│   ├── index.html
│   └── assets/
├── sdk/                                # 第三方 SDK 占位
│   └── README.md
├── internal/
│   ├── base/
│   │   └── base.go                     # DeviceBase (Run/Stop/DataShow)
│   ├── config/
│   │   └── config.go                   # VersionInit, Version 变量
│   ├── interfaces/
│   │   └── device.go                   # IDevice 接口 (16 methods)
│   ├── services/
│   │   ├── device_manager.go           # DeviceManager (goroutine)
│   │   ├── protocol_generator.go       # 协议生成器 (GetAllProtocols)
│   │   └── mqtt_publisher.go           # MQTT 上报
│   ├── protocols/
│   │   ├── cnc/                        # 18 个 CNC 类
│   │   │   ├── cnc_common.go           # GeneratePositionCommand
│   │   │   ├── mach_fanuc_cnc.go       # MachFanucCNC
│   │   │   ├── mach_mitsubishi_cnc.go  # MachMitsubishiCNC
│   │   │   ├── mach_brother_cnc.go     # MachBrotherCNC
│   │   │   ├── mach_dafeng_cnc.go      # MachDafengCnc
│   │   │   ├── mach_gsk_tcp_cnc.go     # MachGskTcpCNC
│   │   │   ├── mach_haas_cnc.go        # MachHaasCNC
│   │   │   ├── mach_haidehan530.go     # MachHaidehan530
│   │   │   ├── mach_haidehan620.go     # MachHaidehan620
│   │   │   ├── mach_knd_cnc.go         # MachKndCNC
│   │   │   ├── mach_matrix640_cnc.go   # MachMatrix640CNC
│   │   │   ├── mach_mazak_smart_cnc.go # MachMazakSmartCNC
│   │   │   ├── mach_mazak_smooth_cnc.go# MachMazakSmoothCNC
│   │   │   ├── mach_simens_cnc.go      # MachSimensCNC
│   │   │   ├── mach_syntec118.go       # MachSyntec118
│   │   │   ├── mach_syntec_v2.go       # MachSyntecV2
│   │   │   ├── mach_syntec_v3.go       # MachSyntecV3
│   │   │   ├── mach_syntec_v4.go       # MachSyntecV4
│   │   │   └── mach_xtc_cnc.go         # MachXtcCNC
│   │   ├── imm/                        # 7 个 IMM 类
│   │   │   ├── mach_changfeiya.go
│   │   │   ├── mach_jsw_ad.go
│   │   │   ├── mach_jsw_ads.go
│   │   │   ├── mach_keba.go
│   │   │   ├── mach_modbus_tcp.go
│   │   │   ├── mach_opc_ua.go
│   │   │   └── mach_socket.go
│   │   └── plc/                        # 6 个 PLC 类
│   │       ├── beckhoff_ads_net.go
│   │       ├── mach_melsec_udp.go
│   │       ├── mach_modbus_tcp.go
│   │       ├── mach_omron_fins.go
│   │       ├── mach_opc_ua.go
│   │       └── mach_s7.go
│   ├── utils/
│   │   ├── ini.go                      # GetIniStr, WriteIni, GetIniInt
│   │   ├── log.go                      # InitLog, LogInfo, LogDebug, LogError
│   │   ├── network.go                  # Ping, Traceroute, RouteInfo
│   │   ├── netset.go                   # ArmNetSet/Arm64NetSet/OpenWrtNetSet
│   │   ├── encoding.go                 # GBKToUTF8, EncodeBase64, DecodeBase64
│   │   ├── shell.go                    # ExecuteShellCommand
│   │   ├── gateway.go                  # GetDefaultGateway
│   │   └── copy.go                     # CopyFile
│   └── handlers/
│       ├── auth.go                     # AuthMiddleware
│       ├── login.go                    # LoginHandler
│       ├── logout.go                   # LogoutHandler
│       ├── user.go                     # GetUserHandler
│       ├── token.go                    # cleanExpiredTokens, encryptString
│       ├── menu.go                     # NewMenuHandler, GetMenu
│       ├── protocol.go                 # ProtocolHandler + 5 routes
│       ├── upload.go                   # UploadHandler, UploadChunkHandler, ...
│       ├── download.go                 # CfgDownloadHandler, createTarGz
│       ├── device.go                   # GetDeviceInfoHandler, GetDeviceStatusHandler, ...
│       ├── var_value.go                # GetVarValueHandler, GetCmdResHandler
│       ├── parameter.go                # GetParaHandler, SetParaHandler, ...
│       ├── log.go                      # GetLogHandler
│       ├── network.go                  # PingHandler, TracerouteHandler, ...
│       ├── system.go                   # RebootHandler, SystemRebootHandler
│       ├── version.go                  # VersionString
│       └── csv.go                      # processCSVContent, removeBOM
└── setting.ini                          # 运行时由 GetIniStr/WriteIni 维护
```

## 4. 核心接口与数据流

### 4.1 IDevice 接口（`internal/interfaces/device.go`）

从 31 个协议类的统一方法集抽取：

```go
type IDevice interface {
    // 生命周期
    Run(ctx context.Context) error
    IsOnline() bool
    SetOnline(bool)
    SetStart(bool)
    GetStart() bool

    // MQTT 标识
    SetMQTTDeviceID(string)

    // 网络参数
    SetIP(string); GetIP() string
    SetPort(int)

    // 协议
    SetProtocol(string); SetSubType(string)

    // 数据采集
    GetRawData(ctx context.Context) (map[string]any, error)
    GetVarData(ctx context.Context, varNames []string) (map[string]any, error)
    DataShow() map[string]any

    // 消息队列
    SendMsgToQueue(map[string]any)
    SetCfgUpdate(map[string]any)
}
```

### 4.2 ProtocolHandler 数据流

```
浏览器 POST /api/protocol/all
  └─ handlers.ProtocolHandler.GetAllProtocols(c)
       └─ services.ProtocolGenerator.GenerateAll()
            └─ protocols/cnc + imm + plc 列出所有支持类型
                 返回 JSON: {cnc:[...18], imm:[...7], plc:[...6]}
```

### 4.3 MenuHandler 数据流

```
浏览器 POST /api/menu
  └─ handlers.MenuHandler.GetMenu(c)  [需 AuthMiddleware]
       返回 JSON: {menu:[设备/参数/网络/上传/系统/日志 6 个一级菜单]}
```

### 4.4 main.main 启动序列（从反编译还原）

```go
func main() {
    // 1. 日志初始化
    utils.InitLog(...)
    utils.LogInfo("iot_CNC_PLC_IMM starting...")

    // 2. 版本初始化 + 写 ini
    config.VersionInit()
    v := handlers.VersionString()
    fmt.Println(v)
    utils.WriteIni("setting", "setting", "appVersion", v)

    // 3. 加载 embed.FS
    frontendFS, err := main_getFrontendFS()
    sdkFS, err := main_getSDKFS()
    if sdkFS == nil { log.Warn("...") }

    // 4. 启动设备管理 goroutine
    dm := services.StartDeviceManager()
    go dm.Run()
    time.Sleep(3 * time.Second)
    dm.PrintStatus()

    // 5. 创建 echo 实例 + 中间件
    e := echo.New()
    e.Use(middleware.RecoverWithConfig(middleware.DefaultRecoverConfig))
    e.Use(middleware.CORSWithConfig(middleware.CORSConfig{
        AllowOrigins: []string{"*"},
        AllowMethods: []string{"GET", "POST", "PUT", "DELETE"},
        AllowHeaders: []string{"Origin", "Content-Type", "X-Requested-With", "Authorization"},
    }))

    // 6. 静态文件
    if sdkFS != nil {
        e.GET("/sdk/*", echo.WrapHandler(http.StripPrefix("/sdk/", http.FileServer(http.FS(sdkFS)))))
    }
    // ./static 优先，否则用 embed.FS
    var frontendFSActual fs.FS
    if _, err := os.Stat("./static"); err == nil {
        frontendFSActual = os.DirFS("./static")
    } else {
        frontendFSActual = frontendFS
    }
    e.GET("/*", echo.WrapHandler(http.StripPrefix("/", http.FileServer(http.FS(frontendFSActual)))))
    e.Use(middleware.Gzip())

    // 7. 注册路由
    // 7a. 5 个 protocol 路由 (无需 Auth)
    ph := handlers.NewProtocolHandler(services.NewProtocolGenerator())
    e.POST("/api/protocol/options",    ph.GetProtocolOptions)
    e.POST("/api/protocol/metadata",    ph.GetProtocolMetadata)
    e.POST("/api/protocol/subtypes",    ph.GetProtocolSubTypes)
    e.POST("/api/protocol/subtype",     ph.GetProtocolSubType)
    e.POST("/api/protocol/all",         ph.GetAllProtocols)

    // 7b. menu (需 Auth)
    mh := handlers.NewMenuHandler()
    e.POST("/api/menu", mh.GetMenu, handlers.AuthMiddleware)

    // 7c. 21 个其他路由 (需 Auth)
    e.POST("/api/login",            handlers.LoginHandler)
    e.POST("/api/logout",           handlers.LogoutHandler, handlers.AuthMiddleware)
    e.POST("/api/getUser",          handlers.GetUserHandler, handlers.AuthMiddleware)
    e.POST("/api/getDeviceInfo",    handlers.GetDeviceInfoHandler, handlers.AuthMiddleware)
    e.POST("/api/getDeviceStatus",  handlers.GetDeviceStatusHandler, handlers.AuthMiddleware)
    e.POST("/api/rebootDevice",     handlers.RebootDeviceHandler, handlers.AuthMiddleware)
    e.POST("/api/reboot",           handlers.RebootHandler, handlers.AuthMiddleware)
    e.POST("/api/systemReboot",     handlers.SystemRebootHandler, handlers.AuthMiddleware)
    e.POST("/api/getVarValue",      handlers.GetVarValueHandler, handlers.AuthMiddleware)
    e.POST("/api/getPara",          handlers.GetParaHandler, handlers.AuthMiddleware)
    e.POST("/api/setPara",          handlers.SetParaHandler, handlers.AuthMiddleware)
    e.POST("/api/setBasePara",      handlers.SetBaseParaHandler, handlers.AuthMiddleware)
    e.POST("/api/setDeviceBasePara",handlers.SetDeviceBaseParaHandler, handlers.AuthMiddleware)
    e.POST("/api/paraDelete",       handlers.ParaDeleteHandler, handlers.AuthMiddleware)
    e.POST("/api/getZhuYouRaw",     handlers.GetZhuYouRawHandler, handlers.AuthMiddleware)
    e.POST("/api/getCmdRes",        handlers.GetCmdResHandler, handlers.AuthMiddleware)
    e.POST("/api/paraUpload",       handlers.ParaUpload, handlers.AuthMiddleware)
    e.POST("/api/upload",           handlers.UploadHandler, handlers.AuthMiddleware)
    e.POST("/api/startChunkUpload", handlers.StartChunkUploadHandler, handlers.AuthMiddleware)
    e.POST("/api/uploadChunk",      handlers.UploadChunkHandler, handlers.AuthMiddleware)
    e.POST("/api/mergeChunks",      handlers.MergeChunksHandler, handlers.AuthMiddleware)
    e.POST("/api/cfgDownload",      handlers.CfgDownloadHandler, handlers.AuthMiddleware)
    e.POST("/api/getLog",           handlers.GetLogHandler, handlers.AuthMiddleware)
    e.POST("/api/getMQTTMessageHistory", handlers.GetMQTTMessageHistory, handlers.AuthMiddleware)
    e.POST("/api/getNetworkStatus",   handlers.GetNetworkStatusHandler, handlers.AuthMiddleware)
    e.POST("/api/getNetworkConfig",  handlers.GetNetworkConfigHandler, handlers.AuthMiddleware)
    e.POST("/api/setNetworkConfig",  handlers.SetNetworkConfigHandler, handlers.AuthMiddleware)
    e.POST("/api/getNetworkInterfaces", handlers.GetNetworkInterfacesHandler, handlers.AuthMiddleware)
    e.POST("/api/testNetworkConnectivity", handlers.TestNetworkConnectivityHandler, handlers.AuthMiddleware)
    e.POST("/api/restartNetwork",    handlers.RestartNetworkHandler, handlers.AuthMiddleware)
    e.POST("/api/ping",              handlers.PingHandler, handlers.AuthMiddleware)
    e.POST("/api/traceroute",        handlers.TracerouteHandler, handlers.AuthMiddleware)
    e.POST("/api/routeInfo",         handlers.RouteInfoHandler, handlers.AuthMiddleware)

    // 8. 读取 ini port + 启动
    port := utils.GetIniStr("setting", "setting", "port", "80")
    utils.WriteIni("setting", "setting", "port", port)
    if err := e.Start(":" + port); err != nil {
        e.Logger.Fatal(err)
    }
}
```

## 5. .NET 端 HslCommunication 集成

按用户明确要求，**HslCommunication 不反编译为源码**，直接 NuGet 集成：

| .NET 项目 | HslCommunication 用法 | 替代目标 |
|---|---|---|
| FanucCncAdapter | `FanucSeries0i` (v13 缺失) → **TcpClient 自实现 Focas 协议帧** | v0.1 已 Mock，可选真实化 |
| MitsubishiEdmAdapter | `MelsecA1EAsciiNet.ReadFromAddress` | v0.1 已 Mock，可选真实化 |
| HttpMemAdapter | `HslCommunication.WebSocket` 或裸 HttpClient | 已用 HttpClient，可选升级 WS |
| GoGatewayAdapter | (无) → HTTP 调用 Go 主网关 `/api/protocol/all` 等 | 已实现 |

**真实化策略**：
- v0.1 MockMode=true 可立即运行（已完成）
- v0.2 增加 `RealProtocol` 静态开关，配置文件中 `MockMode: false` 时切到 HslCommunication 真实调用
- 通过 Wireshark 抓包验证协议细节后再切真实模式（避免 HslCommunication 版本不匹配导致错误）

## 6. 测试矩阵

| 层级 | 工具 | 覆盖 |
|---|---|---|
| Go 单元测试 | `go test ./...` | interfaces, utils, config, base |
| Go 集成测试 | `go test -tags=integration` | handlers (Echo httptest), ProtocolGenerator |
| .NET 单元测试 | `dotnet test` | BaseCollector 状态机, Adapter Mock |
| .NET 集成测试 | 自定义 | Host 启动 + Mock 设备接入 |
| 端到端 | 手动 + NDJSON 检查 | Go :80 + .NET Collector → MQTT broker → 文件 |

## 7. 交付物

| 文件 | 说明 |
|---|---|
| `F:\JQKJ\source\IoTPlatform-GoGateway\` | 完整 Go 源码（31+ 协议类，35+ handler） |
| `F:\JQKJ\source\IoTPlatform-GoGateway\iot_CNC_PLC_IMM.exe` | `go build` 产物（跨平台：windows/amd64, linux/amd64, linux/arm64） |
| `F:\JQKJ\source\IoTPlatform\src\` (v0.2) | .NET 8 真实协议接入层 |
| `F:\JQKJ\source\IoTPlatform-GoGateway\Dockerfile` | 多阶段构建 |
| `F:\JQKJ\source\IoTPlatform-GoGateway\docker-compose.yml` | Go + Mosquitto |
| `F:\JQKJ\docs\superpowers\plans\2026-09-17-c9-go-gateway-rebuild.md` | 实施计划 |
| `F:\JQKJ\docs\superpowers\reports\2026-09-17-c9-deliverable.md` | 六要素交付报告 |

## 8. 时间估算（5-10 天）

| Day | 任务 | 工时 |
|---|---|---|
| **Day 1** | Go 项目骨架 + go.mod + main.go 启动序列 + embed.FS | 4h |
| **Day 2** | utils 全部 (ini/log/network/netset/encoding/shell/copy) | 6h |
| **Day 3** | interfaces.IDevice + base.DeviceBase + services.DeviceManager | 6h |
| **Day 4** | handlers 35 个 (AuthMiddleware + 9 类) | 8h |
| **Day 5** | protocols/cnc 18 类 (Focas/Melsec/A1E 真实帧格式) | 8h |
| **Day 6** | protocols/imm 7 类 + protocols/plc 6 类 | 6h |
| **Day 7** | .NET FanucCncAdapter + MitsubishiEdmAdapter 真实化 (HslCommunication) | 6h |
| **Day 8** | 集成测试 + Docker + 文档 | 6h |
| **Day 9-10** | 缓冲 + Bug 修复 + Wireshark 抓包验证（如果需要） | 8h |

**总计：~58h ≈ 7-8 个工作日**

## 9. 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| Go 版本 | 1.24 | 与原二进制版本匹配 |
| HTTP 框架 | echo v4 | 原二进制已用 |
| MQTT broker | Mosquitto (Docker) | 行业标准，docker-compose 一键起 |
| 日志库 | logrus 或 zap | 原二进制用 `log.Logger`，可保持 |
| INI 库 | `gopkg.in/ini.v1` 或 `github.com/go-ini/ini` | 原二进制用类似库 |
| 第三方协议库 | 不引入 | **完全自实现**，原二进制就是自实现的 |
| HslCommunication | NuGet 13.0.0 | 用户明确指定，MIT 开源直接用 |
| 嵌入资源 | `embed.FS` | 原二进制用 `go:embed` 等价 |

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 反编译产物中协议帧格式不可读 | 协议类实现有误差 | Wireshark 抓真实流量比对 |
| Go 版本与原二进制不匹配 | 编译错误 | 用 Go 1.24.5 + echo v4.10+ |
| 18 个 CNC 类工作量巨大 | 超过 5 天 | **优先级：Fanuc + Mitsubishi + Brother + Modbus TCP** 先做，其余用 placeholder 框架 |
| 设备未在现场 | 无法端到端验证 | 用 MockMode 双轨：本地 mock + 可切换真实协议 |
| 工控协议私有（OEM 私有） | 无法 100% 还原 | 按反编译结果近似实现，标注"基于反编译产物推断" |

## 11. 已确认的设计选择

- ✅ **C9 完整重建**（用户 5-10 天决定）
- ✅ **HslCommunication NuGet 集成**（不反编译为源码）
- ✅ **所有采集器和主程序都是可用源码**（用户）
- ✅ **v0.1 已可工作**（Host + 4 Collector + NDJSON）
- ✅ **Go 主网关跨平台**（windows/amd64, linux/amd64, linux/arm64）

## 12. 用户最终决策（2026-09-17）

| # | 问题 | 决策 |
|---|---|---|
| 1 | 协议实现深度 | **A — 全部 31+ 协议做真实实现** |
| 2 | .NET FanucCncAdapter 真实化 | **X — 切真实模式**（不依赖 MockMode 双轨） |
| 3 | MQTT broker | **E — EMQX**（完整功能，含 Dashboard/规则引擎/多协议网关） |
| 4 | Wireshark 抓包 | **N — 否**（按反编译产物 + 协议标准文档独立推断） |

### 12.1 决策含义

- **A 全部协议**：31+ 个协议类全部真实实现，不做"统一框架占位"
- **X .NET 真实模式**：v0.1 的 MockMode 框架保留为开发/测试辅助，但交付时 FanucCncAdapter / MitsubishiEdmAdapter / HttpMemAdapter / GoGatewayAdapter 全部走真实协议路径（HslCommunication / HTTP Client）
- **EMQX**：用 `emqx/emqx:5.x` Docker 镜像，启用 Dashboard（18083）+ MQTT（1883）+ WebSocket（8083）+ 管理 API（8081）
- **不抓包**：协议帧格式按以下来源推断（优先级从高到低）：
  1. 反编译产物中的常量字符串（命令名/字段名/格式）
  2. 通用工业协议标准（Modbus TCP、OPC UA、S7、Melsec、Omron FINS 等均有公开规范）
  3. HslCommunication 已实现版本的字节序（NuGet 13.0.0 源码可读）
  4. Ghidra 反编译产物中的结构体布局
  推断结果在每协议类顶部 `// IMPLEMENTATION_NOTES` 标注来源

### 12.2 同步更新的章节

- §1.2 目标：明确"31+ 协议全部真实实现 + EMQX + .NET 真实协议接入"
- §3 项目结构：保持不变（文件清单按 A 选项全量）
- §5 HslCommunication 集成：X 选项下 "MockMode 双轨" → "保留 MockMode 为开发辅助 + 真实模式为交付"
- §6 测试矩阵：增加"EMQX 容器化集成测试"
- §8 时间估算：不变（A 选项已对应 7-8 天工作量）
- §9 关键决策：MQTT broker Mosquitto → **EMQX**
- §10 风险与缓解："18 个 CNC 类工作量巨大" 缓解 → "完整 31+ 协议实现，统一 framework 抽取"（无 placeholder）

---

**用户决策已确定，进入实施阶段。下一步 invoke writing-plans skill 创建详细实施计划。**