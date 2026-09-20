# 告警状态机（Alarm State Machine）

> 本文档定义告警全生命周期状态机、状态转换规则、分组去重策略、以及与安灯（Andon）系统的集成。

---

## 1. 告警全生命周期状态机

### 1.1 状态定义

| 状态 | 说明 | 可 notify | 可 ack | 可 resolve |
|------|------|-----------|--------|------------|
| `active` | 触发中，未确认 | Yes | Yes | Yes |
| `acknowledged` | 已确认，正在处理 | 降级 | - | Yes |
| `resolved` | 条件已恢复正常 | No | No | - (进入 cleared) |
| `cleared` | 已清除（人工Dismiss） | No | No | - |
| `suppressed` | 被抑制规则屏蔽 | No | No | No |
| `escalated` | 已升级（升级超时/严重度） | Yes | Yes | Yes |
| `shelved` | 暂时忽略（已知问题） | No | No | No |

### 1.2 完整状态转换图

```
                                        ┌──────────────────────────────────┐
                                        │ suppress                         │
                                        │ (suppression rule matches)       │
                                        ▼                                  │
[trigger]────► [active] ──ack──► [acknowledged] ◄──de-escalate──────────┤
                    │   ▲              │   ▲                               │
                    │   │              │   │                               │
        [unshelve]  │   │ [escalate]   │   │ [unshelve]                    │
        (suppress   │   │ (timeout or  │   │ (manual                       │
         ends)      │   │  severity    │   │  unshelve)                    │
                    │   │  threshold)  │   │                               │
                    │   │              │   │                               │
                    ▼   │              ▼   │                               │
               [shelved]              [escalated]                          │
                                        │                                  │
                                        │ (ack in time                    │
                                        │  or manual                      │
                                        ▼                                  │
                        [resolved] ◄─────┴───── [auto_resolve / manual_resolve]
                            │                              │
                            │ clear                        │ clear
                            │ (operator dismiss)           │ (operator dismiss)
                            ▼                              ▼
                       [cleared]                     [cleared]
```

### 1.3 转换表

| 转换 | 触发条件 | 源状态 | 目标状态 | 说明 |
|------|----------|--------|----------|------|
| `trigger` | 变量值触发阈值 | - | `active` | 新告警产生 |
| `ack` | 操作员确认告警 | `active` / `escalated` | `acknowledged` | 停止紧急通知，启动解决计时器 |
| `auto_resolve` | 条件自动恢复正常 | `acknowledged` / `escalated` | `resolved` | 值回到正常范围（带 deadband） |
| `manual_resolve` | 操作员强制解决 | `active` / `acknowledged` / `escalated` | `resolved` | 人工清除条件 |
| `clear` | 操作员Dismiss已解决告警 | `resolved` | `cleared` | 结束告警生命周期 |
| `suppress` | 抑制规则匹配 | `active` / `shelved` | `suppressed` | 抑制期间不通知 |
| `unshelve` | 抑制结束或人工取消 | `suppressed` / `shelved` | 原状态 | 恢复原状态 |
| `escalate` | 确认超时或严重度升级 | `active` / `acknowledged` | `escalated` | 提升告警级别，通知主管 |
| `de-escalate` | 升级后操作员及时确认 | `escalated` | `acknowledged` | 降回已确认状态 |
| `shelve` | 操作员暂时忽略已知问题 | `active` / `acknowledged` | `shelved` | 暂停通知，进入已知问题列表 |

---

## 2. 告警分组与去重（Alarm Grouping / De-duplication）

### 2.1 合并规则

**同设备、同变量、同告警类型** 在 N 秒内重复触发 → 合并为一条，累加计数：

| 字段 | 处理方式 |
|------|----------|
| `alarmCount` | +1（记录合并次数） |
| `triggeredAt` | 保持首次触发时间 |
| `lastValue` | 更新为最新触发值 |
| `lastTriggeredAt` | 更新为本次触发时间 |
| `message` | 可选：追加 " (x{N}次)" |

**N 秒默认值**：可配置，通常 60s（由告警规则配置指定）。

### 2.2 振动/模拟量告警：Deadband + Dwell Time

模拟量/振动类告警防止临界点抖动：

```
触发条件（以 H=100, hysteresis=2, dwell=5s 为例）：
  - 值持续 > 100 超过 5s（dwell） → 触发
  - 值持续 < 98（100-2）超过 5s → 恢复

          ┌── dwell ──┐
    ──────┘           └────
    100 ─┬────────────────────
         │   [active]
    98 ─┼────────────────────
         │   [resolved]
    ────┴────────────────────
         ◄─ hysteresis ──►
```

**参数**：
- `deadband`：迟滞回差（防止临界抖动）
- `dwellTime`：持续超标时间（防突变误报）

---

## 3. 自动解决 vs 手动解决

### 3.1 自动解决（Auto Resolve）

条件：变量值**持续**回到正常范围（带 deadband + dwell）

- 传感器恢复正常 → 自动进入 `resolved`
- 记录 `resolvedAt` 时间戳
- 用于：温度回落、振动恢复正常、液位回到安全范围

### 3.2 手动解决（Manual Resolve）

条件：操作员强制判定为已解决（不问条件是否恢复）

- 用于：故障已人工修复但传感器未更新、已知误报
- 操作员可附加 `comment` 说明原因
- 记录 `resolvedBy` = 操作员ID

---

## 4. 状态转换时的动作（Actions on Transitions）

| 目标状态 | 触发的动作 |
|----------|-----------|
| `active` | 1. 发送告警通知（邮件/SMS/看板）<br>2. 启动 `escalationTimer`（超时未 ack 则 escalate）<br>3. 写入 alarm 事件到 IoTDB |
| `acknowledged` | 1. 停止紧急通知（降为普通提醒）<br>2. 停止 escalationTimer<br>3. 启动 `resolveTimer`（可选：超时未 resolve 则提示）<br>4. 记录 `acknowledgedAt`, `acknowledgedBy` |
| `escalated` | 1. 发送升级通知（主管/经理）<br>2. 记录 `escalationLevel` +1<br>3. 启动新的 escalationTimer |
| `resolved` | 1. 记录 `resolvedAt`<br>2. 记录 `resolvedBy`（auto_resolve 时为 system）<br>3. 计算 `timeToResolve` = resolvedAt - triggeredAt（用于 MTBF 统计）<br>4. 发送解决通知 |
| `cleared` | 1. 发送清除确认<br>2. 更新 Andon 状态<br>3. 写入最终审计记录 |
| `suppressed` | 1. **不发送通知**<br>2. 记录 `suppressReason`（规则ID或操作员）<br>3. 记录 suppression 开始时间 |
| `shelved` | 1. **不发送通知**<br>2. 记录 `shelveReason`、`shelvedBy`<br>3. 告警保留在列表但暂停处理 |

---

## 5. Ditto Thing 结构（alarmStatus Feature）

```json
{
  "thingId": "org.gencore:CNC04",
  "features": {
    "alarmStatus": {
      "properties": {
        "state": "acknowledged",
        "severity": "error",
        "triggeredAt": 1726588800000,
        "acknowledgedAt": 1726588900000,
        "resolvedAt": null,
        "clearedAt": null,
        "acknowledgedBy": "operator-001",
        "resolvedBy": null,
        "escalationLevel": 0,
        "suppressReason": null,
        "alarmCount": 1,
        "lastValue": 85.0,
        "alarmId": "alm-uuid-xxxx",
        "variableId": "SpindleTemp",
        "deviceId": "CNC04",
        "message": "主轴温度超过阈值 80°C，当前值 85°C"
      }
    }
  }
}
```

### 5.1 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `state` | string | 当前状态：`active` / `acknowledged` / `resolved` / `cleared` / `suppressed` / `escalated` / `shelved` |
| `severity` | string | 严重度：`info` / `warning` / `error` / `critical` |
| `triggeredAt` | int64 | 触发时间戳（毫秒） |
| `acknowledgedAt` | int64 | 确认时间戳 |
| `resolvedAt` | int64 | 解决时间戳 |
| `clearedAt` | int64 | 清除时间戳 |
| `acknowledgedBy` | string | 确认人 ID |
| `resolvedBy` | string | 解决人 ID（`system` = 自动解决） |
| `escalationLevel` | int | 当前升级级别（0=未升级） |
| `suppressReason` | string | 抑制原因（规则ID或 `manual`） |
| `alarmCount` | int | 合并计数（去重后累计） |
| `lastValue` | double | 最后触发时的变量值 |
| `alarmId` | string | 告警唯一 ID |
| `variableId` | string | 关联变量 ID |
| `deviceId` | string | 关联设备 ID |
| `message` | string | 告警消息文本 |

---

## 6. 与安灯（Andon）的集成

### 6.1 告警严重度 → 安灯颜色映射

| 告警 severity | 安灯颜色 | 说明 |
|---------------|----------|------|
| `info` | 蓝色 | 提示信息 |
| `warning` | 黄色 | 一般警告 |
| `error` | 橙色 | 错误/故障 |
| `critical` | 红色 | 紧急停机 |

### 6.2 产线级 Andon 聚合规则

产线安灯颜色 = **最高优先级设备告警** 的颜色：

```
产线 Andon 颜色 = MAX(设备告警 severity)
  critical (红) > error (橙) > warning (黄) > info (蓝) > normal (绿)
```

**设备告警优先级**：
1. 若存在 `critical` 告警（任何状态） → 产线红色
2. 若存在 `error` 告警 → 产线橙色
3. 若存在 `warning` 告警 → 产线黄色
4. 若存在 `info` 告警 → 产线蓝色
5. 无告警 → 绿色

### 6.3 安灯事件订阅

安灯服务订阅 MQTT topic：`v1/{tenant}/{site}/{line}/{device}/alarm`

- 仅处理 `active` / `acknowledged` / `escalated` 状态（忽略 resolved/cleared）
- 产线级安灯由后台服务聚合设备告警后更新

---

## 7. 审计日志（Alarm Audit）

每条告警记录完整状态变更历史：

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

## 8. 与现有 data-models.md 的差异

| 项目 | 原有 data-models.md | 本文档 |
|------|---------------------|--------|
| 状态数 | 3个（active/acknowledged/resolved） | 7个（+ suppressed/escalated/shelved/cleared） |
| 抑制/升级/暂挂 | 无 | 完整定义 |
| 清除（clear） | 无 | 独立状态 |
| 去重合并 | 无 | deadband + dwell + N秒合并 |
| 自动/手动解决 | 混用 | 明确区分 |
| 状态转换动作 | 无 | 完整定义 |
| Ditto alarmStatus feature | 仅 activeAlarms 数组 | 完整 alarmStatus 详情 |
| Andon 集成 | 简单颜色映射 | 含聚合规则 |

---

## 9. 现有代码实现情况

| 功能 | 位置 | 状态 |
|------|------|------|
| 基础 alarm tags | `MelCollector.cs` (AlarmStatus/Num/Msg) | ✅ 已有 |
| 告警 MQTT 上报 | `mqtt-topics.md` alarm topic | ✅ 已有 |
| 状态机逻辑 | - | ❌ 未实现 |
| 分组去重 | - | ❌ 未实现 |
| 升级/抑制/暂挂 | - | ❌ 未实现 |
| 审计日志 | - | ❌ 未实现 |
| Andon 聚合 | - | ❌ 未实现 |
