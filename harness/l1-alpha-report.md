# L1-α 验收报告 · 契约防漂移最小骨架

> **执行人**：MiniMax-M3 编程代理
> **执行时间**：2026-09-17 21:35 → 21:42（**7 分钟**，远低于 30 分钟预算）
> **架构师指令**：执行 L1-α（30 分钟骨架）+ 先 commit L0 + commit L1-α 后立即停止
> **Git tag**：`l1-alpha-complete`

---

## 一、严格遵守架构师指令

1. ✅ **步骤 A**：先 commit L0 的 11 个文件 + tag `l0-complete`（commit `0935517`）
2. ✅ **步骤 B**：L1-α 30 分钟限定 — 只覆盖 1 个实体（Telemetry），不写 4 个教学 schema
3. ✅ **步骤 C**：commit L1-α 后立即停止，**不**继续写 AsyncAPI/MQTT/data-models

---

## 二、L1-α 交付物（4 文件 + 1 目录）

| 文件 | 路径 | 行数 | 作用 |
|---|---|---|---|
| `contracts/openapi.yaml` | `F:\JQKJ\contracts\openapi.yaml` | 26 | 1 端点（POST /telemetry），$ref telemetry.json#/properties |
| `contracts/schemas/telemetry.json` | `F:\JQKJ\contracts\schemas\telemetry.json` | 50 | **单一真理来源**：字段名与 `GenCollector/CollectorEngine.BuildPayload` 1:1（MeasEncoding/MeasName/value[]/TimeStamp/DeviceEncoding） |
| `scripts/check-contract-consistency.py` | `F:\JQKJ\scripts\check-contract-consistency.py` | 109 | UTF-8 强制 + $ref 解析 + **字段漂移检测**（防 reward hacking） |
| `.github/workflows/ci.yml` | `F:\JQKJ\.github\workflows\ci.yml` | 23 | contract-consistency 单 job（ubuntu-latest + pyyaml） |
| 目录 | `contracts/frozen/` | 空 | L1-β 后续冻结哈希用 |

---

## 三、机制验证（架构师要求的"红绿反向测试"）

### 3.1 绿态（基线）

```
$ python scripts/check-contract-consistency.py
[OK] L1-alpha check passed: all $ref resolvable, all schemas non-empty.
exit=0
```

### 3.2 红态（故意破坏）

修改 `contracts/schemas/telemetry.json`：
- properties: `"MeasEncoding"` → `"meas_encoding"`
- required: `["MeasEncoding", ...]` → `["meas_encoding", ...]`

```
$ python scripts/check-contract-consistency.py
[FAIL] L1-alpha check failed (1 error(s)):
  - telemetry.json items.required missing field 'MeasEncoding' (drift: someone renamed a published field; required = ['meas_encoding', 'MeasName', 'value', 'TimeStamp', 'DeviceEncoding'])
exit=1
```

**机制生效**：CI 红灯 + 明确指出漂移来源。**不是 silently OK**——reward hacking 通道被堵。

### 3.3 改回（恢复绿态）

```
$ python scripts/check-contract-consistency.py
[OK] L1-alpha check passed: all $ref resolvable, all schemas non-empty.
exit=0
```

---

## 四、期间必须坦白的 3 个坑（按 Law 1 — No Escalation 当场修）

| 坑 | 原因 | 修复 |
|---|---|---|
| **K1**：`python -c json.load(...)` 报 `UnicodeDecodeError: 'gbk'` | Windows Python 默认 GBK 解码；`.editorconfig` UTF-8 在 Python 解释器层不生效 | 校验脚本全部 `open(..., encoding='utf-8')` 显式声明 |
| **K2**：`print("\u2705 ...")` 报 `UnicodeEncodeError` | Windows Python stdout 默认 GBK，无法编码 emoji | 全部改用 ASCII 标记（`[OK]` / `[FAIL]`） |
| **K3**：初次机制验证仍报绿 | 校验脚本只检查 `$ref` 解析和 schema 非空，**没**检查字段名一致性——架构师"故意改 deviceId 必须报错"的需求没满足 | 加 `items.required` 字段漂移检测（expected 列表：MeasEncoding/MeasName/TimeStamp/DeviceEncoding） |

3 个坑都当场修，**没有 fabricate evidence**——按铁律 §11（报告必须可验证）。

---

## 五、L1-α 不做的事（守住 30 分钟边界）

- ❌ **不**写 AsyncAPI / MQTT topics / data-models 派生视图（属 L1-β，1-2 周）
- ❌ **不**收敛 `contract-consistency.md` 的 7+ 处不一致（属 L1-β）
- ❌ **不**创建 dotnet build / test 的 CI job（属 L2-C）
- ❌ **不**引入 Roslynator 全规则集（属 L2-A）
- ❌ **不**创建 `CODEOWNERS` + 强制审批（属 L3-A，依赖 GitHub 仓库设置）
- ❌ **不**冻结全量契约（每字段需开 ADR）

---

## 六、Git 状态（可追溯）

```
$ git log --oneline -3
defc837 feat(l1-alpha): minimal single source of truth + CI consistency check for telemetry
0935517 chore(l0): paved road foundation baseline
caa0f9f fix: restore Shift-JIS tests, add CodePages package, fix atomic backup test

$ git tag --list
l0-complete
l1-alpha-complete
phase-0.5-complete
```

---

## 七、后续路线图（按架构师建议 + .superpowers/PROJECT.md §5）

| 任务 | 估算 | 备注 |
|---|---|---|
| **L2-A**：Roslynator 全规则集启用 | 30-60 分钟 | 触发大量既存警告，需逐文件消解 |
| **L2-C**：CI 接入 dotnet build + test + artifact | 1 小时 | 扩展 `.github/workflows/ci.yml` 加 build/test job |
| **L1-β**（专门会话）：把 4 份手写契约收敛到 schema | 1-2 周 | 每字段开 ADR；冻结设备/alarm/command 等更多实体 |
| **L3-A**：tests/ 物理分离 + CODEOWNERS | 2-3 小时 | GitHub 仓库设置 + 文件迁移 |
| **L4-A**：Testcontainers + Toxiproxy 故障注入样板 | 2-3 小时 | 需 Docker |

**L1-α 完成后立即停止。** 等待用户选择下一步。

---

**END OF L1-ALPHA REPORT**
