# ADR-0004: INI to JSON Migration with Graded Fallback

**Status**: Accepted  
**Date**: 2026-09-17  
**Deciders**: Architecture Team

---

## Context

GenCollector historically used INI files for all configuration (`setting.ini`, `device_cnc.ini`, `var_info_cnc.ini`, etc.). As the system grows:

- INI lacks schema validation
- INI has no support for nested structures or arrays
- No type-safe deserialization
- Hot reload requires manual file watching per section

However, the INI files are currently in production and cannot be deleted until JSON configs are validated. A migration strategy is needed that is **safe, idempotent, and reversible**.

---

## Decision

1. **JSON is the primary configuration format** — all new config must be authored in JSON with schema validation
2. **INI is fallback only** — INI is loaded ONLY when:
   - The corresponding JSON file does NOT exist, AND
   - The migration marker (`Config/.migration_complete`) has NOT been set
3. **Corrupted JSON throws exception** — if JSON exists but is malformed, the application refuses to start (critical configs) or falls back with a warning (non-critical configs)
4. **Migration is idempotent** — running the migrator multiple times produces the same result; it does not overwrite existing JSON unless `--force` is specified
5. **INI is preserved as backup** — after migration, the original INI file is moved to `Config/.backups/<original_name>.ini`

---

## Config Criticality

| Config File | Critical? | Fallback Behavior on Corruption |
|-------------|-----------|----------------------------------|
| `config.json` | **Yes** — appId, mqtt.server, authCode | Throw `InvalidOperationException` — refuse to start |
| `devices.json` | No | Fall back to INI + warning |
| `var_infos.json` | No | Fall back to INI + warning |
| `var_groups.json` | No | Fall back to INI + warning |

---

## Migration Marker

A marker file at `Config/.migration_complete` (JSON) is written on first INI fallback:

```json
{
  "migratedAt": "2026-09-17T00:00:00.0000000Z",
  "source": "INI"
}
```

This marker prevents silent INI fallback loops. It is created only when INI is actually loaded as a fallback (not on successful JSON load).

---

## Fallback Scenarios

| Scenario | JSON Present | JSON Valid | Migration Marker | Behavior |
|----------|-------------|------------|-----------------|----------|
| 1 | Yes | **No** | — | Throw `InvalidOperationException` |
| 2 | Yes | Yes | — | Normal JSON load |
| 3 | **No** | — | **No** | Load INI, write marker, warn |
| 4 | **No** | — | Yes | Throw `InvalidOperationException` (unexpected state) |

---

## Consequences

### Positive

- **Zero-risk migration** — INI always available as safety net during transition
- **Idempotent** — migrator can be run in CI/CD without side effects
- **Audit trail** — backup directory preserves original INI
- **Schema validation** — JSON schemas in `config/JsonSchemas/` catch misconfigurations early
- **Hot reload** — JSON file watching enables zero-downtime config updates

### Negative

- **Two config formats to maintain** during transition period (Phase 0.5–1.0)
- **Marker file must be cleaned up** if full INI→JSON migration is ever reversed
- **Corrupted JSON requires manual intervention** — no auto-repair

### Migration Command

```bash
# Idempotent — safe to run multiple times
dotnet run -- migrate

# Force overwrite existing JSON (rarely needed)
dotnet run -- migrate --force
```

---

## References

- `GenCollector/Config/ConfigMigrator.cs` — migration logic
- `GenCollector/Config/JsonConfigLoader.cs` — 4-scenario fallback
- `GenCollector/Config/BackupManager.cs` — atomic backup/rollback
- `GenCollector/config/JsonSchemas/` — JSON schemas for all config types
