# mcp

MCP（Model Context Protocol）配置。

DSH 自带官方客户端包 `@deepseek-ai/dsh-mcp-client`，每个 MCP server 一个 entry，挂载在 `cordis.patch.yml` 中即可接入（**不**是通过配置文件列 server URL）。MCP 工具以 `mcp__<serverName>__<tool>` 命名，注册到 `ctx.tools`。

## 接入方式

在 `~/.dsh/profiles/<profile>/cordis.patch.yml` 新增一段：

```yaml
- id: mcp-<server-name>
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: <unique-name>
    transport: stdio  # 或 streamable-http
    command: npx      # stdio 时
    args: [...]
    env:
      KEY: !!js process.env.KEY
    # 或 streamable-http 时：
    # url: http://localhost:3000/mcp
    # headers: { Authorization: !!js '`Bearer ${process.env.MCP_TOKEN}`' }
```

每个 server 独立 id，命名空间唯一。stdio 启动临时 probe 子进程，streamable-http 走 endpoint。

## 验证标准

- **连通性**：服务启动后工具出现在 `<available_skills>` 之外、`ctx.tools.schemas` 内的 `mcp__<server>__<tool>` 列表
- **查询结果**：模型调用 `mcp__<server>__<tool>` 能返回正确结果（成功 + 失败两条路径都要试）
- **失败表现**：`failOnStartupError: false` 时启动失败仅记日志、不挂 harness；设为 `true` 时启动失败直接拒绝 plugin activation

## 重新发现根因：2026-09-20

会话中"codebase-memory-mcp 装了 223MB 索引但 0 次调用"的真相是：**MCP 没作为 plugin 加载**——磁盘上有二进制、有索引，跟能不能被 harness 调用无关。DSH 没有 MCP auto-discovery 配置，每个 server 必须显式作为 `@deepseek-ai/dsh-mcp-client` 的一个 entry 挂载。

相关源码：`packages/mcp/mcp-client/README.md`、`packages/mcp/mcp-client/src/index.ts`（plugin 入口）、`packages/mcp/mcp-client/src/transport.ts`（stdio/HTTP 传输实现）。

## 当前挂载清单（2026-09-21）

| serverName | profile | 启动方式 | 说明 |
|---|---|---|---|
| `codebase-memory` | headless | `npx -y codebase-memory-mcp`（stdio，v0.11.0 本机实测拉起） | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) 官方 npm 分发；首次使用调 `index_repository(repo_path="F:/JQKJ")` 显式索引 |

改 `cordis.patch.yml` 后必须**重启 dsh 会话**才生效（`patchReload: startup`）。

**连通性验证 = 三层判定（缺一层都算未修通）**：

1. **plugin 加载成功**：重启 dsh 会话时，`failOnStartupError: true` 下若 npm 拉包失败/二进制起不来，**启动即被拒绝 plugin activation**——不用等到第一次调用才暴露。启动无拒绝日志 = 第一层通。
2. **工具注册成功**：模型侧工具集出现 `mcp__codebase-memory__<tool>`（15 个工具，`get_graph_schema` 建议先跑）。名字在只是注册成功，不代表能调用。
3. **协议握手成功且返回合法**：实际调一次 `mcp__codebase-memory__get_graph_schema`（或 `index_repository`）看返回是否为合法 JSON schema/结果。此层失败 = plugin 起来了、工具注册了，但 MCP 握手或 server 内部逻辑有问题——**与 `--version` 验证完全不同的故障域**（`--version` 走 CLI 主流程，证明不了 stdio 协议握手/工具注册/schema 暴露）。

三层全通才算"修通"。`--version` 通过仅证明"包能拉、二进制能起、版本存在"，是第一层的辅助证据，不是判定依据。

**failOnStartupError: true 的价值**：把故障暴露点从"调用时才发现挂了"提前到"启动时立刻报错"——提前量很关键，沉默失败就是 2026-09-20 "223MB 索引 0 调用" 事故的温床（server 挂了没人知道，直到业务侧 0 调用才被发现）。

## desktop profile 挂载决策（2026-09-21）

**判断标准是"desktop 侧的 MCP 由谁管"，不是"有没有找到配置文件"**：

- 桌面 IDE 的 MCP 配置可能藏在 IDE 自己的设置数据库里（注册表、SQLite、JSON 二进制化存储），
  而非一个可读的 `.mcp.json` 文件。搜了 `F:\JQKJ\.mcp.json`、`~/.claude/`、`~/.config/`、
  `%LOCALAPPDATA%` 四个常见路径**没找到**，只能证明"不在这四个位置"，**不能证明"不存在"**。
- 若 desktop 侧 MCP 声明权属于 IDE（Cursor / Claude Desktop 各自管自己的 MCP 配置），
  DSH desktop profile 重复挂 = 同一 server 起两个进程、两份索引、两份内存，还可能端口/锁文件冲突。
- 若 desktop 侧确实没有任何 IDE 声明 codebase-memory，挂一次是对的。

**挂前必答一问**：DSH desktop profile 启动时，codebase-memory 的 stdio 子进程是
**复用 headless 那个**，还是**另起一个**？stdio 传输各自 spawn，通常各起各的 →
重复挂载有真实代价（双进程双索引双内存），不是配置冗余。

**决策结论（本次）**：不急着挂。先让 headless 侧端到端跑通三层验证（见上文），
确认 server 本身没问题，再决定 desktop 要不要挂。否则 desktop 挂上后出问题，
分不清是 server 问题还是配置问题。当前实测（2026-09-21）：`F:\JQKJ\.mcp.json` 不存在，
`~/.claude/`、`~/.config/`、`%LOCALAPPDATA%` 下未发现声明 codebase-memory 的 IDE 侧通道
（注：这只排除了这四个位置，不排除 IDE 设置数据库里的通道）。

## jqkj-search 启用步骤（未启用；真实障碍是缺 MCP server 封装层）

`docs/ai-workspace/tools/jqkj-search/` 目前是纯 Python CLI（`jqkj-search.cmd` 包装器），
**没有 MCP server 入口**，所以无法以 MCP 形式挂载。

**MCP ≠ CLI 包装（不要误判工作量）**：MCP 挂上的能力是结构化工具调用——参数有 schema、
返回有类型、模型能自主决策是否调用及调用次数。把 CLI 包一层 shell/命令，只是让模型
"手动拼命令 + 手动解析输出"，没有 schema 约束，也无法被自动路由。所以真实障碍是
**缺一层 MCP server 封装**，不是"加个 `mcp` 子命令"这么简单（子命令只是封装的一种实现）。

启用路径（按优先级）：

1. **首选**：写薄 MCP server 封装 `jqkj_search.py` 的查询函数（`doc`/`sym`/`outline`/`find`/`index`）：
   - 用官方 `mcp` SDK（`pip install mcp`，本机 Py3.14 已有 `mcp` 包；注意
     `python -m mcp` 不是可执行入口，要用 `python -m mcp.cli.stdio` 或自定义 entrypoint；
     CLI 运行时需 `typer`，`pip install "mcp[cli]"`）。
   - 或裸实现 stdio JSON-RPC（`initialize`/`tools/list`/`tools/call`），零依赖。
2. 在 `~/.dsh/profiles/<profile>/cordis.patch.yml` 增加 entry：
   ```yaml
   - id: mcp-jqkj-search
     name: '@deepseek-ai/dsh-mcp-client'
     config:
       serverName: jqkj-search
       transport: stdio
       command: python
       args: ['F:/JQKJ/docs/ai-workspace/tools/jqkj-search/jqkj_search_mcp.py']  # 封装入口
       env:
         JQKJ_SEARCH_DB: !!js process.env.JQKJ_SEARCH_DB
       failOnStartupError: false  # 未就绪前允许沉默，但须配启动日志钩子
   ```
3. 重启 dsh 会话；验证 `mcp__jqkj-search__doc` 调通（成功 + 零命中两条路径）。

在步骤 1 完成前，agent 可经 `pwsh` 直接跑 `jqkj-search.cmd` 获得**功能近似**的能力
（能查，但没有 schema 约束、模型无法自主决策调用）——这是过渡方案，不是 MCP 等价物。

**封装层入口的两条自检要求（防再次沉默失败）**：

- **启动时自检依赖是否齐全**：缺 `mcp` / `mcp[cli]`（`typer`）时**显式报错退出**
  （打印清晰错误到 stderr + 非零 exit），不要让 `import` 失败变静默退出——
  这正是本次反复修的那类沉默失败（"依赖缺了就静默挂"）。封装脚本若用 shebang
  或依赖清单假定"已装 mcp[cli]"，在只装基础 mcp 包的机器上会启动失败且失败方式
  不显眼。
- **启动后向 DSH 报告"我起来了、我能提供这些工具"**：成功 start 时输出一行
  确认到 stderr（如 `[jqkj-search-mcp] ready, tools: doc, sym, outline, find, index`），
  让 `failOnStartupError` 与启动日志钩子有显式信号可抓。自检失败与 ready 信号是
  一正一反两条显式路径，杜绝"起来了但不知道起了"。