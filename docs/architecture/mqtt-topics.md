# MQTT Topic 契约

> **TASK-015 冻结版本 v1.0 (2026-09-18)** — 业务开发前置契约冻结
>
> 单一真源：`contracts/schemas/telemetry.json`（遥测 payload）
>
> 字段命名约定（camelCase 锁）：`tenantId / siteId / lineId / deviceId / variableId`
>
> 时间戳（锁）：`integer` UTC milliseconds int64 — **dropped `timestampIso`**
>
> 质量码（锁）：`integer` 0-3 (GOOD/UNCERTAIN/BAD/OFFLINE) — **dropped string enum**
>
> 已知开放问题（移到 TASK-016+）：
> - AndonStatus enum 冲突（4 套）
> - CommandStatus enum 冲突（OpenAPI vs MQTT）
> - Ditto feature key (telemetry vs realtime)
> - collectorId 跨契约不一致
> - siteId 在 OpenAPI/AsyncAPI 缺失

## 1. Topic 命名规范

```
v1/{tenant_id}/{site_id}/{line_id}/{device_id}/{channel}   # 采集器上行
v1/{tenant_id}/{site_id}/{line_id}/{device_id}/cmd/{action} # 命令下行
```

**版本前缀**: 所有 topic 必须使用 `v1/` 前缀，以支持协议版本管理。

**字段值约定（冻结）**：
- `tenant_id`, `site_id`, `line_id`: 人类可读字符串（例：`tenant-a`, `site-01`, `line-01`）。UUID 方案在 data-models Section 1.1 声明，但所有实际示例使用 plain string。冻结为 plain string。
- `device_id`: plain string（例：`CNC04`）。data-models Section 1.2 的复合 ID 格式（`MITS_12345678`）未实际使用，冻结为 plain string。

---

## 2. 完整 Topic 列表

| Topic 模式 | QoS | 说明 |
|------------|-----|------|
| `v1/{tenant}/{site}/{line}/{device}/telemetry` | 0 | 遥测数据（payload 锁 telemetry.json） |
| `v1/{tenant}/{site}/{line}/{device}/status` | 1 | 在线/离线/心跳状态 |
| `v1/{tenant}/{site}/{line}/{device}/alarm` | 1 + retain | 告警事件 |
| `v1/{tenant}/{site}/{line}/{device}/cmd/write` | 1 | 写值命令 |
| `v1/{tenant}/{site}/{line}/{device}/cmd/write/ack` | 1 | 命令响应 |
| `v1/{tenant}/{site}/{line}/{device}/config/reload` | 0 | 重载配置 |

---

## 3. Last Will and Testament (LWT)

设备连接时设置 LWT，MQTT Broker 在设备意外断开时自动发布：

| 字段 | 值 |
|------|-----|
| Topic | `v1/{tenant}/{site}/{line}/{device}/status` |
| Payload | `{"status": "offline", "reason": "connection_lost"}` |
| QoS | 1 |
| Retain | true |

设备正常断开时应主动发布 `status: offline`；异常断开时由 Broker 代发 LWT。

---

## 4. 消息 TTL (Time To Live)

| Topic | TTL | 说明 |
|-------|-----|------|
| `v1/{...}/telemetry` | 86400s (24h) | 遥测数据保留一天 |
| `v1/{...}/status` | 3600s (1h) | 状态消息一小时 |
| `v1/{...}/alarm` | 永久 (retain) | 告警保留直到解决 |
| `v1/{...}/cmd/write` | 300s | 命令超时失效 |
| `v1/{...}/cmd/write/ack` | 300s | 命令响应超时 |
| `v1/{...}/config/reload` | 60s | 配置重载命令 |

---

## 5. 离线缓冲策略（Edge 端）

### 5.1 本地队列

边缘采集器本地维护 SQLite 队列，确保持久化缓冲：

| 参数 | 值 |
|------|-----|
| 存储 | SQLite 数据库 |
| 最大容量 | 10000 条消息 |
| 策略 | FIFO（先进先出） |
| 去重 | 按 `messageId` (UUID) 去重 |
| 序列号 | 每设备递增序号，用于排序 |

### 5.2 断线续传

- MQTT 断开期间，数据写入本地 SQLite 队列
- 重连后，按序列号顺序 FIFO 上传
- 上传成功后删除本地记录
- 队列满时丢弃最旧消息

### 5.3 重连策略

```
initialDelayMs:  1000
maxDelayMs:      60000
multiplier:       2.0
```

---

## 6. 消息格式（冻结）

### 6.1 时间戳（锁）

**所有时间戳统一使用 `integer` Unix UTC milliseconds（int64）。**

- ❌ Dropped：`timestampIso` 字段（无消费者，冗余）
- ✅ 唯一真源：`timestamp` 字段（integer ms）

### 6.2 Schema 版本（锁）

每条消息必须包含 `schemaVersion` 字段：

```json
{
  "schemaVersion": "1.0",
  ...
}
```

### 6.3 质量码 (Quality Code)（锁）

**整数编码（frozen v1.0）**：

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | GOOD | 数据有效 |
| 1 | UNCERTAIN | 数据可疑 |
| 2 | BAD | 数据无效 |
| 3 | OFFLINE | 设备离线 |

- ❌ Dropped：AsyncAPI 的 string enum（`good/bad/uncertain`，OFFLINE 缺失）
- ❌ Dropped：data-models IoTDB TEXT 编码（`GOOD/UNCERTAIN/BAD/OFFLINE` 全大写）
- ✅ 真源：MQTT 整数编码，Gateway 在边界做转换

质量码存储于 IoTDB quality 列，MQTT 消息中通过 `quality` 字段传递。

---

## 7. 遥测数据 — `v1/{...}/telemetry`

**QoS: 0**

**Payload 单一真源：`contracts/schemas/telemetry.json`**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-xxxx",
  "sequenceNumber": 12345,
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "timestamp": 1726588800000,
  "elapsedMs": 12.5,
  "values": {
    "WorkTime": 12345.6,
    "RunStatus": 1,
    "SpindleSpeed": 3000,
    "SpindleLoad": 65.4
  },
  "errors": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `schemaVersion` | string | 固定 `"1.0"` |
| `messageId` | UUID | 消息唯一标识，用于去重 |
| `sequenceNumber` | int64 | 设备端递增序号 |
| `tenantId/siteId/lineId/deviceId` | string | 见 §1 |
| `timestamp` | int64 | UTC milliseconds（唯一时间戳字段） |
| `elapsedMs` | double | 采样耗时 |
| `quality` | int | 0=GOOD 1=UNCERTAIN 2=BAD 3=OFFLINE |
| `values` | object | 变量名→值映射 |
| `errors` | object | 读取失败的变量及错误信息 |

---

## 8. 设备状态 — `v1/{...}/status`

**QoS: 1**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-yyyy",
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "status": "online",
  "previousStatus": "offline",
  "reason": "heartbeat",
  "timestamp": 1726588800000,
  "quality": 0
}
```

**状态枚举（锁）**: `online` / `offline` / `heartbeat`

---

## 9. 告警事件 — `v1/{...}/alarm`

**QoS: 1, retain: true**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-zzzz",
  "alarmId": "alm-uuid-xxxx",
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "variableId": "SpindleTemp",
  "severity": "error",
  "status": "active",
  "message": "主轴温度超过阈值 80°C，当前值 85°C",
  "triggerValue": 85.0,
  "threshold": { "operator": ">", "value": 80 },
  "triggeredAt": 1726588800000,
  "quality": 0
}
```

**severity 枚举（锁）**: `info` / `warning` / `error` / `critical`
**status 枚举（锁）**: `active` / `acknowledged` / `resolved`

---

## 10. 命令下行 — `v1/{...}/cmd/write`

**QoS: 1**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-cmd-001",
  "commandId": "cmd-uuid-xxxx",
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "variableId": "ToolNo",
  "value": 5,
  "priority": 5,
  "timestamp": 1726588800000,
  "ttl": 300
}
```

---

## 11. 命令响应 — `v1/{...}/cmd/write/ack`

**QoS: 1**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-ack-001",
  "commandId": "cmd-uuid-xxxx",
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "variableId": "ToolNo",
  "status": "success",
  "value": 5,
  "timestamp": 1726588800000
}
```

**status 枚举（锁）**: `success` / `failed` / `timeout`

---

## 12. 配置重载 — `v1/{...}/config/reload`

**QoS: 0**

```json
{
  "schemaVersion": "1.0",
  "messageId": "uuid-reload-001",
  "commandId": "cmd-uuid-yyyy",
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "timestamp": 1726588800000
}
```

---

## 13. 消费者映射表

| Topic | Ditto | IoTDB | 规则引擎 | 安灯服务 |
|-------|-------|-------|----------|----------|
| `telemetry` | - | 遥测数据 | all | - |
| `status` | alarm+status | - | all | - |
| `alarm` | alarm+status | 告警事件 | all | alarm |
| `cmd/write` | - | - | - | - |
| `cmd/write/ack` | - | - | - | - |
| `config/reload` | - | - | - | - |

**说明**：
- **Ditto** ← alarm+status：告警和状态写入 Eclipse Ditto
- **IoTDB** ← telemetry：遥测数据写入 IoTDB 时序数据库
- **规则引擎** ← all：所有消息进入规则引擎进行计算和处理
- **安灯服务** ← alarm：仅订阅告警事件触发安灯展示

---

## 14. 统一语义变量名（跨品牌）

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `WorkTime` | double | 总运行时间（秒） |
| `RunTime` | double | 加工时间（秒） |
| `CycleTime` | double | 循环时间（秒） |
| `RunStatus` | int | 运行状态（0=停/1=运行/2=加工） |
| `SpindleSpeed` | double | 主轴转速（rpm） |
| `SpindleLoad` | double | 主轴负载（%） |
| `FeedRate` | double | 进给速度（mm/min） |
| `AxisX` / `AxisY` / `AxisZ` | double | 坐标位置（mm） |
| `ToolNo` | int | 刀具号 |
| `ProgramNo` | string | 程序号 |
| `AlarmCode` | int | 告警代码（0=正常） |
| `EmergencyStop` | int | 急停（0=正常/1=急停） |

---

## 15. QoS 策略总结

| 场景 | QoS | Topic |
|------|-----|-------|
| 遥测数据（高频） | 0 AtMostOnce | `v1/{...}/telemetry` |
| 状态变更（低频） | 1 AtLeastOnce | `v1/{...}/status` |
| 告警事件（重要） | 1 AtLeastOnce + retain | `v1/{...}/alarm` |
| 命令下发（关键） | 1 AtLeastOnce | `v1/{...}/cmd/write`, `v1/{...}/cmd/write/ack` |
| 配置重载 | 0 AtMostOnce | `v1/{...}/config/reload` |

---

## 16. 消息 JSON 格式契约

所有消息均使用 UTF-8 编码的 JSON，顶部无需包装 envelope。

| Topic 模式 | Content-Type | 编码 |
|------------|--------------|------|
| 所有 `v1/*` | `application/json` | UTF-8 |
