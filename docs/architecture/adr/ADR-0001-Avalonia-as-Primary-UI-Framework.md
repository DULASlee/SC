# ADR-0001: Avalonia as Primary UI Framework

**Status**: Accepted  
**Date**: 2026-09-17  
**Deciders**: Architecture Team

---

## Context

The project requires a cross-platform desktop UI for a real-time dashboard that displays CNC/PLC/IMM data, supports MQTT-driven live updates, and must run on Windows (primary) with a future path to Linux/macOS.

Candidate frameworks considered:

| Framework | Cross-Platform | Real-Time UI | MQTT Support | Ecosystem |
|-----------|---------------|--------------|--------------|-----------|
| Avalonia UI | Yes (Win/Linux/macOS) | Excellent | Yes | Growing |
| Blazor WASM | Yes | Good (SignalR) | Requires server | Large |
| .NET MAUI | Windows/iOS/Android | Good | Yes | Growing |
| Electron | Yes | Good | Yes | Large, but heavy |

---

## Decision

**Use Avalonia UI** as the primary cross-platform desktop UI framework.

All communication between the Avalonia client and backend services MUST go through the API Gateway/BFF. The Avalonia client shall **NOT** directly connect to Ditto REST API or any MQTT broker.

---

## Consequences

### Positive

- Single C#/.NET codebase targets Windows, Linux, and macOS
- Avalonia's reactive bindings are well-suited for real-time dashboard updates
- Avalonia can host MQTTnet library (for protocol capability), but will NOT use it for client connections — all MQTT traffic is routed through BFF
- Native look and feel on each platform via Skia rendering
- Smaller binary size compared to Electron

### Negative

- Avalonia ecosystem is smaller than WPF/WinForms — some third-party controls may need custom implementation
- Skia rendering has GPU memory overhead; mitigated by virtualized lists
- Learning curve for developers unfamiliar with reactive UI patterns

### Constraints Enforced

- **Avalonia MUST NOT instantiate MQTTnet `MqttClient` directly** — all MQTT publish/subscribe goes through BFF HTTP endpoints or BFF-managed SignalR
- **Avalonia MUST NOT call Ditto REST API directly** — all Ditto access is through BFF

---

## References

- Avalonia UI: https://avaloniaui.net/
- API Gateway/BFF Pattern: See ADR-0002
