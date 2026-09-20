# Realtime Contract (WebSocket vs SSE)

> 本文档描述工业 IoT 平台实时通道的使用契约，对应 AsyncAPI 3.0 规范。

---

## 1. WebSocket vs SSE: When to Use Which

| Criteria | WebSocket | SSE |
|----------|-----------|-----|
| **Primary Use** | Avalonia Desktop Clients | Web Frontends |
| **Direction** | Full-duplex (bidirectional) | Server-to-client only |
| **Connection Overhead** | Higher (handshake + upgrade) | Lower (simple HTTP) |
| **Firewall Friendly** | Requires WS support | Uses standard HTTP (80/443) |
| **Auto-reconnect** | Built-in (with backoff) | Browser native retry |
| **Resume After Disconnect** | Via `lastEventId` | Via `Last-Event-ID` header |
| **Heartbeat** | Ping/pong every 30s | Server-sent comment events |
| **Subscription Model** | Dynamic subscribe/unsubscribe | One-time GET with query params |

**Recommendation:**
- **Avalonia Desktop Clients** → WebSocket (primary)
- **Web Browsers** → SSE (simpler, firewall-friendly)
- **Mobile/Web Apps needing push** → SSE

---

## 2. Authentication Flow

### 2.1 WebSocket Authentication

```
1. Client obtains JWT token from /auth/login
2. Client connects to wss://api.platform.example.com/realtime
   with query param: ?token=<jwt>
3. Server validates token:
   - If valid: connection accepted, start heartbeat
   - If invalid/expired: connection closed with code 1001
4. Token refresh: client should refresh token before expiry
```

**Token Location**: Query parameter `token` (not in WebSocket subprotocol or headers)

### 2.2 SSE Authentication

```
1. Client obtains JWT token from /auth/login
2. Client connects to GET /sse/alarms or /sse/andon
   with header: Authorization: Bearer <jwt>
3. Server validates token:
   - If valid: stream starts
   - If invalid/expired: HTTP 401 returned
```

### 2.3 Token Claims

JWT token must contain:
- `sub`: User ID
- `tenant_id`: Tenant identifier
- `exp`: Expiration timestamp
- `permissions`: Array of allowed operations

---

## 3. Reconnection and Resume Protocol

### 3.1 WebSocket Reconnection

**Exponential Backoff Strategy:**
```
Initial delay:  1000ms
Max delay:      60000ms
Multiplier:     2.0
Max attempts:   Unlimited (with backoff cap)
```

**Resume After Disconnect:**
```
1. Client stores last received event timestamp (lastEventId)
2. On reconnect, send:
   {
     "action": "subscribe",
     "deviceIds": ["CNC04", ...],
     "variables": [...],
     "resumeFrom": 1726588800000  // lastEventId timestamp
   }
3. Server resumes from timestamp, sending only missed events
4. If resumeFrom > current, server sends empty batch then live
```

**Important**: Resume is best-effort. Events older than 5 minutes may not be available.

### 3.2 SSE Reconnection

**Browser-native Behavior:**
- Browser automatically reconnects on connection loss
- Client should store and send `Last-Event-ID` header on reconnect

**Client Implementation:**
```javascript
// Store last event ID
let lastEventId = null;

// On reconnect, send Last-Event-ID
const eventSource = new EventSource('/sse/alarms', {
  headers: lastEventId ? {'Last-Event-ID': lastEventId} : {}
});

eventSource.onmessage = (event) => {
  lastEventId = event.lastEventId;
  // Process event.data
};
```

---

## 4. Error Handling

### 4.1 WebSocket Error Codes

| Code | Name | Description | Client Action |
|------|------|-------------|---------------|
| 1001 | Unauthorized | Invalid or missing token | Re-authenticate |
| 1002 | Forbidden | Insufficient permissions | Check token claims |
| 2001 | SubscriptionFailed | Failed to subscribe | Retry with exponential backoff |
| 2002 | DeviceNotFound | Unknown device ID | Remove from subscription list |
| 2003 | VariableNotFound | Unknown variable name | Remove from subscription |
| 3001 | RateLimitExceeded | Too many subscriptions | Reduce subscription count |
| 3002 | ConnectionLimitExceeded | Server at capacity | Wait and retry |
| 9001 | InternalError | Server error | Retry with backoff |

**Error Message Format:**
```json
{
  "code": 1001,
  "message": "Invalid or expired token",
  "details": "Token expired at 2024-09-17T12:00:00Z",
  "requestId": "req-123"
}
```

### 4.2 SSE Error Responses

| HTTP Status | Meaning | Client Action |
|-------------|---------|---------------|
| 200 | Success | Stream continues |
| 401 | Unauthorized | Re-authenticate |
| 403 | Forbidden | Check permissions |
| 429 | Rate Limited | Retry-After header respected |
| 500 | Server Error | Retry with backoff |

### 4.3 Heartbeat

**WebSocket:**
- Client sends `{"type": "ping", "timestamp": <ms>}` every 30 seconds
- Server responds `{"type": "pong", "timestamp": <ms>}`
- If no heartbeat received for 60 seconds, connection considered dead

**SSE:**
- Server sends comment events `: heartbeat\n\n` every 30 seconds
- Client browser handles automatically via EventSource

---

## 5. Consistency with MQTT Topics and Data Models

### 5.1 Data Model Alignment

| Concept | data-models.md | MQTT Topic | Realtime Channel |
|---------|---------------|------------|------------------|
| Device | `thingId: {ns}:{deviceId}` | - | `deviceId` |
| Variable | `variableId` | - | `variable` |
| Sample Data | Section 5 | `gen/{collectorId}/data` | `ServerPushData` |
| Alarm | Section 4 | `gen/{collectorId}/alert` | `ServerPushAlarm` |
| Andon | Section 6 | - | `ServerPushAndon` |

### 5.2 Field Mapping

**DataUpdate** (realtime variable update):
```json
{
  "deviceId": "CNC04",       // = MQTT deviceId = Ditto thingId suffix
  "variable": "WorkTime",   // = variableId from var_info_*.ini
  "value": 12345.6,         // = SampleData.values[{variable}]
  "quality": "good",       // = IoTDB quality measurement
  "timestamp": 1726588800000  // = SampleData.timestamp (UTC ms)
}
```

**AlarmEvent**:
```json
{
  "alarmId": "alm-uuid-xxxx",  // Generated server-side
  "deviceId": "CNC04",        // = MQTT deviceId
  "variableId": "SpindleTemp", // = variable that triggered
  "severity": "error",        // = MQTT severity
  "status": "active",         // = MQTT status
  "triggeredAt": 1726588800000 // = MQTT triggeredAt
}
```

### 5.3 Quality Values

Quality field maps to IoTDB measurement:
- `good`: Data is valid
- `bad`: Data read failed or invalid
- `uncertain`: Data may be inaccurate

### 5.4 Andon Status Colors

| Status | Meaning | Trigger Condition |
|--------|---------|-------------------|
| `green` | Normal | No active alarms on line |
| `yellow` | Waiting | Material shortage or planned wait |
| `red` | Fault | Active error/critical alarm |
| `blue` | Maintenance | Device in maintenance mode |

---

## 6. Subscription Protocol

### 6.1 WebSocket Messages

**Subscribe to devices:**
```json
{
  "action": "subscribe",
  "deviceIds": ["CNC04", "DHH02"],
  "variables": ["WorkTime", "RunStatus"],
  "requestId": "req-123"
}
```

**Unsubscribe:**
```json
{
  "action": "unsubscribe",
  "deviceIds": ["CNC04"],
  "requestId": "req-124"
}
```

**Server acknowledgment:**
```json
{
  "type": "ack",
  "requestId": "req-123",
  "status": "subscribed",
  "subscribedDevices": ["CNC04", "DHH02"]
}
```

### 6.2 SSE Query Parameters

**GET /sse/alarms?**
```
- severity: info,warning,error,critical (comma-separated)
- deviceId: CNC04
```

**GET /sse/andon?**
```
- lineId: line-01
```

---

## 7. Rate Limits

| Channel | Limit | Window |
|---------|-------|--------|
| WebSocket connections | 10,000 | per server |
| Subscriptions per connection | 100 | per client |
| SSE streams | 5,000 | per server |
| Message rate | 1,000 msg/sec | per client |

---

## 8. Reference

- AsyncAPI Spec: `asyncapi.yaml`
- Data Models: `data-models.md`
- MQTT Topics: `mqtt-topics.md`
- MQTT Topic Hierarchy: `gen/{collectorId}/{channel}` for uplink
