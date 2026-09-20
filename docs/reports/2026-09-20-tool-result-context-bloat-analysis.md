# 工具调用结果与上下文膨胀分析（为什么 230 条工具结果）

- 日期：2026-09-20
- 样本：DSH 会话 `d503d810-cc61-45c2-baec-b268205968af`（877 事件，101 步 / 12 轮，agnes-3.0-flash）
- 关联：`docs/reports/2026-09-20-agnes-3.0-flash-slow-diagnosis.md`（v4）、`docs/superpowers/splan/agnes-3.0-flash-latency-remediation-splan.md`
- 结论：**230 条不是 230 次工具调用，而是 189 次调用 + 41 条修剪器重写副本**；体积由 126 次"整文件读取"和 4 条目录递归列举主导

## 一、"230 条"的构成（先纠一个计数误区）

```
tool/call  = 189
tool/result = 230
compaction/prune = 41
189 + 41 = 230   ← 每条 prune 都会追加一条"替换后的 tool/result"
```

即：**真实工具调用 189 次**；41 条是 `dsh-compaction-tool-result-pruner` 把超大结果改写为"头部+`[... middle pruned ...]`+尾部"后追加的副本（原文仍保留在会话日志中）。按工具拆开，替换副本的分布完全对上：

| 工具 | 调用次数 | 结果条数 | 替换副本 | 原始字符 | 均字符 | 最大字符 |
|---|---|---|---|---|---|---|
| **read** | **126** | **160** | **34** | **951,582** | 5,947 | 48,518 |
| pwsh | 23 | 30 | 7 | 301,199 | 10,039 | 50,000 |
| glob | 17 | 17 | 0 | 16,703 | 982 | 5,863 |
| grep | 4 | 4 | 0 | 3,513 | 878 | 2,720 |
| todo_write | 14 | 14 | 0 | 1,389 | 99 | 648 |
| write | 5 | 5 | 0 | 596 | 119 | 122 |
| **合计** | **189** | **230** | **41** | **1,274,982** | | |

**read 占全部工具输出的 74.6%（951,582 / 1,274,982）**，是唯一的主导项。

## 二、更正：v4 报告的字符数被 JSON 转义虚高了 2.6 倍

v4 报告表格用的是 `json.dumps(事件)` 的长度，包含了 `\r\n`、引号、Unicode 转义与 envelope 键名。按**消息正文文本**重算：

| 内容 | 字符 | 占比 | 条数 | 均字符 |
|---|---|---|---|---|
| **tool/result** | **1,274,982** | **92.8%** | 230 | 5,543 |
| assistant/message | 66,663 | 4.9% | 100 | **666** |
| user/message（人类输入） | 27,496 | 2.0% | 17 | 1,617 |
| system/message | 5,231 | 0.4% | 1 | 5,231 |
| **合计** | **1,374,372** | 100% | | |

（v4 中的 "3,359,804 / 77.1%" 应以此表替换。**相对结论不变且更强：工具结果占 92.8%，assistant 正文平均仅 666 字符，人类输入占 2.0%**。）

**prompt 就是工具输出**：会话峰值请求 `seq=691` 的 usage 为 `input=2,074 / cacheRead=435,968 / total=438,541`。1,374,372 字符 ÷ 438,541 token ≈ **3.1 字符/token**。

## 三、膨胀的三个具体来源

### 1. 目录递归列举（信息密度最低，却最占地方）

8 条 >20K 字符的结果合计 321,564 字符（占全部 **25.2%**），其中 **4 条是 `Get-ChildItem -Recurse` 目录树**，每条都被工具上限截断在**恰好 50,000 字符**：

```
50000 chars  pwsh  Get-ChildItem -Path "F:\maiyata\saas\desktop\src" -Recurse -File -Include *.cs,*.xaml | ...
50000 chars  pwsh  Get-ChildItem -Path "F:\JQKJ\src\Collector\GenCollector","F:\JQKJ\src\Frontend\..." | ...
49976 chars  pwsh  Get-ChildItem -Path "F:\JQKJ" -Depth 2 | Select-Object FullName, Length, LastWriteTime | ...
49910 chars  pwsh  Get-ChildItem -Path "F:\maiyata\saas" -Recurse -Depth 3 | ...
```

4 × 50K = 200,000 字符 ≈ **占全部工具输出的 15.7%**，而它们只是文件名清单——**用 `glob` 计数即可替代**。

### 2. 整文件读取（126 次 / 123 个不同文件）

- 涉及 **123 个不同文件**，重复读取仅 2 个文件、3 次调用、浪费 15,396 字符（**仅占 read 的 3.0%**）——**重复劳动不是问题，"广度"才是问题**；
- **只有 32.5%（41/126）的读取使用了 `offset`/`limit` 分页**，其余为整文件读入；
- 单次最大 48,518 字符（`TrendMonitorView.xaml.cs`），turn 5 的 17 次读取平均 **16,459 字符/次**（大文件集中区）。

### 3. 检索几乎没用（grep 4 次 vs read 126 次）

工具使用比 **31.5 : 1**。定位文件靠"整文件读入后肉眼找"，而不是"grep 命中行 → 按窗口读"。这是 126 次读取的直接成因。

## 四、工作区边界被突破（46.8% 的读取在 F:\JQKJ 之外）

126 次 read 的目录分布：

| 目录 | 次数 |
|---|---|
| F:\JQKJ\src\Collector | 22 |
| **F:\maiyata\saas\collector** | **21** |
| **F:\maiyata\saas\desktop** | **17** |
| **C:\Users\admin\.claude**（含 plugins/skills 缓存） | **17** |
| F:\JQKJ\docs\architecture | 9 |
| F:\JQKJ\docs\ai-workspace | 8 |
| F:\JQKJ\tests\GenCollector.Tests | 6 |
| F:\JQKJ\src\Frontend | 4 |
| 其余（superpowers 3、LnkCollector 2、AppData 2、maiyata\deploy 2、.harness\tasks 2、根 md 2） | 20 |

**工作区外合计 59 次 = 46.8%**（F:\maiyata 40 + `~/.claude` 17 + AppData 2）。其中读入 `.claude/plugins/cache/.../writing-skills` 单条 25,899 字符——这类外部配置缓存与当前工程任务无关，却永久占据上下文。

## 五、轮次级膨胀曲线

| turn | 调用 | read | 新增字符 | 累计字符 | 主要工具 |
|---|---|---|---|---|---|
| 1 | 65 | **51** | **474,737** | 474,737 | read:51, glob:6, pwsh:4 |
| 2 | 30 | 25 | 194,516 | 669,253 | read:25, glob:4 |
| 5 | 18 | 17 | **279,826** | 949,079 | read:17（均 16.5K） |
| 7 | 17 | 7 | 8,768 | 957,847 | read:7, todo_write:4 |
| 8 | 5 | 2 | 8,177 | 966,024 | glob:3, read:2 |
| 9 | 9 | 2 | 38,210 | 1,004,234 | pwsh:5, todo_write:2 |
| 10 | 31 | 18 | 250,002 | 1,254,236 | read:18, pwsh:9, write:3 |
| 11 | 3 | 0 | 451 | 1,254,687 | todo_write:2, pwsh:1 |
| 12 | 11 | 4 | 20,295 | 1,274,982 | read:4, grep:4, pwsh:2 |

**turn 1+2+5 = 949,079 字符 = 全部的 74.4%**。turn 1 单轮 51 次读取就吃掉 47 万字符（≈150K token）——这正是"探索阶段全量读入"的代价。

## 六、修剪器是"事后补救"，不是解法

- 41 次 prune 共释放 **172,512 token**，被修剪的原始字符 688,020 = **发出总量的 54.0%**；
- 但修剪发生在**内容已经进入上下文之后**：在修剪前的每一步请求里，这些字符都在 prompt 中计费、都在破坏缓存前缀的可复用性；
- 触发点：turn 10 被用户中断（`turn/end: interrupted`）→ 会话 resume（seq 696-699）→ 紧接着 seq 700-780 连续 41 次 prune。当时 `contextWindow` 仍是 **1048576**（阈值 838,861），**并非压力触发，而是 resume 时的主动压缩**。

**结论：54% 的工具输出是"先塞进去、再剪掉"，必须在发出时控制，不能依赖 pruner。**

### 附：会话期间上下文窗口被改过 3 次（解释了为何能涨到 43.8 万）

| seq | 时间点 | contextWindow | 压缩阈值(×0.8) |
|---|---|---|---|
| 21 | 会话开始 | 262144 | 209,715 |
| 202 | 中途 resume | **1048576**（虚报值） | **838,861** |
| 785 | 再次 resume | 524288（按官方 wiki 更正） | 419,430 |

窗口虚报 2 倍使压缩阈值抬到 83.9 万，prompt 因此长到 43.8 万才被动处理——与 v4 报告一致，属已修复项。

## 七、token 估算偏差（影响阈值换算，必须知道）

DSH token meter 用 **4 字符/token** 启发式（`dsh-compaction-basic` 开发备注亦承认"对 CJK 文本与 JSON schema 定价偏低"），而本会话实测为 **3.1 字符/token**：

```
meter 估算 = 1,374,372 / 4      = 343,593 token
端点实测   = 438,541 token
低估比例   = 438,541 / 343,593 ≈ 1.28 倍
```

因此 **`thresholdRatio × contextWindow` 得到的是 meter token，真实 prompt 约为其 1.28 倍**。整改方案中 agnes 取 `0.2`（meter 105K）→ 真实约 **135K token**；若要硬性把真实 prompt 压在 ~105K，应取 `0.15`。

## 八、优化措施（按杠杆排序，全部有数据支撑）

| # | 措施 | 针对的证据 | 预计收益 |
|---|---|---|---|
| 0 | **精确检索工具（根因措施，已交付）**：`jqkj-search doc/sym/outline/find` 替代整文件读取与目录列举 | 126 次 read（占 74.6%）、4 次 grep 零命中、4×50K 目录树 | 文档检索子任务 **413,998 → ~8,500 字符（48.7×）**；详见 `docs/reports/2026-09-20-precise-search-tooling.md` |
| 1 | **探索性读取下沉 subagent**：把"找出相关文件"这类工作交给 subagent，主上下文只收摘要 | turn 1 的 51 次 read = 474,737 字符 | 单此项可砍掉主上下文约 **35%** 的工具体积 |
| 2 | **禁止目录递归列举**：`Get-ChildItem -Recurse` 改为 `glob` + 计数 | 4 条 50K 字符目录树 = 15.7% | 减少 ~200K 字符 |
| 3 | **检索优先**：先 `grep`/`glob` 定位，再按 `offset`/`limit` 读窗口；单次读 ≤400 行 | grep:read = 4:126；仅 32.5% 用分页 | 直接削减读取次数与单次体积 |
| 4 | **工作区边界**：跨仓库/外部配置目录（F:\maiyata、`~/.claude`、AppData）读取需显式授权 | 46.8% 的读取在工作区外 | 减少 ~47% 的读取次数 |
| 5 | **每轮工具输出预算**：单 turn 新增工具文本 ≤100K 字符（≈32K token），超出转 subagent | turn 1/2/5/10 单轮 19-47 万字符 | 抑制轮次级爆炸 |
| 6 | **压缩阈值下调**（已应用，agnes 0.2） | 峰值 prompt 438K | 最坏情况 prompt 从 43.8 万降到 ~13.5 万（真实 token） |
| 7 | **不依赖 pruner 兜底** | 54% 的发出内容最终被剪 | 避免"先塞后剪"的双重代价 |

### 建议新增规则（拟入 TASK-032，需架构师审批）

> **铁律 15「工具输出纪律」**
> 1. 读取文件必须分页（`limit` ≤ 400 行）；禁止整文件读入 >64KB 的文件。
> 2. 定位优先用 `grep`/`glob`；禁止用整文件读入代替检索。
> 3. 禁止把目录递归列举结果放入上下文（改用 `glob` 计数或落盘后按需查看）。
> 4. 跨工作区路径（其他仓库、用户级配置目录）的读取需在任务卡中显式授权。
> 5. 探索性检索优先委派 subagent，主上下文只接收结论摘要。
> 6. 单轮新增工具输出 >100K 字符时，必须改为委派或先落盘再分段读取。

## 九、复现命令

```powershell
# 事件计数（230 = 189 + 41 的验证）
python "$env:TEMP\probe_tools.py"      # tool/call=189, tool/result=230, prune=41
# 按工具拆分与原始/最终可见体积
python "$env:TEMP\raw_tools.py"        # read 160 条/951,582 字符/34 条被修剪
# read 去重、分页率、目录分布
python "$env:TEMP\read_dedup.py"
# 轮次膨胀曲线
python "$env:TEMP\growth.py"
# 窗口变更与 prune 触发链
python "$env:TEMP\probe_ctx.py"; python "$env:TEMP\probe_trigger.py"
```

（脚本位于 `%TEMP%`，为本次分析的一次性取证工具；如需长期复用应按铁律 14 迁入 `docs/` 对应子目录。）
