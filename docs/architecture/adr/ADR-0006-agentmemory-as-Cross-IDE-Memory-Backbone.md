# ADR-0006: agentmemory as Cross-IDE Shared Memory Backbone

**Status**: Accepted
**Date**: 2026-09-20
**Deciders**: Project owner + AI engineer (harness)

---

## Context

The project needs a **cross-IDE** memory layer: conversations/decisions captured in one IDE
(Claude Code / Cursor / Codex / Gemini CLI / CodeBuddy / Qoder) must be searchable and
reusable from every other IDE. The goal is "verbatim transcript (markdown) + summary, both
available, shared across IDEs".

The prior scaffold (`docs/ai-workspace/memory-setup.md`, 2026-09-18) documented a three-layer
design (episodic-memory + ECC + codebase-memory) as "已落地", but on-disk verification proved it
never worked:

- The episodic capture script is a **CodeBuddy-only** `Stop` hook; Qoder never fires it.
- Every observed hook run logged `session=unknown ... transcript_path=''` (empty stdin), so
  `raw/`, `probe/`, `normalized/` stayed empty.
- Its `.codebuddy/settings.json` registration file no longer exists.
- The `obra/episodic-memory` engine was never installable (native `better-sqlite3` build fails
  on Node v24); ingestion flag was hard-coded off.
- SpecStory `history/` is empty (its recorder is not active in this IDE).

---

## Decision

Adopt **`rohitg00/agentmemory`** as the single, cross-IDE memory backbone, deployed **natively on
Windows** with the pinned local `iii-engine`, and retire the broken episodic/specstory scaffold.

Chosen configuration mode: **① local / free, no LLM summarisation.**

- `EMBEDDING_PROVIDER=local` → free on-device semantic recall (Xenova all-MiniLM-L6-v2, 384 dims).
- `AGENTMEMORY_AUTO_COMPRESS=false`, `CONSOLIDATION_ENABLED=false`, `AGENTMEMORY_REFLECT=false`,
  `GRAPH_EXTRACTION_ENABLED=false`, `AGENTMEMORY_INJECT_CONTEXT=false` → daemon performs **zero**
  outbound LLM/embedding calls; no API cost, no secrets required.
- Trade-off accepted: **summaries are synthetic (zero-LLM), not LLM-written.** A richer summary
  requires a working provider key (deferred; can be upgraded to option ②/③ later without
  re-architecture).

### Provenance / legality (verified 2026-09-20)

| Item | Value |
|------|-------|
| agentmemory npm package | `@agentmemory/agentmemory@0.9.29`, **Apache License 2.0** |
| Engine runtime | `iii-hq/iii` release tag `iii/v0.11.2`, asset `iii-x86_64-pc-windows-msvc.zip` |
| Engine zip size | 10,336,536 bytes |
| Engine zip SHA-256 | `6b1a624be64367aadcbcf5654543fc3029ebb73f3092f4de0d85c3e2e7fac402` (downloaded, verified before extract) |
| Installed engine path | `%USERPROFILE%\.agentmemory\bin\iii.exe` (`--version` → `0.11.2`) |
| Runtime state | `%APPDATA%\agentmemory` (outside repo — no binary DB committed to git) |
| Config | `~/.agentmemory/.env` (outside repo; no committed secrets) |

### Integration surface (cross-IDE)

- All IDEs reach the **same** daemon via REST (`http://localhost:3111`) or MCP shim
  (`agentmemory mcp`). Verified healthy: `livez ok`, viewer `http://localhost:3113` HTTP 200,
  130 REST endpoints, 54 MCP tools.
- **Qoder**: not in agentmemory's `connect` adapter list → wired **manually** into repo
  `.mcp.json` (`agentmemory.cmd mcp`, `AGENTMEMORY_URL=http://localhost:3111`).
- **Native Windows limitation**: `connect` auto-wiring supports only copilot-cli; every other
  native-Windows agent is configured manually (matches official docs).

---

## Consequences

### Positive
- One memory store shared by every MCP/REST-capable IDE; survives the prior per-IDE fragmentation.
- Fully offline/free in mode ①; no key, no bill, no repo-committed secret.
- Native engine + local viewer = the "professional, self-contained" property the owner required.

### Negative / Risks
- **Qoder has no session-end transcript hook**, so verbatim auto-capture from Qoder is not
  automatic. Recall works via MCP; capture from Qoder is agent-driven (call the remember tool)
  rather than hook-pushed. Auto transcript capture is reliable only in hook-capable agents
  (e.g. Claude Code) or via `import-jsonl`.
- Mode ① yields synthetic (not LLM) summaries.
- The daemon must be running for MCP clients. Auto-start is implemented via a Windows
  Scheduled Task `agentmemory-daemon` (trigger: at logon, restart-on-failure x3). Verified
  2026-09-21: manual daemon stopped, task triggered, `livez` recovered in ~3 s. Manage with
  `schtasks /Query|Run|Delete /TN agentmemory-daemon`.
- An ambient out-of-credit `OPENROUTER_API_KEY` exists in user env; `.env` blanking does not
  override the process env var, so the provider line still reports `openrouter` — **harmless only
  because every LLM path is disabled**. Must stay disabled, or unset the env var in the launcher.

### Constraints Enforced
- Memory DB and `.env` MUST remain outside the repository (`%APPDATA%` / `%USERPROFILE%`).
- Provider keys MUST NOT be committed (governance L9).
- Doc/config changes centralized under `docs/` (governance L14); this ADR is the decision record
  (governance L10).

---

## References
- Prior (now-superseded) scaffold: `docs/ai-workspace/memory-setup.md`
- agentmemory: https://github.com/rohitg00/agentmemory (Apache-2.0)
- iii-engine release: https://github.com/iii-hq/iii/releases/tag/iii%2Fv0.11.2
