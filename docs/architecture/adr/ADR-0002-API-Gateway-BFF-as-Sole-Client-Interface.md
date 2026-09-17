# ADR-0002: API Gateway / BFF as Sole Client Interface

**Status**: Accepted  
**Date**: 2026-09-17  
**Deciders**: Architecture Team

---

## Context

Avalonia desktop clients (and any future web/mobile clients) need to interact with:
- Eclipse Ditto (digital twin state)
- MQTT brokers (telemetry/events)
- IoTDB (time-series data)
- Alarm state machine

Direct client connections to these services would expose authentication credentials, violate multi-tenant isolation, and create protocol coupling between clients and backend services.

---

## Decision

**The API Gateway / BFF is the ONLY interface exposed to clients.** No client (Avalonia, web, mobile) may connect directly to Ditto REST, any MQTT broker, or IoTDB.

The BFF handles:
1. **Authentication & Authorization** — validates client credentials, issues JWTs, enforces tenant isolation
2. **Protocol Translation** — converts between client-friendly HTTP/SignalR and backend protocols (Ditto HTTP, MQTT, gRPC)
3. **Multi-Tenant Isolation** — ensures tenants can only access their own digital twin namespaces
4. **Aggregated APIs** — provides dashboard-specific endpoints that combine data from multiple backend services

```
Client (Avalonia)
    │
    ▼ HTTP/SignalR
API Gateway / BFF
    ├──► Eclipse Ditto    (HTTP)
    ├──► EMQX MQTT Broker (MQTT pub/sub)
    └──► IoTDB           (gRPC/HTTP)
```

---

## Consequences

### Positive

- Credentials never exposed to clients — BFF holds all service credentials
- Backend service URLs/ports are invisible to clients (security boundary)
- BFF can implement response caching, rate limiting, and request coalescing
- Protocol upgrades (e.g., MQTT v5) are hidden from clients by updating BFF only
- Supports multiple client types (Avalonia, web, mobile) with a single backend integration

### Negative

- BFF is a single point of failure — requires HA deployment (covered in Phase 1+)
- Additional network hop for every client request (mitigated by colocating BFF with backend services)
- BFF team owns both client-facing and service-facing contracts — clear ownership required

### Rules

1. **No direct Ditto HTTP from clients** — all Ditto calls go through BFF endpoints
2. **No MQTT client connections from Avalonia** — BFF exposes SignalR hubs for real-time push
3. **No direct IoTDB access from clients** — BFF provides aggregated query endpoints
4. **BFF credentials are server-side only** — never logged, never returned to clients

---

## References

- ADR-0001 (Avalonia as Primary UI)
- Eclipse Ditto Documentation
- EMQX Enterprise Documentation
