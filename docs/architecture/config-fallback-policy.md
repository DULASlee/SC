# Config Fallback Policy

## Overview

`JsonConfigLoader` supports a 4-scenario fallback strategy when transitioning from legacy INI config to JSON config. This document explains the critical/non-critical distinction, behavior on corruption, alert strategy, and migration marker format.

---

## Config Criticality Classification

| Class | Description | Examples | Behavior on Corruption |
|-------|-------------|----------|------------------------|
| **Critical** | Without it, the application **cannot start at all** | `config.json` (appId, mqtt.server, authCode) | **Refuse to start** — throw `InvalidOperationException` |
| **Non-critical** | The app can start with degraded functionality | `devices.json`, `var_infos.json`, `var_groups.json` | Load INI fallback; log warning; continue |

Only `config.json` is currently classified as critical.

---

## The 4 Scenarios (JsonConfigLoader.LoadSetting)

### Scenario 1: JSON exists + parse fails → throw `InvalidOperationException`

```
config.json is present but malformed (JSON syntax error, etc.)
```

**Behavior**: Startup is aborted. The exception message includes the original parse error and makes clear the file must be repaired.

**Rationale**: A corrupted critical config means the process cannot know what configuration to apply. Starting with stale or default values risks mis-addressing MQTT endpoints or authenticating incorrectly — both are silent failure modes.

**Operator action**: Restore from backup (`GenCollector/Config/.backups/config.json`) or fix the JSON manually.

---

### Scenario 2: JSON exists + parse succeeds → normal load

```
config.json is present and valid
```

**Behavior**: Normal load, backup saved, env-var substitution and sensitive-field checks applied.

---

### Scenario 3: JSON missing + migration NOT complete → load INI, emit warning, set migration marker

```
config.json is absent AND .migration_complete marker is absent
```

**Behavior**:
1. A warning is written to `Console.Error` (visible in container logs).
2. The legacy INI config is loaded via `ConfigLoader.LoadSetting(_dir)`.
3. A migration marker file is written to `Config/.migration_complete`.

**Rationale**: INI fallback is the safe path during transition. The warning ensures operators notice the fallback; the marker prevents repeated warnings on every startup.

**Operator action**: No immediate action required. The system is running on INI config. A future deployment should include the JSON config.

---

### Scenario 4: JSON missing + migration IS complete → throw `InvalidOperationException`

```
config.json is absent BUT .migration_complete marker exists
```

**Behavior**: Startup is aborted. The exception explains the unexpected state.

**Rationale**: If migration is marked complete but the JSON is gone, either the JSON was accidentally deleted post-migration or the deployment is misconfigured. Starting on INI in this state would be unexpected and potentially misconfigured.

**Operator action**: Either restore `config.json` from backup or remove `Config/.migration_complete` to re-enter Scenario 3.

---

## Migration Marker File

**Location**: `Config/.migration_complete`

**Format**: JSON

```json
{
  "migratedAt": "2026-03-18T09:41:00.0000000Z",
  "source": "INI"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `migratedAt` | ISO 8601 datetime (UTC) | When the marker was written |
| `source` | string | Always `"INI"` for now; reserved for future migration paths |

The marker is written **only on first INI fallback** (Scenario 3). It is never deleted by the loader — only an operator should remove it.

---

## Alert / Notification Strategy for Fallback

| Event | Severity | Signal |
|-------|----------|--------|
| Scenario 3 entered (first INI fallback) | **Warning** | `Console.Error` line + audit log entry with `action: "ini_fallback"` |
| Scenario 4 (unexpected state) | **Error** | `InvalidOperationException` thrown — will appear in container `terminate` log |
| Scenario 1 (JSON corrupted) | **Error** | `InvalidOperationException` thrown — appears in container `terminate` log |
| Hot reload validation failure + rollback | **Warning** | `ConfigChanged` event with `result.Success == false` + audit log entry |

### Kubernetes Alerting Recommendation

In K8S, route these signals as follows:

- `Console.Error` output → Kubernetes log (viewable via `kubectl logs`); configure a Log-based alert or ship to your log aggregator (Loki, ES, etc.).
- `InvalidOperationException` during startup → pod will enter `CrashLoopBackOff`; alert on `CrashLoopBackOff` state for the deployment.
- Hot-reload failures → hook the `ConfigChanged` event and forward `ReloadResult` to your alerting system (e.g., a custom HTTP endpoint, Slack webhook, or PagerDuty).

---

## Hot Reload — K8S / ConfigMap Note

**This hot-reload mechanism is for development and non-Kubernetes deployments only.**

In Kubernetes, when a `ConfigMap` is updated:

1. The mounted file inside the pod **is not automatically updated** in-place.
2. Kubernetes triggers a **pod rollout** (rolling restart) to pick up the new ConfigMap.
3. In-app file watching does **not** detect ConfigMap updates.

Therefore:
- In K8S production: rely on rolling deployments for config updates, not in-app reload.
- In dev / Docker Compose: this `ConfigHotReloader` works correctly because the volume mount is a real filesystem with working `inotify` / `FSEvents` / `ReadDirectoryChangesW`.
- On K3s/Docker volumes that emulate file watching (e.g., `volume` mounts in Docker Desktop): `FileSystemWatcher` may miss events. The polling fallback (every 5 seconds) handles this case automatically.

---

## Files

- `GenCollector/Config/JsonConfigLoader.cs` — implements the 4 scenarios
- `GenCollector/Config/ConfigHotReloader.cs` — handles runtime config hot reload with debounce, atomic switch, rollback, audit log, and K8S polling fallback
- `GenCollector/Config/.migration_complete` — migration marker (written at runtime)
- `GenCollector/Config/.configAudit.json` — audit log of hot-reload changes (written at runtime)
- `GenCollector/Config/.configReload.lock` — multi-instance leader election lock (written at runtime)
