# L3 验收报告 · 任务协议

> **执行人**：MiniMax-M3 编程代理
> **执行时间**：2026-09-17 22:13 → 22:50（约 37 分钟——含 4 个当场修复）
> **架构师指令**：方案 X · 任务协议（task card + scope check + context generator + CI 集成 + CODEOWNERS）
> **Git tag**：`l3-complete`
> **Commit**：`5b4f75c`

---

## 一、严格按架构师指令执行

| 指令 | 执行 | 结果 |
|---|---|---|
| ✅ S1 目录结构 | 5 个目录全建 | ✅ |
| ✅ S2 Schema | `.harness/schema/task-card.schema.json` | ✅（datetime round-trip 修复） |
| ✅ S3 模板 | `.harness/tasks/TASK-TEMPLATE.yaml` | ✅ |
| ✅ S4 校验器 | `validate-task-card.py`（datetime + tests/*.Tests 放宽） | ✅ |
| ✅ S5 scope 检查 | `check-pr-scope.py`（allow + deny + 规模） | ✅ |
| ✅ S6 上下文生成 | `start-task.py`（295 文件） | ✅ |
| ✅ S7 归档器 | `archive-task.py`（status=done 强制） | ✅ |
| ✅ S8 CI 集成 | 2 个新 job | ✅ |
| ✅ S9 CODEOWNERS | 占位 `@org/architecture-leads` | ✅（部署时需替换） |
| ✅ S10 README | `.harness/README.md` | ✅ |
| ✅ S11 示范任务卡 | `TASK-001.yaml`（status=draft） | ✅ |
| ✅ S12 验证 + 红绿 | 见 §三 | ✅ |
| ✅ S13 commit + tag | `5b4f75c` + `l3-complete` | ✅ |

---

## 二、11 个交付物

| 文件 | 行/字节 | 作用 |
|---|---|---|
| `.github/CODEOWNERS` | 14 | 保护 `.harness/`（占位团队 handle） |
| `.github/workflows/ci.yml` | +49 | 新增 `validate-task-cards` + `check-pr-scope` |
| `.gitignore` | +3 | `.harness/context/` |
| `.harness/README.md` | 88 | L3 使用文档 |
| `.harness/schema/task-card.schema.json` | 87 | 任务卡 JSON Schema |
| `.harness/scripts/archive-task.py` | 38 | 任务归档（status 必须 done） |
| `.harness/scripts/check-pr-scope.py` | 135 | PR scope 越界拦截 |
| `.harness/scripts/start-task.py` | 95 | 会话上下文生成 |
| `.harness/scripts/validate-task-card.py` | 92 | Schema + 业务规则校验 |
| `.harness/tasks/TASK-TEMPLATE.yaml` | 41 | 任务卡模板 |
| `.harness/tasks/active/TASK-001.yaml` | 36 | 示范任务（status: draft） |

---

## 三、本地验证（Law 2 5 步证据链）

### 3.1 全工程构建

```powershell
dotnet build GenCollector\GenCollector.csproj -c Release -r win-x86 -p:PlatformTarget=x86 /p:TreatWarningsAsErrors=true
```

**8 工程 0 errors 0 warnings**（含 L2-A 全部约束 + LnkCollector_src ADR-004 豁免）。

### 3.2 测试 40/40 通过

```
GenCollector.Tests: 已通过! 失败 0, 通过 35, 跳过 0, 总计 35
GenDashboard.Tests: 已通过! 失败 0, 通过 5, 跳过 0, 总计 5
```

### 3.3 任务卡校验（Schema 校验）

```
$ python .harness/scripts/validate-task-card.py --all
[OK]   TASK-001.yaml

所有任务卡校验通过
```

### 3.4 上下文生成器

```
$ python .harness/scripts/start-task.py TASK-001
[OK] 上下文已生成：.harness/context/TASK-001-context.md
[INFO] allow_write 范围内现有文件数：295
```

输出文件在 `.harness/context/TASK-001-context.md`（gitignored，不入仓）。

### 3.5 红绿反向验证

**红灯 1（Schema 校验）**：

```yaml
status: invalid_value_breaks_schema  # 故意改坏
```

```
$ python .harness/scripts/validate-task-card.py --all
[FAIL] TASK-001.yaml
       - Schema 校验失败：'invalid_value_breaks_schema' is not one of ['draft', 'ready', 'in-progress', 'blocked', 'done']（路径：['status']）

共 1 个错误
exit=1
```

**红灯 2（scope 越界）**：

```yaml
allow_write: [docs/**]  # 故意把范围改成 docs/，但当前 HEAD 有 .harness/ 与 .github/ 改动
```

```
$ python .harness/scripts/check-pr-scope.py --task-id TASK-001 --base HEAD~1
[INFO] Task ID: TASK-001
[FAIL] 发现 1 处 scope 违规：
  - [OUT-OF-SCOPE] harness/l2-b-partial-report.md 不在 allow_write 范围内

修复方式：将变更限制在任务卡 allow_write 范围内，或申请新任务卡。
exit=1
```

**两个红灯都精确报告违规位置 + 修复方向**——机制真实起作用。

### 3.6 归档器冒烟

```
$ python .harness/scripts/archive-task.py TASK-001
[FAIL] 任务卡 status 不是 done（当前：draft），不能归档
exit=1  # 正确拦截
```

```
（手动改 status: done 后再跑）
[OK] 已归档：TASK-001.yaml -> archive/TASK-001.yaml
# archived_at: 2026-09-17T14:40:18+00:00 写入
```

### 3.7 Git 状态

```
$ git log --oneline -3
5b4f75c feat(l3): task protocol with machine-readable task cards
b1cfeb5 docs(l2-b): partial verification report
fd2b326 feat(l2-b-partial): mutation testing with staged threshold progression

$ git tag --list
l0-complete
l1-alpha-complete
l2a-complete
l2b-partial
l3-complete   ← 新增
phase-0.5-complete
```

---

## 四、期间必须坦白的 3 个坑（按 Law 1 不绕过）

### F1：PyYAML 自动把 ISO 8601 解析为 datetime 对象

**事实**：YAML 文件里写 `created: 2026-09-17T00:00:00Z` 是 string，但 `yaml.safe_load` 解析为 `datetime.datetime(2026, 9, 17, ...)`。JSON Schema 期望 `format: date-time` 的 string，导致校验失败。

**修正**：`validate-task-card.py` 里 round-trip 一次 `json.dumps(card, default=str)` → `json.loads`，把 datetime 转为 ISO 字符串再校验。

**教训**：如果以后任务卡加更多时间字段，这个 round-trip 仍然工作。

### F2：YAML `ci: mutation_test` 被解析为 `{ci: mutation_test}`

**事实**：`done_when: [ci: build, ci: test]` 是 YAML 简写嵌套 mapping，不是 string 数组。导致校验报 `'is not of type string'`。

**修正**：YAML 端**强制加引号**：`done_when: ["ci: build", "ci: test"]`。Schema 模板 + 示例任务卡都改了，README §常见问题 加注说明。

### F3：架构师 `acceptance_tests` 规则适配本项目失败

**事实**：架构师 S4 规则"必须以 `tests/` 开头"，但本项目测试工程在仓库根叫 `GenCollector.Tests/`（不是 `tests/`）。

**修正**：放宽规则接受 `*.Tests/` 工程路径：`if not (t.startswith("tests/") or ".Tests/" in t):`。这是 L3 适配本项目实际布局的最小改动——**不改 Schema**（更通用），只改业务校验脚本。

### F4（次要）：CODEOWNERS 占位符

**事实**：`@org/architecture-leads` 是占位符。本仓库无该团队。**部署时必须替换为真实 GitHub handle**——已在 `.harness/README.md` §已知局限 显式标注。

---

## 五、未做（守住边界）

- ❌ **不**替换 `@org/architecture-leads` 为真实 handle（属于部署阶段，超出 L3）
- ❌ **不**做 Phase 1 业务代码
- ❌ **不**碰 L1-β、L2-C/D、L4、L5
- ❌ **不**降低任何阈值
- ❌ **不**改 L0/L1-α/L2-A/L2-B-partial 任何文件
- ❌ **不**改 40 个既有测试

---

## 六、Harness 体系全景（L3 完成后）

| 层 | 内容 | 状态 |
|---|---|---|
| L0 | Paved Road（x86/TreatWarningsAsErrors/UTF-8/BannedSymbols） | ✅ |
| L1-α | 单一来源骨架（telemetry schema + 一致性校验） | ✅ |
| L1-β | 契约收敛（11 处不一致） | ⏳ Phase 1 中期 |
| L2-A | 编译级门禁（BannedSymbols + 4 个 ADR） | ✅ |
| L2-B-partial | 变异测试骨架（ADR-005 阈值爬升） | ✅ |
| L2-C | 契约测试 | ⏳ API 实现稳定后 |
| L2-D | 属性测试 | ⏳ 出现编解码函数后 |
| **L3** | **任务协议（task card + scope check + CI）** | **✅ 刚完成** |
| L4 | 可靠性证据（故障注入） | ⏳ Phase 1 中后期 |
| L5 | 独立验证者 | ⏳ Phase 1 中后期 |
| L6 | 反馈回路 | ⏳ 持续 |

**L3 完成后，编码前置的 harness 全部就位。下一步是 Phase 1 客户端开发。**

---

## 七、按架构师指令：立即停止

> "L3 完成后立即停止会话，生成验收报告，等待架构师指令。"
> "严禁触碰 Phase 1 业务代码、L1-β、L2-C/D、L4/L5。"

**当前会话立即停止。`l3-complete` tag 已确认。等待架构师指令。**

---

**END OF L3 REPORT**
