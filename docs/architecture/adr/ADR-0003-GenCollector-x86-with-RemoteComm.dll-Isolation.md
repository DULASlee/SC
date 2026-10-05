# ADR-0003: GenCollector x86 with RemoteComm.dll Isolation

**Status**: Accepted  
**Date**: 2026-09-17  
**Deciders**: Architecture Team

---

## Context

`RemoteComm.dll` is a 3rd-party native 32-bit driver that interfaces with proprietary hardware (DHH series). This driver is only available as a 32-bit binary and cannot be loaded into a 64-bit process.

The project needs GenCollector to run on modern Windows (x64) while maintaining full compatibility with this legacy driver.

---

## Decision

**Short Term (Phase 0.5–0.9):**  
GenCollector and GenCollector.Tests run as **x86 (32-bit)** processes. This allows direct loading of `RemoteComm.dll` without any inter-process communication overhead.

**Long Term (Phase 1+):**  
Isolate `RemoteComm.dll` in a dedicated `RemoteCommHost` x86 process, communicated with via **gRPC** (or named pipes) from the main 64-bit GenCollector process. This decouples the 32-bit memory constraint from the main collector.

```
GenCollector (x64, long-term)
    │ gRPC / Named Pipes
    ▼
RemoteCommHost (x86)
    └──► RemoteComm.dll (32-bit driver)
```

---

## Consequences

### Short-Term (Phase 0.5–0.9)

#### Positive
- Works today with zero additional complexity
- `RemoteComm.dll` loads directly — no IPC latency

#### Negative
- **Memory ceiling of ~4 GB** (32-bit address space limit)
- Cannot take advantage of >4 GB RAM on host machine
- Some .NET libraries are x64-only (rare, but possible)

### Long-Term (Phase 1+)

#### Positive
- GenCollector runs x64, fully utilizing available memory
- RemoteCommHost crash does not crash GenCollector (process isolation)
- Future: RemoteCommHost can be containerized separately

#### Negative
- gRPC IPC adds ~0.5–2 ms latency per call
- Additional deployment complexity (two processes)

---

## Memory Budget (Short Term)

| Component | Estimated Memory |
|-----------|-----------------|
| GenCollector .NET runtime | ~150–300 MB |
| RemoteComm.dll (native) | ~20–50 MB |
| Config/state buffers | ~50–100 MB |
| MQTTnet buffers | ~50–100 MB |
| **Headroom** | **~3.5 GB** |

JSON config migration (ADR-0004) reduces memory footprint vs. old INI parsing approach.

---

## Build Configuration

```
GenCollector.csproj  → Platform Target: x86
GenCollector.Tests.csproj → Platform Target: x86
```

RemoteComm.dll must be placed in the same directory as `GenCollector.exe` for DLL resolution.

---

## References

- ADR-0004 (INI to JSON Migration)
- RemoteComm.dll vendor documentation (internal)
