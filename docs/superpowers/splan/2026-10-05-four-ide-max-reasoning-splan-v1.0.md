# 四 IDE 统一最高思考档实施计划 v1.1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**前置核对结论（2026-10-05 只读核对，未改配置）：** 第一家 22 条长度全齐、思考深度 0 条，只补思考档；第二家 22 条中 6 条长度缺失、思考深度 0 条，补 6 条长度加全部思考档；第三家全局已是最高档，只补一条模型目录与一条服务商通道；第四家只出确认单。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已审批规格，把四工具的自定义模型全部置为最高思考档并补齐上下文长度，生成上限不动，待审批后执行。

**Architecture:** 先备份再改配置：脚本化改两份自定义清单，手工补 Codex 目录与供应商通道，Qoder 只出确认单，最后用复核脚本验收，不通过即回退。

**Tech Stack:** Python 3（配置改写与复核脚本）、PowerShell 7（备份与校验）、Git feature 分支 + PR。

**对应规格：** `docs/superpowers/spec/2026-10-05-four-ide-max-reasoning-ctx-spec-v1.0.md`

---

### Task 1：备份全部目标文件

**Files:**
- Read: `C:\Users\admin\.workbuddy\models.json`
- Read: `C:\Users\admin\.codebuddy\models.json`
- Read: `C:\Users\admin\.codex\config.toml`
- Read: `C:\Users\admin\.codex\mmx-model-catalog.json`

- [ ] **Step 1: 创建特性分支**

Run: `git -C F:\JQKJ checkout -b feat/four-ide-max-reasoning`
Expected: `Switched to a new branch 'feat/four-ide-max-reasoning'`

- [ ] **Step 2: 执行备份**

Run: `powershell -NoProfile -Command "$ts=Get-Date -Format 'yyyyMMdd-HHmm'; foreach($f in @('C:\Users\admin\.workbuddy\models.json','C:\Users\admin\.codebuddy\models.json','C:\Users\admin\.codex\config.toml','C:\Users\admin\.codex\mmx-model-catalog.json')){ $d=Split-Path $f; Copy-Item -LiteralPath $f -Destination (Join-Path $d (\"backup-\"+$ts+\"-\"+[IO.Path]::GetFileName($f))) -Force }; Get-ChildItem C:\Users\admin\.workbuddy,C:\Users\admin\.codebuddy,C:\Users\admin\.codex -Filter 'backup-*' | Select-Object FullName"`
Expected: 列出 4 个 backup-* 文件，无报错。

- [ ] **Step 3: 记录备份清单**

在 PR 描述中列出 4 个备份文件名，本任务结束。

### Task 2：WorkBuddy 自定义清单补最高思考档（长度只复核）

**Files:**
- Modify: `C:\Users\admin\.workbuddy\models.json`

规则：有 max 用 max、无 max 用 high；summary 统一 auto；纯推理模型加 onlyReasoning；密钥与地址原样保留，不在任何文档中抄录。

- [ ] **Step 1: 写入改写脚本**

Create: `C:\Users\admin\AppData\Local\Temp\opencode\apply_wb.py`

```python
import json
P = r'C:\Users\admin\.workbuddy\models.json'
data = json.load(open(P, encoding='utf-8'))
items = data if isinstance(data, list) else data['models']
MAX_OK = {'deepseek-v4-pro', 'deepseek-flash', 'deepseek-v4-1-flash-260910'}
for m in items:
    mid = str(m.get('id', ''))
    effort = 'max' if (mid in MAX_OK or 'deepseek' in mid.lower()) else 'high'
    m['reasoning'] = {'effort': effort, 'summary': 'auto'}
    if mid in ('deepseek-v4-pro',):
        m['onlyReasoning'] = True
    if 'temperature' not in m:
        m['temperature'] = 1
json.dump(data, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('updated', len(items))
```

- [ ] **Step 2: 试运行前先校验长度基线**

Run: `python3 C:\Users\admin\AppData\Local\Temp\opencode\ctx_check.py`
Expected: WORKBUDDY 每行都有 in=/out= 数字，无 None。

- [ ] **Step 3: 执行改写**

Run: `python3 C:\Users\admin\AppData\Local\Temp\opencode\apply_wb.py`
Expected: `updated 22`（以实际条数为准，本次核对为 22），无报错。

- [ ] **Step 4: 复核无 none/off 且密钥未变**

Run: `powershell -NoProfile -Command "$t=Get-Content -LiteralPath 'C:\Users\admin\.workbuddy\models.json' -Raw; if($t -match '\"effort\":\s*\"none\"'){exit 1}; if($t -notmatch '\"effort\":\s*\"(max|high)\"'){exit 1}; Write-Output 'WB-OK'"`
Expected: `WB-OK`

### Task 3：CodeBuddy 补长度缺失 + 全部最高思考档

**Files:**
- Modify: `C:\Users\admin\.codebuddy\models.json`

长度基准：M2.7 系 204800；千问版 GLM 200000；其余缺失项 1000000；输出上限保持大上限不动。

- [ ] **Step 1: 写入改写脚本**

Create: `C:\Users\admin\AppData\Local\Temp\opencode\apply_cb.py`

```python
import json
P = r'C:\Users\admin\.codebuddy\models.json'
d = json.load(open(P, encoding='utf-8'))
items = d['models']
FILL_IN = {
    'MiniMax-M2.5-highspeed': 204800,
    'MiniMax-M2.7': 204800,
    'MiniMax-M3': 1000000,
    'ark-code-latest': 1000000,
    'doubao-seed-2.0-mini': 1000000,
    'doubao-seedance-2.5': 1000000,
}
FILL_OUT = 131072
for m in items:
    mid = str(m.get('id', ''))
    if m.get('maxInputTokens') is None:
        m['maxInputTokens'] = FILL_IN.get(mid, 1000000)
    if m.get('maxOutputTokens') is None:
        m['maxOutputTokens'] = FILL_OUT
    effort = 'max' if 'deepseek' in mid.lower() else 'high'
    m['reasoning'] = {'effort': effort, 'summary': 'auto'}
    if 'temperature' not in m:
        m['temperature'] = 1
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('updated', len(items))
```

- [ ] **Step 2: 执行改写**

Run: `python3 C:\Users\admin\AppData\Local\Temp\opencode\apply_cb.py`
Expected: `updated 22`（本次核对为 22），无报错。

- [ ] **Step 3: 复核缺失归零**

Run: `python3 C:\Users\admin\AppData\Local\Temp\opencode\ctx_check.py`
Expected: CODEBUDDY 段无 `None`，且 M2.7 两行是 204800，GLM 千问侧是 200000。

### Task 4：Codex 补目录条目与千问通道（保持 high）

**Files:**
- Modify: `C:\Users\admin\.codex\mmx-model-catalog.json`
- Modify: `C:\Users\admin\.codex\config.toml`

- [ ] **Step 1: 确认全局强度仍为 high**

Run: `powershell -NoProfile -Command "Select-String -LiteralPath 'C:\Users\admin\.codex\config.toml' -Pattern 'model_reasoning_effort'"`
Expected: 命中 `model_reasoning_effort = "high"` 一行。

- [ ] **Step 2: 补 deepseek-v4-pro 目录条目**

在 `mmx-model-catalog.json` 的 models 数组追加（密钥不入档，上下文与档位如下）：

```json
{
  "slug": "deepseek-v4-pro",
  "display_name": "DeepSeek-V4-Pro",
  "description": "Most capable frontier agentic coding model.",
  "default_reasoning_level": "high",
  "supported_reasoning_levels": [{"effort": "low"}, {"effort": "high"}, {"effort": "max"}],
  "context_window": 1048576,
  "max_context_window": 1048576,
  "supported_in_api": true,
  "priority": 2
}
```

- [ ] **Step 3: 新增千问供应商通道（占位写法，密钥复用现有注入）**

在 `config.toml` 追加（密钥值用现有同名注入方式，不把明文写入计划与文档）：

```toml
[model_providers.qianwen]
base_url = "https://token-plan.maas.qianwenaiapi.com/compatible-mode/v1"
name = "千问TokenPlan"
wire_api = "responses"
# experimental_bearer_token 沿用现有密钥注入方式，此处不填明文
```

- [ ] **Step 4: 轻量连通探针（只探通断，不跑问答）**

Run: `powershell -NoProfile -Command "Test-Path 'C:\Users\admin\.codex\mmx-model-catalog.json'"`
Expected: `True`，且上一步 JSON 可被解析（用编辑器或 `python3 -c "import json;json.load(open(r'C:\Users\admin\.codex\mmx-model-catalog.json',encoding='utf-8'));print('CATALOG-OK')"` 输出 `CATALOG-OK`）。

### Task 5：Qoder 对照确认单（不写本地文件）

**Files:**
- Create: `F:\JQKJ\docs\reports\2026-10-05-qoder-max-reasoning-check.md`

- [ ] **Step 1: 建确认单并勾选**

内容仅四列：模型→档位→长度→深入思考开关状态，逐项在工具内确认后打勾，留存截图编号。

- [ ] **Step 2: 不满足则记为阻塞**

若某模型无最高档可选，记为阻塞项，不强行改本地文件。

### Task 6：总验收与提交（不合入主干）

- [ ] **Step 1: 跑总复核**

Run: `python3 C:\Users\admin\AppData\Local\Temp\opencode\ctx_check.py`
Expected: 两份清单均无 `None`；再跑 Task 2 Step 4 的 WB-OK 探针通过。

- [ ] **Step 2: 提交分支并开 PR**

Run: `git -C F:\JQKJ add docs/superpowers/spec/2026-10-05-four-ide-max-reasoning-ctx-spec-v1.0.md docs/superpowers/splan/2026-10-05-four-ide-max-reasoning-splan-v1.0.md docs/reports/2026-10-05-qoder-max-reasoning-check.md && git -C F:\JQKJ status --short`
Expected: 仅显示上述文档变更（配置在用户目录，不进本仓库），然后按仓库规范开 PR 待架构师审核，禁止直推主干。

## 自检记录

- 规格覆盖：G1 对应 Task 2/3/4，G2 对应 Task 2 Step 2 与 Task 3 Step 3，G3 对应 Task 4 Step 1 与 Task 5，G4 对应 Task 4 Step 2/3；
- 占位扫描：无 TBD/TODO，所有脚本为完整可执行内容，密钥均未明文写入；
- 类型一致：effort 取值限定 max/high，长度数字与规格第 3 节一致，204800/200000 未放大。
