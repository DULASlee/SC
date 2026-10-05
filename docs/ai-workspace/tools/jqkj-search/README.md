# jqkj-search —— 精确的文档/代码检索工具

> 目的：用「小输出、高精度」的检索，替代 DSH 智能体的「整文件读取 + 目录递归列举」。

## 为什么需要它（实测数据）

会话 `d503d810`（agnes-3.0-flash，101 步）的工具调用统计：

| 现象 | 数据 |
|---|---|
| 整文件读取 | **126 次 `read`**，占工具输出 **74.6%**（951,582 字符） |
| 检索调用 | **仅 4 次 `grep`**（31.5 : 1） |
| 目录递归列举 | 4 条 `Get-ChildItem -Recurse` 各被截断在 **50,000 字符** = 20 万字符 |
| 重复读取 | 仅 2 个文件 / 3.0% —— **重复不是问题，检索能力不足才是** |

那 4 次 `grep` 的实际结果暴露了根因：

```
{"pattern":"MQTT.*(断开|点丢失|30s)|...|30\\s?s.*MQTT"}   -> 16 字符   ← 零命中
{"pattern":"灯号|cloud|聚合服务|uplink|MQTT 上报"}         -> 128 字符
```

**agent 用正则去搜"概念"，搜不到就退化成整文件读取。** 经核查，`云端聚合`、`点丢失`
这两个词在语料中确实 **0 命中**（`断开` 有 32 章节、`MQTT` 有 717 章节）——
纯正则检索永远无法跨越"提问用词 ≠ 文档用词"的鸿沟，也不会告诉 agent 为什么失败。

## 用法

在仓库根目录执行（或直接用 `docs\ai-workspace\tools\jqkj-search\jqkj-search.cmd`）：

```powershell
# 1) 概念级文档检索：BM25 + 密度排序，返回**章节**（标题路径 + 行号 + 片段）
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py doc "MQTT 断开"
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py doc "离线缓冲 队列" --top 8
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py doc "云端 聚合 上报" --any     # OR 放宽

# 2) 符号级代码检索：定义定位 / 引用列表（不必读整个文件）
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py sym CollectorEngine
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py sym MqttPublisher --refs

# 3) 结构概览：读之前先看"形状"
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py outline docs/architecture/mqtt-topics.md
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py outline src/Collector/GenCollector/Core/CollectorEngine.cs

# 4) 路径检索：替代目录递归列举（只回计数 + 少量路径）
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py find "**/*.csproj"
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py find "**/*.cs" --count

# 5) 索引维护（首次自动建；改了文件后增量刷新，秒级）
python docs\ai-workspace\tools\jqkj-search\jqkj_search.py index
```

## 实测效果（同一批真实查询）

| 查询 | 本工具输出 | 原方式 |
|---|---|---|
| `doc "MQTT 断开"` | **1,729 字符**，第 1 条即命中 `docs/architecture/mqtt-topics.md:69-75`（"5.2 断线续传"） | 正则零命中 → 退化为读整文件 |
| `sym CollectorEngine` | **157 字符**（`CollectorEngine.cs:12 class`） | 读 `CollectorEngine.cs`（5,988 字符） |
| `sym MqttPublisher --refs` | **~400 字符**（1 定义 + 3 引用，含行号） | 读 2 个文件（约 8,000 字符） |
| `find "**/*.csproj"` | **677 字符**（12 项） | `Get-ChildItem -Recurse` 50,000 字符 |

## 设计要点

- **索引**：SQLite **FTS5(trigram)**（本机 SQLite 3.50.4），CJK 子串可匹配；增量重建（按 mtime+size）。
- **混合检索**：≥3 字符词元走 FTS5 取候选，再用 LIKE 强制**全部词元命中**。
  原因：trigram 分词器**无法匹配 <3 字符的词**，而 CJK 双字词（如"断开"）恰恰最常见。
- **零命中诊断**：词元在语料中不存在时，给出真实存在的 2 字片段
  （例：`点丢失` → 建议 `丢失(44)`），把"搜不到"变成可行动信息。
- **密度排序**：命中数相同优先"短而集中"的章节，避免 468 行的巨型章节霸榜。
- **内容去重**：同一章节在多份副本中重复时只留一条（sha1 去重）。
- **噪声排除**：`.git`/`node_modules`/`bin`/`obj`/`.decomp`/`packages`/`.pypredef`/`.pyi`/`.jar`，
  以及 **`.harness/worktrees/`**——实测它是同一仓库在不同任务态下的整份副本，
  索引它会让同一文档以 3-4 条重复命中并污染排序。
- **索引版本号**：解析器或建表语句变更时必须 `INDEX_VERSION += 1`，否则增量索引会保留旧抽取结果
  （实测：修正 C# 成员正则后，未变更文件不重抽，`outline` 仍显示泛型误报 `List`/`Dictionary`）。
- **输出纪律**：每条结果 ≤160 字符片段；打印"命中总数 / 显示条数"；提示按 `offset/limit` 读取。
- **UTF-8 强制**：Windows 控制台默认 GBK 会让中文输出乱码，脚本内已 `reconfigure(encoding='utf-8')`。

## 覆盖范围与落位

文档：`.md` / `.mdc`（508 + 4 个）；代码：`.cs` / `.java` / `.py` / `.js` / `.ts` / `.go` / `.ps1` / `.xaml`。
当前索引：268 文件 / 2,049 文档章节 / 804 符号（首建约 1.5 秒，增量 0.07 秒）。

**落位**：脚本本体在本目录（随版本库分发，符合铁律 14「脚本存放于 docs/ 对应子目录」与
原则 6「AI 配置唯一源在 docs/ai-workspace/」）；**索引是构建产物**（约 17MB），落在
`.tools/search/index.db`——该路径已被 `.gitignore:75` 的 `.tools/` 覆盖，不入库，缺失时自动重建。
可用环境变量 `JQKJ_SEARCH_DB` 指定其他位置。

## 已知限制

- 概念检索是**词面**匹配（FTS + 片段提示），不是向量语义检索；跨用词鸿沟靠"零命中提示"缓解，未做同义词/embedding。
- `sym` 的符号抽取是**正则**实现，非 AST；泛型/表达式体成员等复杂写法可能漏检。
- 索引不覆盖 `.yaml`/`.json` 等配置文本（如需可扩 `CODE_EXT`）。
