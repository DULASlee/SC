# 工业数据采集与数字孪生平台设计方案

> **日期**: 2026-09-17
> **版本**: v1.0
> **状态**: 待审批

---

## 一、背景与目标

### 1.1 现有资产

| 系统 | 描述 | 成熟度 |
|---|---|---|
| **GenCollector** | 经过商业验证的采集引擎（三菱 CNC RemoteComm.dll、Modbus/S7/Omron/三菱 PLC），配置驱动 + 协议可插拔架构，MQTT 上报 | ✅ 商业验证 |
| **GenDashboard** | .NET 8 WinForms 看卡（MQTT 订阅 + DataGridView + 地址码对照）| ⚠️ 基础框架 |
| **twin-data-collector** | GitHub 完整开源，C# WinForms，43 个驱动源码，完整 UI（MainForm/DeviceConfigForm/DatabaseConfigForm），MCP AI | ⚠️ 2 个月，无商业验证 |
| **brand_address_map.md** | 原始 Go 二进制反编译提取的 fanuc/mitsubishi/simens 品牌 addrCode 映射表 | ✅ 可用 |

### 1.2 核心问题

1. **无 UI**：GenCollector 无配置界面，设备/变量全靠手工 INI 文件管理
2. **无持久化**：数据只到 MQTT，没有本地时序存储
3. **重连机制缺失**：MQTT/驱动断线不自动重连
4. **8 个 CNC 品牌无驱动**：fanuc/simens/haidehan/gsk/syntec/brother/knd/mazak 仅有 SimDriver 模拟
5. **WinForms 无法跨平台**：.NET Framework 4.8 依赖 Windows

### 1.3 目标

构建一个**生产级工业数据采集与数字孪生平台**：

```
阶段目标：
Phase 0: 配置体系迁移（INI → JSON，50 代备份）
Phase 1: 采集引擎健壮性（MQTT 重连、驱动断线重连）
Phase 2: 跨平台客户端（Avalonia UI + gRPC API Gateway）
Phase 3: Eclipse Ditto 集成（语义孪生、Thing 模型）
Phase 4: Apache IoTDB 集成（时序持久化、分析查询）
Phase 5: 安灯系统（告警规则引擎 + 产线灯号看板 + REST API）
Phase 6: 补全 CNC 驱动（Fanuc/Siemens CNC/Mazak/Heidenhain/Haas）
```

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           跨平台客户端 (Avalonia UI)                         │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────────────────────┐  │
│  │  GenDashboard │  │   安灯看板     │  │  设备/变量配置 (改造自 twin)  │  │
│  │  (实时数据)    │  │ (产线灯号 A 方案)│  │  四级组织架构 + CSV 导入      │  │
│  └───────┬───────┘  └───────┬────────┘  └───────────────────────────────┘  │
│          │                  │                                                   │
│          └──────────────────┼───────────────────────────────────────────────┘
│                             │ gRPC
┌─────────────────────────────▼─────────────────────────────────────────────────┐
│                    API Gateway (.NET 8 gRPC/REST)                             │
│         ┌──────────────────────────────────────────────────────────────┐      │
│         │  gRPC: 设备 CRUD / 实时数据订阅 / 历史查询 / 告警状态         │      │
│         │  REST: 第三方集成（MES/ERP） / WebHook                       │      │
│         └──────────────────────────────────────────────────────────────┘      │
└────────────────────────────┬────────────────────┬────────────────────────────┘
                             │ gRPC               │ MQTT
┌────────────────────────────▼──────┐  ┌──────────▼───────────────────────────┐
│         Eclipse Ditto             │  │           安灯服务                    │
│         (语义孪生层)               │  │  (告警规则 + 响应流程 + 统计)          │
│  Thing: 公司→车间→工序→设备       │  │  - 阈值规则 (HH/H/L/LL)               │
│  Feature: 实时状态/告警/配置       │  │  - 告警确认/恢复流程                   │
│  Command: 读变量/写变量/重启采集   │  │  - SLA 超时升级                       │
│  Event:  告警事件/状态变化         │  │  - REST API (第三方集成)              │
└──────────────┬────────────────────┘  └──────────┬───────────────────────────┘
               │                                    │
               │ MQTT                               │ MQTT
┌──────────────▼────────────────────┐  ┌───────────▼───────────────────────────┐
│         Apache IoTDB              │  │         GenCollector                   │
│         (时序存储+分析层)          │  │         (采集引擎)                     │
│  TsFile 边缘存储                  │  │  三菱CNC RemoteComm.dll                │
│  降采样/聚合/趋势分析             │  │  Fanuc / Siemens CNC (补全)            │
│  Flink/Spark 离线分析接口         │  │  Modbus / S7 / Omron / 三菱PLC         │
│  云端同步 (MQTT Bridge)           │  │  IDeviceDriver 接口可插拔              │
└──────────────────────────────────┘  └──────────────────────────────────────┘
```

### 2.2 数据流

```
设备 (CNC/PLC)
    │
    │ 驱动协议 (Fanuc FOCAS / Mitsubishi MC / S7 / Modbus...)
    ▼
GenCollector (采集引擎, .NET 8 console, 跨平台)
    │
    ├─→ MQTT Broker ─→ Eclipse Ditto ─→ Thing 模型 ─→ gRPC ─→ Avalonia UI
    │
    └─→ MQTT Broker ─→ 安灯服务 ─→ 告警规则引擎 ─→ 看板 + REST API
    │
    └─→ MQTT Broker ─→ Apache IoTDB (本地 TsFile)
                              │
                              ▼
                        趋势分析/聚合查询
                        (Flink/Spark)
```

### 2.3 组件职责

| 组件 | 技术栈 | 部署方式 | 职责 |
|---|---|---|---|
| **GenCollector** | .NET 8 Console | Windows/Linux 独立进程 | 唯一数据接入层，MQTT 上报 |
| **Eclipse Ditto** | Java 17, Docker | K3S Pod | 语义孪生建模，设备状态管理，Thing/Feature/Command |
| **Apache IoTDB** | Java, Docker | K3S Pod | 时序数据持久化，降采样，聚合分析 |
| **安灯服务** | Java 17 / Spring Boot, Docker | K3S Pod | 告警规则引擎，响应流程，SLA 管理 |
| **API Gateway** | .NET 8, gRPC + REST | K3S Pod 或 Windows/Linux | 客户端通信，第三方集成 |
| **Avalonia UI** | .NET 8, Avalonia UI 11 | Windows/macOS/Linux | 跨平台客户端 UI |

---

## 三、配置体系设计（Phase 0）

### 3.1 设计原则

- **INI → JSON 迁移**：将现有 `setting.ini` / `device_*.ini` / `var_info_*.ini` / `var_group_*.ini` 迁移到 JSON Schema
- **50 代备份**：每次保存自动备份，保留最近 50 代
- **向后兼容**：过渡期支持 INI 和 JSON 双读
- **Schema 校验**：JSON Schema 验证，配置错误提前暴露

### 3.2 JSON 配置结构

```json
// config.json - 主配置
{
  "version": "1.0",
  "appId": "gen-collector-01",
  "mqtt": {
    "server": "tcp://broker.example.com:1883",
    "prefix": "/YLCY/CNC/",
    "qos": 0,
    "reconnect": {
      "enabled": true,
      "initialDelayMs": 1000,
      "maxDelayMs": 60000,
      "multiplier": 2.0
    }
  },
  "simulate": false,
  "port": 8080,
  "authCode": "",
  "database": {
    "enabled": true,
    "type": "iotdb",
    "iotdb": {
      "host": "iotdb.internal",
      "port": 6667,
      "username": "root",
      "password": "root"
    }
  },
  "ditto": {
    "enabled": true,
    "endpoint": "http://ditto.internal:8080",
    "namespace": "org.gencore"
  },
  "andons": [
    {
      "id": "line-01",
      "name": "1号产线",
      "devices": ["cnc-01", "cnc-02"]
    }
  ]
}
```

```json
// devices.json - 设备配置
{
  "devices": [
    {
      "id": "cnc-01",
      "name": "CNC-01 加工中心",
      "protocol": "mitsubishi_cnc",
      "protocolFamily": "mitsubishi_cnc",
      "ip": "192.168.1.10",
      "port": "",
      "mqttDeviceId": "CNC01",
      "enabled": true,
      "varGroup": "realtime",
      "company": "总公司",
      "workshop": "一车间",
      "process": "加工工序"
    },
    {
      "id": "plc-01",
      "name": "PLC-01 注塑机",
      "protocol": "modbus",
      "protocolFamily": "modbus",
      "ip": "192.168.1.20",
      "port": "502",
      "mqttDeviceId": "PLC01",
      "enabled": true,
      "varGroup": "realtime",
      "company": "总公司",
      "workshop": "一车间",
      "process": "注塑工序"
    }
  ]
}
```

```json
// var_infos.json - 变量配置
{
  "mitsubishi_cnc": [
    {
      "id": "spindleSpeed",
      "remark": "主轴转速",
      "addr": "33868",
      "readType": "macro",
      "group": "realtime",
      "enabled": true,
      "alarm": {
        "hh": 5000,
        "h": 4500,
        "l": 100,
        "ll": 50,
        "unit": "RPM"
      }
    },
    {
      "id": "statusOrg",
      "remark": "运行状态",
      "addr": "42.0",
      "readType": "plc",
      "group": "realtime",
      "enabled": true
    }
  ],
  "fanuc_cnc": [...],
  "siemens_cnc": [...]
}
```

```json
// var_groups.json - 变量组
{
  "groups": [
    {
      "id": "realtime",
      "name": "实时数据",
      "timer": 20,
      "enabled": true
    },
    {
      "id": "alarm",
      "name": "告警数据",
      "timer": 5,
      "enabled": true
    }
  ]
}
```

---

## 四、采集引擎健壮性（Phase 1）

### 4.1 MQTT 重连机制

采用**指数退避重连**：

```
初始延迟: 1s → 2s → 4s → 8s → 16s → 32s → 60s (最大)
触发条件: 连接断开 / 发布失败
恢复后: 立即重置延迟为 1s
```

### 4.2 驱动断线重连

每设备线程独立，遇到驱动异常时：
1. 记录错误日志
2. 调用 `driver.Disconnect()`
3. 等待 10s 后重新 `driver.Connect()`
4. 最大重试 10 次，超过后告警上报

### 4.3 离线缓存

当 MQTT 断开时，将数据写入本地缓冲文件：
- 格式: `{timestamp}\t{topic}\t{json_payload}\n`
- 大小限制: 100MB，超过则丢弃最旧数据
- 恢复后自动补发

---

## 五、跨平台客户端（Phase 2）

### 5.1 技术选型：Avalonia UI 11

| 对比 | WinForms (.NET 4.8) | Avalonia UI (.NET 8) |
|---|---|---|
| 跨平台 | ❌ Windows only | ✅ Win/macOS/Linux |
| 部署 | 单机 | 跨平台 |
| 生态 | 成熟 | 成熟 (.NET 生态完整) |
| 学习曲线 | 低 | 中（XAML 类似 WPF）|
| 实时数据 | MVVMI 异步绑定 | ReactiveUI 响应式 |

### 5.2 页面结构

```
┌────────────────────────────────────────────────────────────────┐
│  [logo] 工业数据平台          [连接状态]  [用户名] [设置] [退出] │
├────────────┬───────────────────────────────────────────────────┤
│            │                                                    │
│  ◉ 实时数据│   ┌─────────────────────────────────────────────┐ │
│  ◉ 设备管理│   │         DataGridView (变量实时值)            │ │
│  ◉ 变量配置│   │                                             │ │
│  ◉ 安灯看板│   │  变量名 | 当前值 | 单位 | 状态 | 更新时间    │ │
│  ◉ 告警记录│   └─────────────────────────────────────────────┘ │
│  ◉ 历史趋势│                                                    │
│  ◉ 系统设置│   ┌─────────────────────────────────────────────┐ │
│            │   │         趋势图 (LiveCharts)                  │ │
│            │   └─────────────────────────────────────────────┘ │
└────────────┴───────────────────────────────────────────────────┘
```

### 5.3 参考 twin-data-collector 的实现

| twin-data-collector 源码 | 移植到 Avalonia UI |
|---|---|
| `Forms/MainForm.cs` | `MainWindow.axaml` |
| `Forms/MainForm.DeviceTree.cs` | `DeviceTreeView.axaml` (四级组织架构) |
| `Forms/DeviceConfigForm.cs` | `DeviceConfigView.axaml` |
| `Forms/DatabaseConfigForm.cs` | `DatabaseConfigView.axaml` |
| `Forms/MqttConfigForm.cs` | `MqttConfigView.axaml` |
| `Forms/McpConfigForm.cs` | `McpConfigView.axaml` |
| `Services/DataCollectionService.cs` | gRPC 服务端，复用逻辑 |
| `Services/DatabaseWriteService.cs` | `DatabaseWriteService` 移植 |
| `Services/MqttPublishService.cs` | 作为 gRPC 服务端 |
| `Models/DeviceConfig.cs` | 直接引用 |
| `Models/DataPoint.cs` | 直接引用 |

---

## 六、语义孪生（Phase 3）

### 6.1 Eclipse Ditto 集成

Eclipse Ditto 的 Thing 模型与 GenCollector 的四级组织架构映射：

```
Ditto Thing ID: org.gencore:cnc-01
└── Attributes:
      company: "总公司"
      workshop: "一车间"
      process: "加工工序"
      ip: "192.168.1.10"
      protocol: "mitsubishi_cnc"
└── Features:
      realtime:
        properties:
          spindleSpeed: { value: 3500, unit: "RPM", timestamp: 1234567890 }
          spindleLoad: { value: 75, unit: "%", timestamp: 1234567890 }
          feedRate: { value: 1200, unit: "mm/min", timestamp: 1234567890 }
      alarms:
        properties:
          status: "normal" | "warning" | "critical"
          activeAlarms: [...]
          lastAlarmTime: 1234567890
      config:
        properties:
          varGroup: "realtime"
          mqttDeviceId: "CNC01"
```

### 6.2 gRPC 接口设计

```protobuf
service CollectorGateway {
  // 设备管理
  rpc ListDevices(ListDevicesRequest) returns (ListDevicesResponse);
  rpc GetDevice(GetDeviceRequest) returns (Device);
  rpc CreateDevice(CreateDeviceRequest) returns (Device);
  rpc UpdateDevice(UpdateDeviceRequest) returns (Device);
  rpc DeleteDevice(DeleteDeviceRequest) returns (google.protobuf.Empty);

  // 实时数据订阅
  rpc SubscribeRealtimeData(SubscribeRequest) returns (stream DataPoint);

  // 历史数据查询
  rpc QueryHistory(QueryHistoryRequest) returns (QueryHistoryResponse);

  // 告警管理
  rpc ListAlarms(ListAlarmsRequest) returns (ListAlarmsResponse);
  rpc AcknowledgeAlarm(AckRequest) returns (Alarm);
  rpc ResolveAlarm(ResolveRequest) returns (Alarm);

  // 安灯状态
  rpc GetAndonStatus(google.protobuf.Empty) returns (AndonStatusResponse);
}
```

---

## 七、时序存储（Phase 4）

### 7.1 Apache IoTDB 集成

```
GenCollector ──MQTT──→ IoTDB (本地 TsFile)
                         │
                         ├─→ 趋势聚合查询 (UDF)
                         ├─→ 降采样存储 (Flume/Spark)
                         └─→ 云端同步 (MQTT Bridge)
```

### 7.2 存储策略

| 数据类型 | 保留策略 | 压缩 |
|---|---|---|
| 原始数据 (1s 精度) | 7 天 | TsFile 列式压缩 |
| 5s 降采样 | 30 天 | 高压缩 |
| 1min 降采样 | 1 年 | 高压缩 |
| 告警事件 | 永久 | 标准 |

---

## 八、安灯系统（Phase 5）

### 8.1 告警规则引擎

```java
// 规则示例：主轴过载告警
Rule {
  id: "spindle_overload",
  deviceFilter: "protocol == 'mitsubishi_cnc'",
  condition: "spindleLoad > 90",
  severity: "critical",  // critical / warning / info
  andonPattern: "red",   // 红灯
  slaMinutes: 5,         // 5分钟未处理则升级
  notifyTargets: ["车间主管", "设备工程师"]
}
```

### 8.2 产线灯号看板（A 方案）

```
┌──────────────────────────────────────────────────────────────────┐
│                      1号产线  安灯看板                    09:23:15 │
├──────────────────────────────────────────────────────────────────┤
│  设备        状态    告警信息                    持续时间          │
│  ──────────────────────────────────────────────────────────────  │
│  CNC-01     🟢 运行   -                            -             │
│  CNC-02     🔴 告警   主轴过载 (87℃>80℃)          00:03:22       │
│  CNC-03     🟡 待机   运行超时 (45min)             00:12:05       │
│  PLC-01     🟢 运行   -                            -             │
├──────────────────────────────────────────────────────────────────┤
│  [告警历史] [统计报表] [系统设置]                                   │
└──────────────────────────────────────────────────────────────────┘
```

状态灯规则：
- 🟢 绿色：正常运行，无活跃告警
- 🟡 黄色：警告级告警（阈值 H/L、运行超时）
- 🔴 红色：严重告警（阈值 HH/LL、设备断线）

### 8.3 REST API（第三方集成）

```
GET  /api/v1/andon/status              # 全厂安灯状态
GET  /api/v1/andon/devices/{id}        # 单设备告警详情
GET  /api/v1/alarms?status=active      # 活跃告警列表
POST /api/v1/alarms/{id}/ack           # 确认告警
POST /api/v1/alarms/{id}/resolve       # 恢复告警
GET  /api/v1/alarms/stats?from=&to=    # 告警统计（MTBF/MTTR）
```

---

## 九、开发阶段与里程碑

| 阶段 | 内容 | 交付物 | 优先级 |
|---|---|---|---|
| **Phase 0** | 配置体系迁移 (INI→JSON) | `config.json` Schema + 重构 ConfigLoader | P0 |
| **Phase 1** | 采集引擎健壮性 | MQTT 重连 + 驱动重连 + 离线缓存 | P0 |
| **Phase 2** | Avalonia UI 跨平台客户端 | 可运行的多页面客户端 | P1 |
| **Phase 3** | gRPC API Gateway | 完整的 gRPC 服务 + REST 适配层 | P1 |
| **Phase 4** | Eclipse Ditto 集成 | Thing 模型 + 状态同步 | P1 |
| **Phase 5** | Apache IoTDB 集成 | 时序存储 + 查询 API | P1 |
| **Phase 6** | 安灯系统核心 | 告警规则 + 灯号看板 + REST API | P2 |
| **Phase 7** | CNC 驱动补全 | Fanuc / Siemens CNC / Mazak / Heidenhain 驱动 | P2 |

**开发顺序**：
```
Phase 0 → Phase 1 → Phase 2 + Phase 3（并行）→ Phase 4 → Phase 5 → Phase 6 → Phase 7
```

---

## 十、技术风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| Avalonia UI 学习曲线高于预期 | 中 | 中 | 参考 twin-data-collector 的 WinForms 实现，先做 MVP |
| Eclipse Ditto Java 运维复杂度 | 低 | 高 | 使用官方 Docker Image，K3S Helm 部署 |
| gRPC 与 Ditto REST 协议转换开销 | 中 | 低 | gRPC-JSON transcoder 适配层 |
| IoTDB 边缘端资源占用 | 中 | 中 | 选择轻量模式，按需启用降采样 |
| Fanuc FOCAS 驱动无真实设备测试 | 高 | 高 | 先用模拟驱动，保留 addrCode 映射表 |

---

## 十一、已验证的技术决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| UI 框架 | **Avalonia UI** | 跨平台，.NET 8 原生，XAML 与 WPF 相近 |
| API 协议 | **gRPC** | 高性能，类型安全，双向流，适合实时数据 |
| 语义孪生 | **Eclipse Ditto** | Apache 顶级项目，Thing/Feature 模型成熟 |
| 时序数据库 | **Apache IoTDB** | 工业 IoT 原生，边缘云协同，高压缩 |
| 安灯看板 | **A 方案**（产线灯号）| 制造业标准形式，直观高效 |
| 配置体系 | **JSON Schema** | 50 代备份，校验能力强 |
| 部署环境 | **K3S** | Docker 环境已就绪，轻量 K8s |
| TDengine LOT | **不引入** | 绑定风险高，与 GenCollector 功能重叠 |
| StreamPipes | **暂不引入** | 等业务人员提出需求后再评估 |
