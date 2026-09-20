# 数据模型（Data Models）

> 本文档定义平台核心数据模型，对应 Ditto Thing 模型、IoTDB 时序schema、MQTT 消息结构。

---

## 1. ID 策略

### 1.1 层级 ID

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `tenant_id` | UUID | 租户唯一标识 | `550e8400-e29b-41d4-a716-446655440000` |
| `site_id` | UUID | 站点唯一标识 | `6ba7b810-9dad-11d1-80b4-00c04fd430c8` |
| `line_id` | UUID | 产线唯一标识 | `6ba7b811-9dad-11d1-80b4-00c04fd430c8` |
| `device_id` | UUID 或复合ID | 设备唯一标识 | 制造商码+序列号组合（不可变） |
| `variable_id` | string | 变量唯一标识 | `SpindleSpeed` (字母数字) |

### 1.2 设备 ID 组成

设备 ID 由制造商码 + 序列号组合生成，确保全球唯一且不可变：

```
device_id = "{manufacturer_code}_{serial_number}"
```

示例：`MITS_12345678` (三菱加工中心，序列号 12345678)

### 1.3 变量 ID 命名

变量 ID 在同一设备内唯一，允许使用字母、数字、下划线：

```
variable_id = [a-zA-Z][a-zA-Z0-9_]*
```

示例：`SpindleSpeed`, `Axis_X`, `RunStatus_1`

---

## 2. 变量定义模型

对应 `TagDefinition`（IoTPlatform.Core）和 `var_info_*.ini`（原始采集器配置）。

```json
{
  "variableId": "WorkTime",
  "deviceId": "CNC04",
  "name": "WorkTime",
  "displayName": "总运行时间",
  "remark": "设备累计运行时间",
  "address": "33868",
  "dataType": "CNCMacro",
  "unit": "s",
  "precision": 1,
  "deadband": 0.1,
  "sampleRate": 1000,
  "group": "realtime",
  "enabled": true,
  "thresholds": {
    "HH": { "value": null, "hysteresis": 0 },
    "H":  { "value": null, "hysteresis": 0 },
    "L":  { "value": null, "hysteresis": 0 },
    "LL": { "value": null, "hysteresis": 0 }
  },
  "trigger": null
}
```

### 2.1 dataType 枚举

| 值 | 说明 |
|----|------|
| `CNCMacro` | CNC 宏变量（双精度浮点） |
| `PLCWord` | PLC 字寄存器（short/long） |
| `HttpMemRegister` | HttpMem 寄存器（int/double） |
| `ModbusRegister` | Modbus 寄存器 |
| `Digital` | 数字量（bool） |
| `Analog` | 模拟量（float/double） |

### 2.2 阈值配置

每 个变量可配置四级阈值，带迟滞回差：

| 阈值级别 | 名称 | 触发方向 |
|----------|------|----------|
| `HH` | Highest High | > 上限上限 |
| `H` | High | > 上限 |
| `L` | Low | < 下限 |
| `LL` | Lowest Low | < 下限下限 |

**迟滞 (hysteresis)**：防止阈值临界点抖动。例如 H=100, hysteresis=2，则：
- 值 > 100 时触发
- 值 < 98 时恢复（100 - 2）

### 2.3 group（变量组）

| 组名 | 采集频率 | 用途 |
|------|----------|------|
| `realtime` | 1-20s | 实时监控 |
| `tech` | 工艺周期 | 工艺参数 |
| `spc` | 统计周期 | SPC 统计过程控制 |

---

## 3. 告警状态机

### 3.1 状态定义

| 状态 | 说明 |
|------|------|
| `active` | 告警触发中 |
| `acknowledged` | 已确认（正在处理） |
| `resolved` | 已解决 |

### 3.2 状态转换

```
[active] --ack--> [acknowledged] --resolve--> [resolved]
    ^                    |
    |                    +--escalate--+
    |                               |
    +-----------suppress------------+
```

| 转换 | 触发条件 | 说明 |
|------|----------|------|
| `trigger` | 变量值触发阈值 | 进入 active 状态 |
| `ack` | 操作员确认告警 | active → acknowledged |
| `resolve` | 条件恢复正常 | acknowledged → resolved |
| `escalate` | 告警超时未处理 | acknowledged → active（升级） |
| `suppress` | 人工抑制告警 | active → resolved（抑制） |

### 3.3 告警审计

每条告警记录完整的状态变更历史：

```json
{
  "alarmId": "alm-uuid-xxxx",
  "deviceId": "CNC04",
  "variableId": "SpindleTemp",
  "severity": "error",
  "status": "acknowledged",
  "audit": [
    {
      "action": "trigger",
      "timestamp": 1726588800000,
      "operator": null,
      "previousState": null,
      "comment": null
    },
    {
      "action": "ack",
      "timestamp": 1726588900000,
      "operator": "operator-001",
      "previousState": "active",
      "comment": "正在检查设备"
    }
  ]
}
```

---

## 4. 安灯状态机

### 4.1 产线安灯状态

| 状态 | 颜色 | 说明 |
|------|------|------|
| `normal` | 绿色 | 一切正常 |
| `warning` | 黄色 | 存在警告 |
| `stop` | 红色 | 紧急停机 |
| `planned` | 蓝色 | 计划性停机 |
| `maintenance` | 白色 | 维护中 |

### 4.2 状态转换

```
[green] <---> [yellow] ---> [red]
   ^              |              ^
   |              v              |
   +---- [blue] --+---> [white] -+
```

| 当前状态 | 触发条件 | 目标状态 | 说明 |
|----------|----------|----------|------|
| green | 任一设备 warning | yellow | 有警告 |
| yellow | 所有设备恢复正常 | green | 恢复正常 |
| yellow | 任一设备 stop | red | 紧急停机 |
| red | 所有设备恢复正常 | green | 恢复正常 |
| any | 计划停机开始 | blue | 计划性停机 |
| blue | 计划停机结束 | green | 恢复运行 |
| any | 维护开始 | white | 进入维护 |
| white | 维护结束 | green | 恢复运行 |

### 4.3 安灯模型

```json
{
  "lineId": "line-01",
  "lineName": "1号产线",
  "status": "warning",
  "devices": [
    {
      "deviceId": "CNC04",
      "deviceName": "CNC-01",
      "status": "running",
      "alertCode": "TEMP_HIGH",
      "alertMessage": "主轴温度告警",
      "severity": "warning"
    }
  ],
  "statistics": {
    "totalDevices": 10,
    "runningDevices": 8,
    "warningDevices": 1,
    "stoppedDevices": 1
  },
  "updatedAt": 1726588800000
}
```

---

## 5. Ditto ↔ IoTDB 映射

### 5.1 Ditto Thing 模型

Eclipse Ditto 使用 **Thing** 抽象设备，每个设备对应一个 Thing。

```json
{
  "thingId": "org.gencore:CNC04",
  "policyId": "org.gencore:policy-default",
  "attributes": {
    "name": "CNC-01 三菱加工中心",
    "protocol": "mitsubishi_cnc:mitsubishi_v3",
    "ip": "192.168.3.14",
    "port": 8193,
    "mqttDeviceId": "CNC04",
    "company": "总公司",
    "workshop": "一车间",
    "process": "加工工序",
    "collectorId": "CNC04",
    "varGroup": "realtime",
    "enabled": true
  },
  "features": {
    "telemetry": {
      "properties": {
        "WorkTime": { "value": 12345.6, "timestamp": 1726588800000, "quality": 0 },
        "RunStatus": { "value": 1, "timestamp": 1726588800000, "quality": 0 }
      }
    },
    "alarm": {
      "properties": {
        "activeAlarms": [],
        "lastAlarm": { "alarmId": "alm-xxx", "severity": "error", "message": "..." }
      }
    },
    "status": {
      "properties": {
        "online": { "value": true, "timestamp": 1726588800000 }
      }
    }
  }
}
```

### 5.2 IoTDB Path 映射

IoTDB 采用树形路径组织时序数据，与 Ditto feature 对应：

| Ditto Feature | IoTDB Path | 说明 |
|---------------|------------|------|
| `telemetry` | `/root/{tenant}/{device}/variables/{variable}` | 遥测变量时序 |
| `alarm` | `/root/{tenant}/{device}/alarms/{alarmId}` | 告警事件时序 |
| `status` | `/root/{tenant}/{device}/status` | 设备状态时序 |

**示例**：

```
/root/tenant-a/CNC04/variables/WorkTime
/root/tenant-a/CNC04/variables/RunStatus
/root/tenant-a/CNC04/variables/SpindleSpeed
/root/tenant-a/CNC04/alarms/alm-uuid-xxxx
/root/tenant-a/CNC04/status
```

### 5.3 IoTDB Schema

每条时序注册以下 Measurement：

| Measurement | 数据类型 | 说明 |
|-------------|----------|------|
| `value` | DOUBLE | 变量值 |
| `quality` | TEXT | 数据质量标识 (GOOD/UNCERTAIN/BAD/OFFLINE) |

### 5.4 质量码映射

| 平台质量码 | IoTDB quality | 说明 |
|------------|---------------|------|
| 0 | `GOOD` | 数据有效 |
| 1 | `UNCERTAIN` | 数据可疑 |
| 2 | `BAD` | 数据无效 |
| 3 | `OFFLINE` | 设备离线 |

---

## 6. 时序数据保留策略

IoTDB 数据保留策略（冷热分层）：

| 层级 | 保留时间 | 存储介质 | 说明 |
|------|----------|----------|------|
| hot | 30 天 | SSD/高速存储 | 实时查询 |
| warm | 31-365 天 | 普通存储 | 历史分析 |
| cold | > 1 年 | 归档存储 | 归档备查 |

### 6.1 降采样规则

| 原始频率 | 降采样后 | 保留时长 |
|----------|----------|----------|
| 1s | - | 30 天 |
| 10s | 1min avg | 1 年 |
| 1min | 5min avg | 长期 |
| 5min | 1h avg | 长期 |

---

## 7. 设备模型（对应 Ditto Thing）

Eclipse Ditto 使用 **Thing** 抽象设备，每个设备对应一个 Thing。

```json
{
  "thingId": "org.gencore:CNC04",
  "policyId": "org.gencore:policy-default",
  "attributes": {
    "name": "CNC-01 三菱加工中心",
    "protocol": "mitsubishi_cnc:mitsubishi_v3",
    "ip": "192.168.3.14",
    "port": 8193,
    "mqttDeviceId": "CNC04",
    "company": "总公司",
    "workshop": "一车间",
    "process": "加工工序",
    "collectorId": "CNC04",
    "varGroup": "realtime",
    "enabled": true
  },
  "features": {
    "realtime": {
      "properties": {
        "WorkTime": { "value": 12345.6, "timestamp": 1726588800000 },
        "RunStatus": { "value": 1, "timestamp": 1726588800000 },
        "SpindleSpeed": { "value": 3000.0, "timestamp": 1726588800000 }
      }
    }
  }
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `thingId` | 格式 `{namespace}:{deviceId}`，如 `org.gencore:CNC04` |
| `attributes` | 设备静态属性（配置信息） |
| `features` | 设备功能特征，按变量组（varGroup）划分 |
| `features.*.properties` | 动态实时值（最新采样值） |

---

## 8. 变量/指标模型

对应 `TagDefinition`（IoTPlatform.Core）和 `var_info_*.ini`（原始采集器配置）。

```json
{
  "variableId": "WorkTime",
  "deviceId": "CNC04",
  "name": "WorkTime",
  "displayName": "总运行时间",
  "remark": "设备累计运行时间",
  "address": "33868",
  "dataType": "Double",
  "unit": "s",
  "decimals": 1,
  "group": "realtime",
  "enabled": true,
  "trigger": null
}
```

### dataType 枚举

| 值 | 说明 |
|----|------|
| `CNCMacro` | CNC 宏变量（双精度浮点） |
| `PLCBit` | PLC 位寄存器（bool） |
| `PLCWord` | PLC 字寄存器（short/long） |
| `PLCFloat` | PLC 浮点寄存器 |
| `HttpMemRegister` | HttpMem 寄存器（int/double） |
| `Boolean` | 布尔 |
| `Integer` | 整数 |
| `Double` | 浮点数 |
| `String` | 字符串 |

### group（变量组）

| 组名 | 采集频率 | 用途 |
|------|----------|------|
| `realtime` | 1-20s | 实时监控 |
| `tech` | 工艺周期 | 工艺参数 |
| `spc` | 统计周期 | SPC 统计过程控制 |

---

## 9. 时序数据模型（对应 IoTDB）

IoTDB 采用树形路径组织时序数据。

### 9.1 Path 命名规范

```
/root/{tenant_id}/{device_id}/{variable_name}
```

示例：

```
/root/tenant-a/CNC04/WorkTime
/root/tenant-a/CNC04/RunStatus
/root/tenant-a/CNC04/SpindleSpeed
/root/tenant-a/DHH02/RunStatus
```

### 9.2 时间序列 Schema

每条时序注册以下类型的 Measurement：

| Measurement | 数据类型 | 说明 |
|-------------|----------|------|
| `value` | DOUBLE | 变量值 |
| `quality` | TEXT | 数据质量标识（good/bad/uncertain） |

### 9.3 查询示例

```sql
-- 查询设备最近 1 小时数据
SELECT time, value FROM root.tenant-a.CNC04.* WHERE time > NOW() - 3600000

-- 按变量名精确查询
SELECT time, value FROM root.tenant-a.CNC04.RunStatus WHERE time > NOW() - 86400000

-- 聚合查询（每 1 分钟平均值）
SELECT avg(value) FROM root.tenant-a.CNC04.SpindleSpeed GROUP BY INTERVAL=60000
```

---

## 10. 告警事件模型

```json
{
  "alarmId": "alm-uuid-xxxx",
  "deviceId": "CNC04",
  "collectorId": "CNC04",
  "variableId": "SpindleTemp",
  "severity": "error",
  "status": "active",
  "message": "主轴温度超过阈值 80°C，当前值 85°C",
  "triggerValue": 85.0,
  "threshold": {
    "operator": ">",
    "value": 80
  },
  "triggeredAt": 1726588800000,
  "acknowledgedAt": null,
  "acknowledgedBy": null,
  "resolvedAt": null,
  "comment": null
}
```

### severity 枚举

| 值 | 说明 | 颜色（安灯） |
|----|------|-------------|
| `info` | 提示信息 | 蓝色 |
| `warning` | 警告 | 黄色 |
| `error` | 错误 | 橙色 |
| `critical` | 严重（停机） | 红色 |

### status 枚举

| 值 | 说明 |
|----|------|
| `active` | 触发中 |
| `acknowledged` | 已确认 |
| `resolved` | 已解决 |

---

## 11. 采样数据模型（MQTT 上行）

对应 `SampleData`（IoTPlatform.Core）。

```json
{
  "deviceId": "CNC04",
  "collectorId": "CNC04",
  "timestamp": 1726588800000,
  "elapsedMs": 12.5,
  "values": {
    "WorkTime": 12345.6,
    "RunTime": 67890.1,
    "RunStatus": 1,
    "SpindleSpeed": 3000.0,
    "SpindleLoad": 65.4,
    "FeedRate": 1500.0,
    "AxisX": 120.345,
    "AxisY": 85.672,
    "AxisZ": 0.0,
    "ToolNo": 3,
    "ProgramNo": "O1234",
    "AlarmCode": 0,
    "EmergencyStop": 0
  },
  "errors": {}
}
```

---

## 12. 安灯状态模型

```json
{
  "lineId": "line-01",
  "lineName": "1号产线",
  "status": "alert",
  "devices": [
    {
      "deviceId": "CNC04",
      "status": "running",
      "alertCode": "TEMP_HIGH",
      "alertMessage": "主轴温度告警"
    }
  ],
  "updatedAt": 1726588800000
}
```

---

## 13. 模型关系图

```
Tenant (租户)
  │
  ├── Collector (采集器)
  │     └── deviceId ──► Device Thing (Ditto)
  │                        ├── attributes (静态配置)
  │                        └── features.telemetry (实时变量值)
  │
  ├── Variable (变量定义)
  │     └── deviceId ──► Device
  │
  ├── SampleData (时序数据)
  │     └── deviceId + timestamp ──► IoTDB path: /root/{tenant}/{device}/variables/{var}
  │
  ├── Alarm (告警事件)
  │     └── deviceId + variableId ──► 关联 Variable
  │     └── IoTDB path: /root/{tenant}/{device}/alarms/{alarmId}
  │
  └── AndonLine (安灯产线)
        └── deviceId ──► Device
```
