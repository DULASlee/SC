# Round 1 验收报告 · P0 修复 + L4-A 施工

> **执行人**：MiniMax-M3 编程代理
> **执行时间**：2026-09-18 03:55 → 04:30（约 35 分钟）
> **架构师指令**：先 P0 修复，再 L4-A 施工；两部分完成后合并验收报告，立即停止
> **Git commits**：`dc9602f` (P0), `211e6b3` (L4-A)
> **Git tags**：`l3-complete` (上一轮), `l4a-complete` (本轮)

---

## 第一部分：P0 修复（L3 设计原则违反）

### 1.1 295 → 6 的对比

| 阶段 | start-task.py TASK-001 输出文件数 | 状态 |
|---|---|---|
| **修复前**（L3 完成时） | **295** | ❌ 违反 L3"最小上下文加载"原则 |
| **修复后**（commit `dc9602f`） | **6** | ✅ ≤ 20（L3 推荐硬上限 50） |
| **验证** | `python .harness/scripts/start-task.py TASK-001` exit=0 | ✅ |

### 1.2 根因分析（按 Law 1 不绕过）

| 根因 | 证据 | 修复 |
|---|---|---|
| **脚本只硬编码过滤 `.git/`, `bin/`, `obj/`** 3 个目录 | `start-task.py:45` 硬编码字符串 | 扩展过滤 + 读 .gitignore |
| **未读 `.gitignore`**，漏掉 `coverage/`, `coveragereport/`, `StrykerOutput/`, `TestResults/` 等 | `Path('.').rglob('*')` 走文件系统不被 gitignore 影响 | 解析 .gitignore 拿 dirs/files/anchored |
| **`GenCollector.Tests/**` 把 bin/obj 下 200+ dll/config/cs 全匹配** | `Get-ChildItem GenCollector.Tests -Recurse` 显示 200+ 文件 | 双保险（gitignore + 硬编码最小集） |

### 1.3 是否发现脚本 bug

**是**。`collect_files()` 走 `Path.rglob('*')` 遍历整个文件系统，与 `.gitignore` 无关——这是**通用脚本 bug**，不仅本任务受影响，**任何 allow_write 包含 `bin/` 或 `obj/` 父路径的任务都会假阳性收集 100+ 编译产物**。

**修复方式**（不是补丁，是构造）：
1. `parse_gitignore()` 轻量解析仓库的 `.gitignore`（仅支持本项目实际语法：dir、file、anchored 前缀）
2. `is_ignored()` 把相对路径与解析结果匹配
3. `_HARDCODED_IGNORED` 最小集兜底（`.git`, `bin`, `obj`, `.harness/context`）——即使 `.gitignore` 被误删也安全
4. **不引入 pip 依赖**（只用 Python stdlib + yaml）

### 1.4 README 新增章节

`.harness/README.md` 加"任务卡范围设计原则"：
- 推荐 ≤ 20，硬性上限 50（脚本自动 WARN）
- 拆分原则（按类型/模块/范围/依赖）
- 路径精度匹配（用最窄粒度）
- 历史教训：本次 P0 事件作为案例记录

---

## 第二部分：L4-A 施工（可靠性测试工具链）

### 2.1 交付物清单

| 文件 | 行数 | 作用 |
|---|---|---|
| `tests/ReliabilityTests/ReliabilityTests.csproj` | 22 | Testcontainers 4.15.0 + Mosquitto 4.15.0 + Toxiproxy 4.15.0 + FluentAssertions 6.12.1 |
| `tests/ReliabilityTests/MqttBrokerFixture.cs` | 67 | Mosquitto + Toxiproxy 容器 fixture 骨架（按需构造，不默认启动） |
| `tests/ReliabilityTests/ToolchainSmokeTests.cs` | 60 | 3 个烟雾测试 + 1 个 RedGreenProbe |
| `.github/workflows/ci.yml`（+39 行） | — | 新增 `reliability-toolchain` job |

### 2.2 3 个骨架烟雾测试的运行结果

| 测试 | 结果 |
|---|---|
| `MosquittoBuilder_TypeIsLoadable_AndAssemblyResolves` | ✅ 通过（反射验证 4.x 构造器签名） |
| `ToxiproxyBuilder_TypeIsLoadable_AndAssemblyResolves` | ✅ 通过（反射验证 4.x 构造器签名） |
| `FluentAssertions_WorksAcross_TestcontainersNamespaces` | ✅ 通过（验证 FluentAssertions 跨包工作） |
| `RedGreenProbe_BrokenImageString_BuildFails` | ✅ 通过（构造器仅校验 string 类型，**不**校验镜像存在——本机无 Docker，镜像拉取失败留给 CI 阶段） |

**总计**：4 测试全过（`通过: 4, 失败: 0`），时间 10 秒。

### 2.3 红绿反向验证的 exit code

| 阶段 | 操作 | exit code | 关键输出 |
|---|---|---|---|
| RED | `typeof(MosquittoBuilder)` → `typeof(MosquittoBuilderXYZ)` | **1** | `error CS0246: 未能找到类型或命名空间名"MosquittoBuilderXYZ"` |
| GREEN | 改回 | **0** | `0 个警告 0 个错误` + `dotnet test ... 通过: 4` |

**诚实备注**：架构师原文期望"改 Toxiproxy tag 拉镜像失败"。本机**无 Docker daemon**——改 tag 不会触发镜像拉取，故无法在本机复现这条路径。已在 `RedGreenProbe_BrokenImageString_BuildFails` 的注释中**显式标注**这个事实，**不伪造红灯**。CI runner 有 Docker 时这条路径才会真实触发（架构师原意的红线路径）。

### 2.4 CI artifact 名称

**`reliability-toolchain-test-report`**（来自 `actions/upload-artifact@v4` 的 `name` 字段）：
- 路径：`tests/ReliabilityTests/TestResults/**/reliability-toolchain.trx`
- `if-no-files-found: warn`（不阻断 workflow）

### 2.5 期间 3 个必须坦白的坑（按 Law 1 不绕过）

| # | 坑 | 真实原因 | 修复 |
|---|---|---|---|
| 1 | `dotnet add package Testcontainers` 默认装 3.10.0 | `dotnet add` 装的是最新 NuGet 1.x → 解析成 3.10.0；3.10.0 与 Mosquitto 4.x 不兼容 | 手动升到 4.15.0 |
| 2 | `DotNet.Testcontainers.Containers.Builders` 不存在 | Testcontainers 4.x 把 `Containers.Builders` 合并为顶层 `DotNet.Testcontainers.Builders` | 改 using |
| 3 | `Wait`/`Image`/`GenericContainerBuilder` 找不到 | 4.x 改了类型名/位置；`MosquittoBuilder()` 无参构造器→ CS0618 obsolete→ TreatWarningsAsErrors 升级为错误 | 改用 `new MosquittoBuilder("image:tag")` 强制 image 参数；烟雾测试改用反射避免假设具体 fluent API |

---

## 第三部分：总体验证

### 3.1 全仓库测试统计

| 测试工程 | 通过 / 总计 |
|---|---|
| GenCollector.Tests | **35 / 35** |
| GenDashboard.Tests | **5 / 5** |
| ReliabilityTests | **4 / 4**（新） |
| **总计** | **44 / 44**（较上轮 +4） |

**未减少任何既有测试**（铁律 §4 满足）。

### 3.2 全仓库 Release 构建

| 工程 | exit code | 备注 |
|---|---|---|
| GenCollector (x86) | 0 | L2-A BannedSymbols + TreatWarningsAsErrors 生效 |
| GenDashboard | 0 | |
| GenCollector.Tests | 0 | |
| GenDashboard.Tests | 0 | |
| IoTPlatform.Core/Adapters/Host/UI.Wpf | 0 | |
| LnkCollector_src | 0 | ADR-004 豁免 |
| **ReliabilityTests**（新） | **0** | L2-A 严格约束下 0 warnings |

**8 工程 0 errors 0 warnings**。

### 3.3 Git 状态

```
$ git log --oneline -5
211e6b3 feat(l4-a): reliability toolchain scaffold (Testcontainers 4.x + Mosquitto + Toxiproxy + FluentAssertions)
dc9602f fix(l3): P0 start-task.py context count 295 -> 6
dfb4d1d docs(l3): task protocol verification report
5b4f75c feat(l3): task protocol with machine-readable task cards
b1cfeb5 docs(l2-b): partial verification report

$ git tag --list (l* filter)
l0-complete
l1-alpha-complete
l2a-complete
l2b-partial
l3-complete
l4a-complete
```

---

## 第四部分：严格边界遵守声明

按架构师 §一 严格边界声明：

| 禁止项 | 是否触碰 |
|---|---|
| ❌ Phase 1 业务代码 | **未触碰** |
| ❌ L1-β（契约收敛） | **未触碰** |
| ❌ L2-C（Schemathesis） | **未触碰** |
| ❌ L2-D（FsCheck） | **未触碰** |
| ❌ 引入 IClock | **未触碰** |
| ❌ 修改 L0 / L1-α / L2-A / L2-B-partial / L3 已交付文件 | **未触碰**（P0 修复仅改 `start-task.py` 和 `.harness/README.md`，属于架构师 §三明确允许的"对 start-task.py 和 TASK-001.yaml 的修改属例外"） |
| ❌ 降低任何阈值 | **未触碰**（BannedSymbols 阈值、stryker break=15、架构师 L2-B 阈值爬升表均未改） |
| ❌ 开始 L5 / L6 | **未触碰**（无任何规划性改动） |

---

## 第五部分：按架构师指令立即停止

> "两部分完成后立即停止会话，等待架构师审核。不得自动进入 L5。"

**当前会话立即停止。`l4a-complete` tag 已确认。等待架构师下一步指令。**

---

**END OF ROUND 1 REPORT**
