# Phase 0.5 Archive Manifest

**Phase**: 0.5  
**Tag**: `phase-0.5-complete`  
**Date**: 2026-09-17  
**Status**: Complete

---

## 1. Deliverables Summary

### 1.1 Schema Files

| File | Path | Purpose |
|------|------|---------|
| `config.schema.json` | `GenCollector/config/JsonSchemas/` | JSON schema for main config (appId, mqtt, authCode) |
| `devices.schema.json` | `GenCollector/config/JsonSchemas/` | JSON schema for device registry |
| `var_infos.schema.json` | `GenCollector/config/JsonSchemas/` | JSON schema for variable metadata |
| `var_groups.schema.json` | `GenCollector/config/JsonSchemas/` | JSON schema for variable groups |

### 1.2 Sample JSON Configs

| File | Path |
|------|------|
| `config.json` | `GenCollector/config/samples/` |
| `devices.json` | `GenCollector/config/samples/` |
| `var_infos.json` | `GenCollector/config/samples/` |
| `var_groups.json` | `GenCollector/config/samples/` |

### 1.3 Source Files (Config System)

| File | Path | Responsibility |
|------|------|----------------|
| `ConfigMigrator.cs` | `GenCollector/Config/` | INI → JSON migration (idempotent) |
| `JsonConfigLoader.cs` | `GenCollector/Config/` | 4-scenario JSON/INI fallback |
| `ConfigHotReloader.cs` | `GenCollector/Config/` | File watching, debounce, atomic switch, rollback |
| `BackupManager.cs` | `GenCollector/Config/` | Atomic backup, rollback, concurrent-safe |
| `MigrationReport.cs` | `GenCollector/Config/` | Migration result model |
| `IMigrationReport.cs` | `GenCollector/Config/` | Migration result interface |

### 1.4 Architecture Documents

| File | Path |
|------|------|
| `ADR-0001` | `docs/architecture/adr/` |
| `ADR-0002` | `docs/architecture/adr/` |
| `ADR-0003` | `docs/architecture/adr/` |
| `ADR-0004` | `docs/architecture/adr/` |
| `phase-0-5-acceptance.md` | `docs/architecture/` |
| `config-fallback-policy.md` | `docs/architecture/` |
| `deployment-topology.md` | `docs/architecture/` |
| `data-models.md` | `docs/architecture/` |
| `mqtt-topics.md` | `docs/architecture/` |
| `realtime-contract.md` | `docs/architecture/` |
| `asyncapi.yaml` | `docs/architecture/` |
| `openapi.yaml` | `docs/architecture/` |

### 1.5 Legacy INI Configs (Preserved)

| File | Path |
|------|------|
| `setting.ini` | `GenCollector/config/` |
| `device_cnc.ini` | `GenCollector/config/` |
| `device_plc.ini` | `GenCollector/config/` |
| `device_imm.ini` | `GenCollector/config/` |
| `protocol.ini` | `GenCollector/config/` |
| `protocol_cnc.ini` | `GenCollector/config/` |
| `var_group_cnc.ini` | `GenCollector/config/` |
| `var_group_plc.ini` | `GenCollector/config/` |
| `var_info_cnc.ini` | `GenCollector/config/` |

---

## 2. Test Report Summary

### 2.1 Results

| Metric | Value |
|--------|-------|
| Total Tests | 35 |
| Passed | 33 |
| Skipped | 2 |
| Failed | 0 |
| Duration | 0.7069 seconds |

### 2.2 Skipped Tests

| Test | Reason |
|------|--------|
| `ConfigIntegrationTests.MigrateSetting_NonUtf8EncodedIni_ParsesCorrectly` | GBK/Shift-JIS encoding requires .NET Core Encoding.Provider registration |
| `ConfigIntegrationTests.LoadSetting_NonUtf8EncodedIni_ParsesCorrectly` | Same as above |

### 2.3 Test Coverage by Module

| Module | Test Class | Count |
|--------|-----------|-------|
| Config Migration | `ConfigMigratorTests` | 6 |
| Config Integration | `ConfigIntegrationTests` | 16 |
| JSON Config Loading | `JsonConfigLoaderTests` | 4 |
| Backup Management | `BackupManagerTests` | 6 |

---

## 3. Gate Checklist

### 3.1 Code Quality

- [x] All unit tests pass (no critical skipped tests blocking)
- [x] Code compiles without warnings
- [x] Configuration files are well-formed (INI/JSON)

### 3.2 Functional Acceptance

- [x] GenCollector supports FOCAS protocol for CNC data collection
- [x] GenCollector supports HttpMem protocol for DHH data collection
- [x] Config migration tool (INI → JSON) works correctly
- [x] Backup manager supports atomic writes and concurrent safety
- [x] JSON config loader supports INI fallback

### 3.3 Documentation Acceptance

- [x] `deployment-topology.md` contains complete deployment architecture
- [x] `data-models.md` defines device, time-series, and alarm models
- [x] `mqtt-topics.md` defines MQTT topic contracts
- [x] `collector-architecture-analysis.md` analyzes collector architecture
- [x] Four ADRs created in `docs/architecture/adr/`

### 3.4 Test Acceptance

- [x] Unit test coverage report generated
- [x] All tests pass (35 total, 33 passed, 2 skipped)

---

## 4. Git Commit Information

> **Note**: This workspace is **not a git repository**. Git tagging was requested but could not be performed. The following tag was intended:

```
Tag: phase-0.5-complete
Message: "Phase 0.5 complete: JSON config system, schemas, migrator, backup, hot-reload, specs"
```

All deliverables listed above are part of Phase 0.5. When git is initialized, apply the tag above to capture this milestone.

---

## 5. Phase 0.6+ Backlog

- [ ] RemoteCommHost x86 process isolation (gRPC)
- [ ] EMQX rules engine → Kafka integration (>10k devices/second)
- [ ] IoTDB hot/cold分层存储策略
- [ ] End-to-end integration tests
- [ ] Prometheus告警规则完善
