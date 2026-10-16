# Agnes 3.0 Flash 延迟整改方案（实施计划）

- 日期：2026-09-20
- 依据：`docs/reports/2026-09-20-agnes-3.0-flash-slow-diagnosis.md`（v4）
- 目标：把 agnes 会话的 TTFT 从 **均值 69s/步（100 步合计 1.92h）** 降到 **~10s/步量级**，且不牺牲正确性

## 一、机制层根因（已取证）

| # | 事实 | 证据 |
|---|---|---|
| 1 | **压缩触发阈值默认是窗口的 80%** | `dsh-compaction-basic/lib/index.js:15` `DEFAULT_THRESHOLD_RATIO = .8`；agnes 512K × 0.8 = **419,430**，实测最大 prompt **438,042** —— 完全吻合 |
| 2 | **prompt 体积 77% 来自工具结果** | transcript 统计：230 条 tool/result = 3,359,804 字符；单条最大 126,279 字符 |
| 3 | **未缓存预填充仅 ~2.2K tok/s** | 317K 未缓存 → 151s；369K → 163s；命中时 33 万 token 仅 18.4s |
| 4 | **34% 的步整段缓存未命中** | 未命中步 TTFT 中位 122.4s；且与步间隔/prune/todo/inbox 均无关 |
| 5 | 工具结果修剪器**已挂载但默认宽松** | `dsh-base/cordis.patch.yml:394` `tool-result-pruner: thresholdChars 8192 / head 4096 / tail 1024`，且**仅在压缩触发后才运行** |

**推论**：阈值 0.8 让上下文长到 33~44 万 token 才压缩 → 此时一次 miss 就是 100~176s。降低 agnes 的阈值 + 收紧修剪 + 从源头控制工具输出，三者叠加才能治本。

## 二、改动清单

### A0. 精确检索工具（根因措施，已交付 2026-09-20）

> 优先级高于本节的补丁类措施：压缩阈值只是**止血**（限制最坏情况），精确检索才是**根因修复**
> （让 agent 不必把 5,000-16,000 字符的文件整篇塞进上下文）。详见
> `docs/reports/2026-09-20-precise-search-tooling.md`。

已交付：`docs/ai-workspace/tools/jqkj-search/`（`jqkj_search.py` + `jqkj-search.cmd` + `README.md`；
`doc` 概念级文档检索 / `sym` 符号定义与引用 / `outline` 结构概览 / `find` 路径检索 / `index` 增量索引；
索引 `.tools/search/index.db` 为构建产物，已在 `.gitignore` 覆盖范围内）。

实测：文档检索子任务 **413,998 → ~8,500 字符（48.7×）**；`sym CollectorEngine` 用 157 字符替代读 5,988 字符文件；
`find "**/*.csproj"` 用 677 字符替代 50,000 字符目录树。

采纳方式：并入下方 B 项规则卡条款（检索优先、禁止目录递归列举、读取必须分页）。

### A. DSH profile 补丁（用户级配置，可逆）

文件（当前均为空数组 `[]`）：
- `C:\Users\admin\.dsh\profiles\web\cordis.patch.yml`
- `C:\Users\admin\.dsh\profiles\headless\cordis.patch.yml`（项目派发器 `dsh --profile headless` 使用）

内容（**补丁按行整体替换 `config`，故必须复述全部键**）：

```yaml
# Agnes 3.0 Flash 延迟整改：把压缩阈值从窗口 80% 降到 agnes 专属 20%，
# 使每步 prompt 稳定在 ~7-10 万 token（原 33-44 万），miss 成本从 ~150s 降到 ~30-48s。
- id: compaction-basic
  config:
    thresholdRatio: 0.8          # 其余模型保持 DSH 默认
    retainRatio: 0.16
    modelPolicies:
      - provider: agnes
        model: agnes-3.0-flash
        thresholdRatio: 0.2      # 524288 × 0.2 = 104,857 触发压缩
        retainTokens: 32768      # 逐字保留近期 32K（必须 < 阈值）

# 【可选，本次未应用】工具结果修剪：默认 8192/4096/1024 偏宽松，
# 如需进一步压缩体积可收紧到 6144/3072/768。仅影响压缩触发后的超大结果；
# 原文仍保留在会话日志中可回放。
# - id: tool-result-pruner
#   config:
#     thresholdChars: 6144
#     headChars: 3072
#     tailChars: 768
```

要点：
- `retainTokens` 必须小于该模型解析后的阈值（78,643）——32,768 合规；两者同时写 `retainRatio` 会加载期报错。
- 全局 `thresholdRatio` 保持 0.8，**只有 agnes 走 0.15**，不影响 doubao/minimax/openrouter。
- 桌面 profile（`profiles/desktop/cordis.patch.yml`）已有自定义内容，如需同样生效需单独追加。

### B. 项目规则卡（仓库侧，需架构师审批）

新增卡 `.harness/tasks/active/TASK-032-tool-output-discipline.yaml`，`allow_write` 覆盖 `AGENTS.md`、`docs/ai-workspace/rules/engineering-rules.mdc`、`docs/ai-workspace/rules/lessons-learned.md`。

拟新增规则（铁律 15「工具输出纪律」草案，条款由 `docs/reports/2026-09-20-tool-result-context-bloat-analysis.md` 的实测数据支撑）：

> 1. 读取文件必须分页（`limit` ≤ 400 行）；禁止整文件读入 >64KB 的文件。
> 2. 定位优先用 `grep`/`glob`；禁止用整文件读入代替检索（实测 grep:read = 4:126）。
> 3. 禁止把目录递归列举结果放入上下文（实测 4 条 `Get-ChildItem -Recurse` = 20 万字符 = 全部工具输出的 15.7%）。
> 4. 跨工作区路径（其他仓库、用户级配置目录如 `~/.claude`）的读取需在任务卡中显式授权（实测 46.8% 的读取在工作区外）。
> 5. 探索性检索优先委派 subagent，主上下文只接收结论摘要（实测 turn 1 单轮 51 次 read = 47.5 万字符）。
> 6. 单轮新增工具输出 >100K 字符时必须改为委派或先落盘再分段读取；长任务（预计 >30 步）优先用缓存稳健的 provider（doubao/minimax），agnes 仅用于小上下文任务或已按本卡配置的会话。

验收：`python .harness/scripts/validate-task-card.py .harness/tasks/active/TASK-032-tool-output-discipline.yaml` 通过；门禁 4 项按卡模板。

### C. 供应商反馈（持证提交）

要点（附 v4 报告第四节数据）：
1. 未缓存预填充 ~2.2K tok/s，而官方榜输出速度 252.7 tok/s —— 输入侧与输出侧能力严重不对称；
2. 34% 的请求出现整段前缀未命中（同会话密集连续请求，间隔中位 0.0s），仅开头 ~6.4K 命中；
3. 缓存为异步写入：首次请求不命中，间隔 <5s 的重复请求仍 miss（易误导接入方）；
4. 流式请求出现 HTTP 500 与 `stream idle timeout`（DSH transcript 5 次重试记录）。

### D. 验证口径（改完必须量）

对比同一类任务的 `.dsh/storages/session_projcache/sessions/<id>.json`：

| 指标 | 现状（d503d810） | 目标 |
|---|---|---|
| `sessionStats.ttftMs / ttftSteps` | 67.5s | **≤25s**（受端点 miss 地板限制，见下） |
| prompt 中位数 | 328,795 | **≤100,000** |
| 全量 miss 步占比 | 41% | ≤41%（**端点侧决定，与体积无关**；体积下降只降低每次 miss 成本） |
| TTFT 合计 | 6,896s | **≤3,300s**（地板约 2,150s，见下） |
| `contextPressure.surfaceTokens` | 188,117 | ≤90,000 |

复算脚本（transcript 逐请求 A/B/TTFT）：见 v4 报告第七节 `calc_prompts.py`。

## 三、预期收益（已用实测校准，见 ADR-0005）

以 100 步会话、**实测 miss 率 41%**、命中步 TTFT 中位 21.9s（含排队/首 token 开销）、未缓存预填充 2.2K tok/s 计。

**重要换算**：DSH token meter 用 4 字符/token 启发式，而实测为 **3.1 字符/token**（`1,374,372 字符 ÷ 438,541 真实 token`），即 **真实 prompt ≈ meter 估算 × 1.28**。因此 `thresholdRatio × contextWindow` 得到的是 meter token：

| 方案 | meter 峰值 | 真实峰值 | 单次 miss | 基线 100 步 | 压缩开销 | 100 步合计 |
|---|---|---|---|---|---|---|
| 现状（0.8） | 419K | 537K | 151s | 7,495s | 318s | **7,813s**（模型）／6,896s（实测，误差 13%） |
| 恢复到 0.7 | 367K | 470K | 132s | 6,720s | 280s | **7,000s** |
| 折中 0.5 | 262K | 336K | 95s | 5,169s | 408s | 5,577s |
| **本次（0.2）** | 105K | **134K** | **38s** | 2,843s | 453s | **3,296s** |
| 0.2 + 检索工具（已交付） | 105K | 134K | 38s | 2,843s | ~190s | **~3,030s** |

**收益上界（重要）**：41% 的 miss 由**端点后端不一致**造成——同一 turn 内、间隔 <5s、前缀相同，
一部分后端返回 `cacheRead=383,488/392,448`（缓存整个会话前缀），另一部分只返回 `6,400/7,936`
（仅共享系统+工具块）；且 miss 状态黏性 63.4%，**与 prompt 规模无关（r=-0.035）**。
因此 **即使 prompt 降到 0，TTFT 地板仍约 2,150s**（100 步 × 21.9s 命中开销）。
0.2 已接近当前端点条件下的可达下限；进一步收益必须来自端点侧修复。

代价：压缩更频繁（每次压缩 = 一次摘要模型调用，且使该点之后缓存失效）。实测 0.2 下约 **4.6 次压缩/100 步**
（vs 0.7 的约 1 次），额外开销约 **+173s**；而每次 miss 因体积下降省下 94s × 41 步 ≈ **3,854s**，代价可忽略。
**实测 turn 1 单轮新增 47.5 万字符（≈118K meter token）就会一次性冲破 105K 阈值**，因此 B 项规则卡不是可选项
——不控制每轮新增体积，压缩次数会失控。

**决策**：阈值**保持 0.2，不恢复到 0.7**（恢复会多花 3,704s 且命中率不变）。依据、取证与复审条件见
`docs/architecture/adr/ADR-0005-Compaction-Threshold-Keep-0.2-Over-0.7.md`。


调参提示：若要把**真实** prompt 硬压在 ~105K，`thresholdRatio` 应取 `0.15`（105K ÷ 1.28）；当前取 0.2 对应真实 ~135K。

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| 补丁 YAML 写错导致 DSH 启动失败 | 改前备份 `cordis.patch.yml`；`python -c "import yaml;yaml.safe_load(open(p))"` 语法校验；回滚 = 恢复为 `[]` |
| 阈值过低导致频繁压缩、丢失细节 | 先取 0.15，按第二节 D 口径实测；不达标再调 0.2/0.25 |
| `retainTokens ≥ 阈值` 加载期报错 | 已核算：32,768 < 78,643 |
| 规则卡改动受保护路径 | 走卡 + `[APPROVED-BY]` 已作废，须卡内 `approver` 非空且 `allow_write` 覆盖 |

## 五、执行记录（2026-09-20）

| 步骤 | 状态 | 证据 |
|---|---|---|
| A. 写入 web + headless 补丁（阈值 0.2，未动 pruner） | ✅ 已应用 | `C:\Users\admin\.dsh\profiles\{web,headless}\cordis.patch.yml` |
| 备份 | ✅ | 同目录 `cordis.patch.yml.bak-20260920-065914`（217B，原为空 `[]`） |
| YAML 结构 + 策略约束校验 | ✅ PASS | 5 项检查全 OK；agnes 触发点 = floor(524288 × 0.2) = **104,857**；`retainTokens 32,768 < 104,857`；未同时给互斥的 `retainRatio` |
| profile 加载校验（fail-fast） | ✅ PASS | `dsh --profile web --help` / `--profile headless --help` 均 exit=0、无配置报错 |
| B. TASK-032 规则卡 | ⬜ 待提交 | 需架构师审批（受保护路径） |
| C. 供应商反馈稿 | ⬜ 待发出 | 证据见 v4 报告第四节 |
| D. 收紧 tool-result-pruner（可选） | ⬜ 未应用 | 按"保守"选择保留 DSH 默认 8192/4096/1024；YAML 见第二节注释 |

**生效条件**：补丁在 DSH 进程启动时加载——**当前正在运行的会话仍是旧策略，需重启 DSH 后生效**。

**回滚**：`Copy-Item cordis.patch.yml.bak-20260920-065914 cordis.patch.yml -Force`（或把文件内容改回 `[]`）。

## 六、后续动作

1. 重启 DSH → 跑一个可比任务 → 按第二节 D 口径取数（目标 TTFT/步 ≤15s）；
2. 未达标则把 agnes 阈值在 0.15~0.25 区间再调，或追加 pruner 收紧；
3. 提交 TASK-032 规则卡（工具输出纪律 + 模型选型）；
4. 发出供应商反馈稿。
