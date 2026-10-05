# 跨 IDE 共享记忆（现状 = agentmemory）

> 本文件曾于 2026-09-18 描述一套 episodic + ECC + codebase 三层骨架并标注"已落地"。
> 2026-09-20 经磁盘实测，该骨架从未真正跑通（详见下"历史骨架为何失效"）。
> **现状以 agentmemory 为唯一跨 IDE 记忆主干。决策见 ADR-0006。**

## 当前方案（agentmemory）

| 项 | 值 |
|---|---|
| 主干 | `rohitg00/agentmemory`（Apache-2.0），本地 `iii-engine v0.11.2` |
| 模式 | ① 纯本地·免费·无 LLM 摘要（`EMBEDDING_PROVIDER=local`，LLM 环节全关） |
| 共享入口 | REST `http://localhost:3111` · MCP `agentmemory mcp` · 查看器 `http://localhost:3113` |
| Qoder 接线 | 仓库根 `.mcp.json` → `agentmemory.cmd mcp`（手动，Qoder 无自动适配器） |
| 数据/配置存储 | `%APPDATA%\agentmemory`、`~/.agentmemory\.env`（均在仓库外，不入库） |

### 日常使用
- 启动 daemon：`agentmemory`（保持其在跑，MCP/REST 客户端才有记忆服务）
- 健康检查：`agentmemory status` 或 `GET http://localhost:3111/agentmemory/livez`
- 查看记忆：浏览器打开 `http://localhost:3113`
- 诊断：`agentmemory doctor`
- 完整卸载：`agentmemory remove`

### 已知边界（诚实披露）
- **Qoder 无会话结束钩子** → 逐字稿不会自动抓取；写入靠会话中主动调 MCP remember 工具，
  自动 transcript 抓取仅在支持钩子的 agent（如 Claude Code）或 `import-jsonl` 下可靠。
- 模式 ① 摘要是零 LLM 机械压缩，非大模型撰写的漂亮总结。
- 用户环境残留一个额度耗尽的 `OPENROUTER_API_KEY`；daemon 仍会检测到但**因所有 LLM 调用已关闭
  而不会实际使用**。切勿在保持该 key 的同时开启 `AUTO_COMPRESS/CONSOLIDATION`。
- daemon 需常驻；开机自启**已实现**：Windows 计划任务 `agentmemory-daemon`（登录时触发，失败自动
  重启 3 次）。管理：`schtasks /Query|Run|Delete /TN agentmemory-daemon`。已实测：停掉手动 daemon
  后仅触发该任务，`livez` 约 3 秒恢复。

## 历史骨架为何失效（2026-09-18 → 已由 ADR-0006 取代）

| 组件 | 实情 |
|---|---|
| episodic Stop 钩子 | 仅 CodeBuddy 触发；Qoder 从不触发；实测日志全是 `transcript_path=''`（空 stdin）→ `raw/probe/normalized` 恒空 |
| `.codebuddy/settings.json` | 现已不存在，钩子未接线 |
| `obra/episodic-memory` 引擎 | Node v24 下 `better-sqlite3` 原生编译失败，从未装上；导入开关写死 false |
| SpecStory | `history/` 为空，其记录器未在此 IDE 启用 |
| `.ecc/memory/*`、`.ai-memory/*` | 空骨架，从未被真实读写路径激活 |

> 教训：文档断言"已落地"而无磁盘证据 = 虚假文档。收尾必须 grep/实测核对（已写入经验库）。
