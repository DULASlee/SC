# Cross-Contract Consistency Report

**Files read:**
- `f:/JQKJ/docs/architecture/openapi.yaml` (1103 lines)
- `f:/JQKJ/docs/architecture/asyncapi.yaml` (538 lines)
- `f:/JQKJ/docs/architecture/mqtt-topics.md` (350 lines)
- `f:/JQKJ/docs/architecture/data-models.md` (583 lines)

---

## 1. Cross-Mapping Table

### Field: `tenantId`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | JWT claim: `tenant_id`; header: `X-Tenant-Id` | Not in message payloads (connection-level only) | `tenantId` | `tenant_id` |
| **Type** | `string` | N/A | `string` | `string` (UUID in Section 1.1) |
| **Format** | Free string | — | Free string | UUID (not enforced in examples) |
| **Example** | JWT claim `tenant_id` | N/A | `"tenant-a"` | `"550e8400-e29b-41d4-a716-446655440000"` |

> **Discrepancy**: Three naming conventions for the same value — `tenant_id` (snake_case in JWT/data-models) vs `tenantId` (camelCase in MQTT/OpenAPI header). UUID declared but never used in examples.

---

### Field: `siteId`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | Not defined anywhere | Not defined anywhere | `siteId` | `site_id` |
| **Type** | N/A | N/A | `string` | `string` (UUID) |
| **Format** | — | — | Free string | UUID (not enforced) |
| **Example** | — | — | `"site-01"` | `"6ba7b810-9dad-11d1-80b4-00c04fd430c8"` |

> **Discrepancy**: `siteId` is absent from OpenAPI and AsyncAPI entirely. Only present in MQTT payloads and topic path. All examples use plain strings, not UUIDs.

---

### Field: `lineId`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | `lineId` | `lineId` | `lineId` | `line_id` |
| **Type** | `string` | `string` | `string` | `string` (UUID) |
| **Format** | Free string | Free string | Free string | UUID (not enforced) |
| **Example** | `/andons?lineId=...` | `lineId: "line-01"` | `"line-01"` | `"6ba7b811-9dad-11d1-80b4-00c04fd430c8"` |

> **Discrepancy**: `lineId` vs `line_id` naming inconsistency. UUID declared but not enforced.

---

### Field: `deviceId`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | `deviceId` | `deviceId` | `deviceId` | `device_id` |
| **Type** | `string` | `string` | `string` | `string` (UUID or composite) |
| **Format** | Free string | Free string | Free string | `{manufacturer_code}_{serial_number}` |
| **Example** | `"CNC04"` | `"CNC04"` | `"CNC04"` | `"MITS_12345678"` |

> **Discrepancy**: data-models Section 1.2 defines composite ID format (`MITS_12345678`), but all examples in every other contract use plain strings (`CNC04`). No unification.

---

### Field: `variableId`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | `variableId` | `variable` (DataUpdate) / `variableId` (AlarmEvent) | `variableId` (alarm/cmd); telemetry has only `values` map | `variable_id` |
| **Type** | `string` | `string` | `string` | `string` |
| **Format** | Free string | Free string | Free string | `[a-zA-Z][a-zA-Z0-9_]*` |
| **Example** | `"SpindleSpeed"` | DataUpdate: `"WorkTime"`; AlarmEvent: `"SpindleTemp"` | Alarm: `"SpindleTemp"`; telemetry: N/A (keys in `values`) | `"SpindleSpeed"` |

> **Discrepancy**: AsyncAPI uses two different field names (`variable` vs `variableId`) for the same concept. MQTT telemetry has no `variableId` — variables are identified by name as keys in the `values` map. OpenAPI Alarm schema omits `variableId` entirely.

---

### Field: `timestamp`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | `timestamp` | `timestamp` / `triggeredAt` | `timestamp` + `timestampIso` (dual) | `timestamp` |
| **Type** | `integer` | `integer` | `timestamp`: `integer`; `timestampIso`: `string` | `integer` |
| **Format** | UTC milliseconds (int64) | UTC milliseconds (int64) | **Dual**: Unix ms + ISO8601 string | UTC milliseconds (int64) |
| **Example** | `1726588800000` | `1726588800000` | `1726588800000` + `"2024-09-17T10:30:00.000Z"` | `1726588800000` |

> **Discrepancy**: MQTT sends both int64 ms and ISO8601 string simultaneously. OpenAPI, AsyncAPI, and data-models only consume int64 ms. The `timestampIso` field is redundant and no downstream consumer is documented.

---

### Field: `qualityCode`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | Not defined | `quality` | `quality` | (IoTDB `quality` column) |
| **Type** | N/A | `string` | `integer` | TEXT |
| **Format/Enum** | — | `[good, bad, uncertain]` | `0`=GOOD, `1`=UNCERTAIN, `2`=BAD, `3`=OFFLINE | `GOOD`, `UNCERTAIN`, `BAD`, `OFFLINE` |
| **Example** | — | `"good"` | `0` | `"GOOD"` |

> **Discrepancy**: MQTT uses integer codes (0–3). AsyncAPI converts to string enum (good/bad/uncertain) — `OFFLINE` is dropped from the enum. OpenAPI has no quality field anywhere. IoTDB stores uppercase TEXT strings. No conversion rule is documented. `qualityCode` field name is not standardized.

---

### Field: `alarmState` (alarm status)

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | `status` | `status` | `status` | `status` |
| **Type** | `string` | `string` | `string` | `string` |
| **Enum** | `[active, acknowledged, resolved]` | `[active, acknowledged, resolved]` | `[active, acknowledged, resolved]` | `[active, acknowledged, resolved]` |
| **Example** | `"active"` | `"active"` | `"active"` | `"active"` |

> **Consistent across all four contracts** — no drift.

---

### Field: `schemaVersion`

| | OpenAPI | AsyncAPI | MQTT Topics | data-models |
|--|---------|----------|-------------|-------------|
| **Field name** | Not present | Not present | `schemaVersion` | Not formally defined |
| **Type** | N/A | N/A | `string` | N/A |
| **Format** | — | — | `"1.0"` | — |
| **Example** | — | — | `"1.0"` | — |

> **Discrepancy**: `schemaVersion` only exists in MQTT. OpenAPI, AsyncAPI, and data-models have no version field for message formats. No backward-compatibility strategy defined.

---

## 2. End-to-End Flow Trace

**Trace**: MQTT telemetry → rule engine → alarm trigger → Ditto state update → AsyncAPI push → OpenAPI query

### Step 1 — MQTT Telemetry (`v1/tenant-a/site-01/line-01/CNC04/telemetry`, QoS 0)

```json
{
  "schemaVersion": "1.0",
  "messageId": "d8f7c6b5-a4e3-4892-8f1a-3b5c7e9d2a4f",
  "sequenceNumber": 12345,
  "tenantId": "tenant-a",
  "siteId": "site-01",
  "lineId": "line-01",
  "deviceId": "CNC04",
  "timestamp": 1726588800000,
  "timestampIso": "2024-09-17T10:30:00.000Z",
  "quality": 0,
  "elapsedMs": 12.5,
  "values": {
    "WorkTime": 12345.6,
    "RunStatus": 1,
    "SpindleSpeed": 3000,
    "SpindleTemp": 85.0,
    "SpindleLoad": 65.4
  },
  "errors": {}
}
```

Note: `siteId` appears here but is absent from all OpenAPI and AsyncAPI schemas.

### Step 2 — Rule Engine

No intermediate format documented. Rule engine evaluates `SpindleTemp` = 85.0 > threshold H = 80, operator `>`.

### Step 3 — MQTT Alarm published (`v1/tenant-a/site-01/line-01/CNC04/alarm`, QoS 1, retain)

```json
{
  "schemaVersion": "1.0",
  "messageId": "f1e2d3c4-b5a6-7890-cdef-1234567890ab",
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
  "triggeredAtIso": "2024-09-17T10:30:00.000Z",
  "quality": 0
}
```

### Step 4 — Ditto Thing Update

```json
{
  "thingId": "org.gencore:CNC04",
  "features": {
    "alarm": {
      "properties": {
        "activeAlarms": [{
          "alarmId": "alm-uuid-xxxx",
          "deviceId": "CNC04",
          "variableId": "SpindleTemp",
          "severity": "error",
          "status": "active",
          "triggerValue": 85.0,
          "threshold": { "operator": ">", "value": 80 },
          "triggeredAt": 1726588800000
        }]
      }
    },
    "status": {
      "properties": { "online": { "value": true, "timestamp": 1726588800000 } }
    }
  }
}
```

Note: data-models Section 5.1 uses Ditto feature key `"telemetry"` for telemetry data, but Section 7 uses `"realtime"`. This document uses `"alarm"` and `"status"` (consistent with Section 5.1).

### Step 5 — AsyncAPI server.push.alarm (WebSocket/SSE push to clients)

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
  "threshold": { "operator": ">", "value": 80 },
  "triggeredAt": 1726588800000,
  "acknowledgedAt": null,
  "acknowledgedBy": null,
  "resolvedAt": null,
  "comment": null
}
```

Note: `collectorId` appears here but is not in the MQTT alarm payload.

### Step 6 — OpenAPI `GET /alarms` query

```
GET /v1/alarms?deviceId=CNC04&severity=error&status=active
X-Tenant-Id: tenant-a
```

```json
{
  "items": [{
    "alarmId": "alm-uuid-xxxx",
    "deviceId": "CNC04",
    "variableId": "SpindleTemp",
    "severity": "error",
    "status": "active",
    "triggerValue": 85.0,
    "threshold": { "operator": ">", "value": 80 },
    "triggeredAt": 1726588800000,
    "acknowledgedAt": null,
    "acknowledgedBy": null,
    "resolvedAt": null,
    "comment": null
  }],
  "total": 1
}
```

---

## 3. Explicit Confirmations

### 3.1 Timestamp: all UTC ISO8601

| Contract | Format | Standard |
|----------|--------|----------|
| OpenAPI | `integer` int64 UTC milliseconds | Unix epoch |
| AsyncAPI | `integer` int64 UTC milliseconds | Unix epoch |
| MQTT Topics | **Dual**: `timestamp` int64 **and** `timestampIso` string | Both simultaneously |
| data-models | `integer` int64 UTC milliseconds | Unix epoch |

**Result: ✗ INCONSISTENT**

MQTT is the only contract sending ISO8601 strings. OpenAPI, AsyncAPI, and data-models only handle int64 ms. The `timestampIso` field is documented but no consumer is specified.

### 3.2 ID Strategy: UUID everywhere

| Field | Declared (data-models) | Actual usage (all docs) |
|-------|------------------------|-------------------------|
| `tenant_id` | UUID | Plain string (`tenant-a`) |
| `site_id` | UUID | Plain string (`site-01`) |
| `line_id` | UUID | Plain string (`line-01`) |
| `device_id` | UUID or composite | Plain string (`CNC04`) or composite |
| `variable_id` | Pattern `[a-zA-Z][a-zA-Z0-9_]*` | Plain string |
| `alarmId` | string | `alm-` prefix + UUID (informal) |

**Result: ✗ INCONSISTENT**

UUID is the declared standard in data-models Section 1.1 but zero examples across any contract use it. All examples use human-readable plain strings. `alarmId` uses an informal `alm-` prefix not defined anywhere.

### 3.3 Enum Values: no drift across documents

| Enum | OpenAPI | AsyncAPI | MQTT | data-models | Consistent? |
|------|---------|----------|------|-------------|-------------|
| AlarmSeverity | info/warning/error/critical | info/warning/error/critical | info/warning/error/critical | info/warning/error/critical | ✓ |
| AlarmStatus | active/acknowledged/resolved | active/acknowledged/resolved | active/acknowledged/resolved | active/acknowledged/resolved | ✓ |
| AndonStatus | **normal/alert/stopped** | **green/yellow/red/blue** | **green/yellow/red/blue** (example: `alert`) | **normal/warning/stop/planned/maintenance** | ✗ INCOMPATIBLE |
| CommandStatus | accepted/executing/completed/failed | Not defined | success/failed/timeout | Not defined | ✗ |
| Quality | Not defined | **good/bad/uncertain** (string) | **0/1/2/3** (integer) | GOOD/UNCERTAIN/BAD/OFFLINE (TEXT) | ✗ |
| TagType | CNCMacro/PLCBit/PLCWord/PLCFloat/HttpMemRegister/String/Boolean/Integer/Double | N/A | N/A | CNCMacro/PLCBit/PLCWord/PLCFloat/HttpMemRegister/Boolean/Integer/Double/String | ✗ (order diff) |

**Result: ✗ NOT FULLY CONSISTENT**

Only AlarmSeverity and AlarmStatus are fully consistent. AndonStatus, CommandStatus, Quality, and TagType all have drift.

---

## 4. Discrepancies Found

### D1 — CRITICAL: Andon Status — 4 Incompatible Enum Sets

| Source | Enum Values |
|--------|-------------|
| OpenAPI `AndonStatus.status` | `normal`, `alert`, `stopped` |
| AsyncAPI `AndonStatus.status` | `green`, `yellow`, `red`, `blue` |
| MQTT topics (Section 6 description) | `green`, `yellow`, `red`, `blue` |
| MQTT topics (example payload) | `alert` (contradicts enum) |
| data-models Section 4.1 | `normal`, `warning`, `stop`, `planned`, `maintenance` |
| data-models Section 12 example | `warning` |

Four different enum sets for the same `status` field. The MQTT doc even contradicts itself (enum says green/yellow/red/blue, example shows `alert`).

### D2 — CRITICAL: Quality — Integer Codes vs String Enum vs IoTDB TEXT

MQTT sends `quality: 0` (integer, 0=GOOD through 3=OFFLINE). AsyncAPI `DataUpdate` defines `quality` as `enum: [good, bad, uncertain]` (string, OFFLINE dropped). OpenAPI has no quality field. IoTDB stores `quality` as TEXT with uppercase values `GOOD`/`UNCERTAIN`/`BAD`/`OFFLINE`. No documented conversion logic between these representations exists in any of the four contracts.

### D3 — HIGH: `siteId` Absent from OpenAPI and AsyncAPI

`siteId` is in the MQTT topic path hierarchy (`v1/{tenant}/{site}/{line}/{device}`) and in every MQTT payload, but OpenAPI Device schema and AsyncAPI message schemas contain no `siteId` field. This breaks traceability — a client using only OpenAPI or AsyncAPI cannot determine the site context of a device.

### D4 — HIGH: Ditto Feature Key — `telemetry` vs `realtime`

- data-models Section 5.1 Ditto example: feature key `"telemetry"`
- data-models Section 7 Device model example: feature key `"realtime"`
- data-models Section 5.2 IoTDB mapping table: maps Ditto `"telemetry"` feature
- AsyncAPI ServerPushData description: references "data-models Section 5 (Sampling Data Model)"

Section 5 uses `"telemetry"`; Section 7 uses `"realtime"` for the same concept. One must be designated canonical.

### D5 — HIGH: `variable` vs `variableId` in AsyncAPI

- `ServerPushData` (DataUpdate schema): uses field name `variable` (value is the variable name string, e.g. `"WorkTime"`)
- `ServerPushAlarm` (AlarmEvent schema): uses field name `variableId` (value is the variable identifier, e.g. `"SpindleTemp"`)

Same concept, two different field names in the same AsyncAPI document.

### D6 — MEDIUM: Dual Timestamp Format in MQTT (Redundant `timestampIso`)

MQTT messages carry both `timestamp: 1726588800000` and `timestampIso: "2024-09-17T10:30:00.000Z"`. No other contract generates or consumes `timestampIso`. It is documented but operationally dead — it should either be removed or a consumer should be explicitly designated.

### D7 — MEDIUM: Command Status Enum Mismatch

OpenAPI `CommandResponse.status`: `accepted`, `executing`, `completed`, `failed`
MQTT `cmd/write/ack` status: `success`, `failed`, `timeout`

`success` ≠ `completed`, `timeout` has no OpenAPI equivalent, `executing` has no MQTT equivalent. If BFF translates between MQTT and OpenAPI, explicit mapping rules are needed.

### D8 — MEDIUM: `tenantId` Three Naming Variants

| Contract | Name |
|----------|------|
| OpenAPI (JWT) | `tenant_id` (snake_case) |
| OpenAPI (header) | `X-Tenant-Id` (camelCase with prefix) |
| MQTT payload | `tenantId` (camelCase) |
| data-models | `tenant_id` (snake_case) |

Same value, three naming conventions. Should be unified to one.

### D9 — MEDIUM: `schemaVersion` Only in MQTT

Every MQTT message carries `"schemaVersion": "1.0"`. OpenAPI, AsyncAPI, and data-models have no version field. If message formats evolve, there is no versioning mechanism in REST or WebSocket contracts. This creates a future compatibility risk.

### D10 — MEDIUM: `collectorId` Present in AsyncAPI Alarm but Not in MQTT Alarm

AsyncAPI `AlarmEvent` has `collectorId: "CNC04"`. MQTT alarm payload does not carry `collectorId`. The field appears in Ditto (data-models Section 5.1/10) but is not in the OpenAPI `Alarm` schema. Its presence is inconsistent across contracts.

### D11 — LOW: MQTT Telemetry Has No `variableId` Field

MQTT telemetry payload only has a `values` map (`{"WorkTime": 12345.6, ...}`). There is no `variableId` at the message level. Variables are identified by name as map keys. This is a structural difference from alarm/command payloads which do carry `variableId`. It means clients cannot query telemetry by `variableId` — only by variable name.
