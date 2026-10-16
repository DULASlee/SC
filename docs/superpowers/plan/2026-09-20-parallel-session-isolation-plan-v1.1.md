# 并行会话隔离与全局协调机制 — Formal Implementation Plan v1.1（冻结版）

> 版本：v1.1（冻结施工契约）
> 日期：2026-09-20
> 状态：**FROZEN** — 依评审结论冻结；施工以此为准
> 溯源：v1.0 为架构师原稿；v1.1 并入评审报告（`docs/reports/2026-09-20-parallel-session-plan-review.md`）的五处修订（A1-A5）与七项补充登记（B1-B7），P4 可行性已由该报告 §7 的真实探针实证
> 执行方式：按阶段（P0→P6）推进，每阶段结束以可验证证据收口；施工包建议拆任务卡执行（本仓 L3 协议）

## v1.1 修订总览（相对 v1.0 的全部差异）

| 编号 | 修订点 | 落入章节 |
|---|---|---|
| A1 | 账本框架纠正：现状已集中，P3 工作重定义为"跨进程写锁 + 临界区 + 崩溃安全"，且必须覆盖双账本（RUNS + PIPELINE） | §4、§11 |
| A2 | P4 设计定案：per-attempt 设置副本 + `--patch` 重定向，全局设置零写入（可行性已实证） | §12 |
| A3 | P5 语义补丁：ownership 键 = TaskId；attempt 重试合法复用同 worktree；Owner 变更仅发生在任务释放后 | §7、§13 |
| A4 | P1 入口工件与 enforcement：`start-session.py` 薄包装 + pre-commit hook 校验登记与归属 | §9 |
| A5 | 协调根定位定案：仓库级（沿用 `.harness/runs/` 目录语义），显式排除用户级 runtime root | §10 |
| B1 | worktree 回收并入 P3 崩溃恢复（现存 TASK-008/009/010 陈旧 worktree 为证） | §11 |
| B2 | 主树只读依赖登记（上下文/skills 绝对路径） | §14 |
| B3 | 旧规则"同一时间只允许一个 AI 会话操作仓库"随本方案落地显式废止 | §18 |
| B4 | 验证场景补 V9（重试链）与 V10（主树卡提交与 worktree 会话并发） | §14 |
| B5 | Windows 并发 append 交织风险点名：锁必须覆盖账本全部写操作含 append 路径 | §5 |
| B6 | ADR 目录定案 `docs/adr/`（事实惯例），D-Parallel 编号 ADR-006 起 | §18 |
| B7 | Gate F 回归命令固化 `python -m unittest discover -s .harness/tests -t .harness` | §19 |

原文未改动部分为 v1.0 契约本体；修订处以 **【v1.1】** 标记。

---

# 1. 文档目的

本计划用于将当前"单工作目录隐含前提"的工程执行机制，改造成支持多个 AI 会话并行工作的安全执行基础设施。

本计划只解决以下问题：

1. 多会话必须物理隔离，不能共享工作目录。
2. 多工作目录不能导致全局并发额度失控。
3. 多工作目录不能导致模型切换产生全局配置污染。
4. 多工作目录不能导致任务状态出现多个事实源。
5. 一个任务必须具有明确 Owner，非 Owner 会话不得修改其任务状态。
6. 并行执行必须能够通过真实三工作目录并发运行验证。

本计划**不是重新设计整个 AI Engineering OS**，也不是重构现有任务系统、派发器、Hook、MCP、配置系统或 Git 流程。

**【v1.1】** 现状断言已由评审报告 §2 的 P0 级映射逐条核实（12+2 项机制），其中两处与 v1.0 的描述不符并已在本版修正（A1/A5 相关）；施工侧 P0 的剩余工作仅为补漏（Hook 细节、canary、verify-all 侧逐行核实），不必从零开始。

---

# 2. 施工目标

最终必须形成如下运行模型：

```text
                    ┌────────────────────────────┐
                    │ Repository Coordination    │
                    │      Shared Authority      │
                    ├────────────────────────────┤
                    │ Global Run Ledger           │
                    │ Global Concurrency          │
                    │ Coordination Lock           │
                    │ Task Ownership Registry     │
                    └─────────────┬──────────────┘
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
             ▼                    ▼                    ▼
       Session A            Session B            Session C
       Worktree A           Worktree B           Worktree C
       Branch A             Branch B             Branch C
       Task A               Task B               Task C
       Local Runtime        Local Runtime        Local Runtime
```

必须满足：

```text
1 Session = 1 Worktree = 1 Branch = 1 Task Owner
```

但：

```text
Global Coordination State ≠ Worktree Local State
```

**【v1.1 补充（A3）】** 上式按 Task 粒度成立：现状即 `1 Task = 1 Worktree = 1 Branch（feat/TASK-XXX）`，且 attempt 重试合法复用同一 worktree（失败 → 复位 → 重派同任务同 worktree）。Session 是新增维度，不得把 Owner 绑到 attempt 粒度。

---

# 3. 架构契约（施工不得偏离）

## 3.1 L0：物理隔离

### 必须成立

每一个可执行会话必须拥有：

```text
独立 Worktree
独立 Branch
明确 SessionId
明确 TaskId
明确 Owner
```

禁止：

```text
Session A ─┐
           ├── same working directory
Session B ─┘
```

禁止：

```text
Branch A + Branch B → same worktree
```

禁止手工会话绕过现有 worktree 创建机制，直接在主目录执行。

**【v1.1 补充（A4）】** "禁止绕过"必须是机制而非规则：pre-commit hook 增加"提交发生地 = 已登记 worktree 且提交者 = 该任务 owner"校验；违反即拒绝提交（hook 属全仓共享基础设施，为允许修改面 D/E 的最小延伸）。本仓"约定即可靠"已被证伪多次（lessons：[parallel-sessions]、[TASK-013]），只写规则不写机制等于没写。

### L0 的责任边界

L0 只负责：

* 工作目录隔离
* Git branch 隔离
* Session ↔ Worktree 绑定
* Session ↔ Task 绑定

L0 不负责：

* 全局并发额度
* 全局运行账本
* 模型锁
* 任务全局状态

这些属于 L1/L2。

---

# 4. L1：全局协调状态

## 4.1 Global Run Ledger

**【v1.1 重写（A1）】** v1.0 原文"运行账本必须从 Worktree-local state 提升为 Repository/Coordination-level shared state"与现状不符：账本**今天已集中于主树** `.harness/runs/`，且为双账本（`RUNS.jsonl` owner=dispatch + `PIPELINE.jsonl` owner=pipeline，槽位经 `running_count(owner=None)` 全量查询互通）。**不存在**每 worktree 一份账本的情形。

P3 的真实工作因此是：

```text
1. 为双账本的全部读写加跨进程临界区（同一把协调锁）
2. 消除 dispatch/poll 手工并行时无保护的 check-then-act（槽位计算）
3. 账本写入路径（含 append）在并发写者下的崩溃安全
```

账本的唯一事实源只能有一份（每 owner 一份，共两份，统一在同一临界区保护下）。

仍然禁止：

```text
Worktree A/.runtime/ledger
Worktree B/.runtime/ledger
Worktree C/.runtime/ledger
```

作为并发控制依据。

允许每个 Worktree 保留本地日志，但：

> 本地日志只能是诊断副本，不能成为全局协调事实源。

---

# 5. L1：全局并发额度

## 5.1 目标

任何 Worktree 启动任务时，都必须查询同一个全局并发状态。

例如全局限制：

```text
MAX_CONCURRENCY = N
```

那么：

```text
A = 1
B = 1
C = 1
```

必须得到：

```text
Global = 3
```

而不是：

```text
A.local = 1
B.local = 1
C.local = 1
```

被错误解释成三个独立额度。

**【v1.1 补充】** 现状核对：全局额度**已实现**（`running_count` 跨双账本全量计数），缺口仅在原子性（§5.2）。

## 5.2 原子性要求

以下操作必须是同一临界区：

```text
Read Global Ledger
        ↓
Check Capacity
        ↓
Reserve Slot
        ↓
Write Ledger
```

禁止：

```text
read
unlock
check
lock
write
```

这种 check-then-act 竞争窗口。

**【v1.1 补充（B5）】** 锁必须覆盖账本**全部写操作**，含 append 路径：Windows 多进程对同一文件的并发 append 无逐行原子保证，交织写入会损坏账本。

## 5.3 锁机制

必须提供真正跨进程共享的协调锁。

要求：

* 同一机器多个进程有效
* 同一仓库多个 Worktree 有效
* 不能依赖当前 Worktree 文件
* acquire/release 必须明确
* 异常退出后必须具备恢复机制
* 禁止永久锁死

优先复用现有运行时，不重新引入第三方协调基础设施。

**【v1.1 补充】** 复用路径已定：本仓 mkdir 锁模式（pid 文件 + 600 秒 stale + 二次确认）在 `modelswap.py::acquire_lock` 与 `loop.py::acquire_singleton` 两处已 Windows 实战验证，P3 直接泛化该模式。注意 P4 落地后 modelswap 锁随之退役（§12），协调锁以 loop 锁模式为蓝本。

---

# 6. L1：模型配置必须改成 Session Override

**【v1.1 重写（A2，设计定案）】** v1.0 标记为"必须删除的危险行为"的判断完全成立，且实证危害比 v1.0 描述更宽：

* 写入点是**用户机器级** `~/.dsh/settings.yaml`（非仓库级），影响面跨仓库、跨所有手工会话；
* 该文件默认带文件监视器，改写会**热发布到正在运行的其他会话**；
* 派发器被迫"同轮同模型"降级规避跨轮竞态（v1.0 已知）。

必须删除：

```text
读取全局模型配置
↓
修改全局模型配置
↓
运行任务
↓
恢复全局模型配置
```

替换为（已实证可行，评审报告 §7）：

```text
Global Model Baseline（~/.dsh/settings.yaml，全程只读）
        ↓
Per-Session Override（per-attempt 设置副本 + --patch 重定向）
        ↓
Process Effective Configuration
```

### 必须保证

两个 Session 可以同时运行：

```text
Session A → Model A
Session B → Model B
```

且：

```text
A 不修改 B
B 不修改 A
Global baseline 不被修改
```

### 明确禁止

本任务中禁止：

* 重设计整个配置体系
* 引入新的配置中心
* 修改无关配置优先级
* 重写 Provider/Model abstraction
* 为此迁移全部旧配置文件

只需打通现有配置覆盖能力，使模型路由不再修改共享全局状态。（**【v1.1】**该能力已实证存在，见 §12。）

---

# 7. L2：任务归属

## 7.1 Ownership 是唯一写权限

任务必须明确：

```text
TaskId
OwnerSessionId
OwnerWorktree
```

任务状态修改规则：

```text
Owner Worktree → READ + WRITE
Other Worktree  → READ ONLY
```

非 Owner 不能修改：

```text
pending
running
blocked
done
failed
cancelled
```

等任务状态。

**【v1.1 补充（A3）】** 三条硬语义，施工不得偏离：

```text
1. ownership 键 = TaskId（不是 attempt）
2. 同一任务的 attempt 重试链合法复用同一 worktree（复位后重派）
3. OwnerSessionId 变更仅发生在任务释放（blocked / awaiting-review / done）之后
```

违反第 2、3 条会打断现有重试机制并误伤 Gate F 回归。

## 7.2 双目录执行同一任务

必须明确禁止：

```text
Task-17
  ├── Worktree A → running
  └── Worktree B → running
```

系统必须在任务 claim/execute 前发现冲突并拒绝。

**【v1.1 补充】** 现状由"占坑即改卡状态 + 单派发器"隐式保证；本计划将其升级为显式拒绝机制（§13）。claim 临界区必须覆盖"读卡状态 → 写 → commit"整段（git index.lock 只防同时写、不防 TOCTOU）。

---

# 8. 任务拆分

施工严格按以下顺序执行。

---

## P0 — 现状映射

### 目的

不写代码，先把现有机制真实位置找出来。

### 必须找到

1. Worktree 创建入口
2. Branch 创建入口
3. 自动派发入口
4. 手工会话入口
5. 当前运行账本文件/实现
6. 当前并发计数实现
7. 当前模型锁实现
8. 当前全局模型配置写入点
9. Task Card 状态读写实现
10. Task ownership 判定实现
11. Hook 读取 Task Card 的位置
12. 所有"不入库/每 Worktree 自生成"的 runtime state

### 探测原则

使用真实代码搜索，不允许凭目录名称猜测。

例如：

```bash
rg -n "worktree|git worktree|branch|ledger|concurr|lock|model|TaskId|status|claim|owner" .
```

然后形成：

```text
EXISTING-MAP.md
```

内容只记录：

```text
Mechanism
Current File
Current Authority
Current Scope
Used By
```

### P0 完成标准

必须证明：

```text
Current implementation ≠ assumed implementation
```

未找到的机制不得自行发明替代架构。

**【v1.1 补充】** 上述 12+2 项映射已由评审报告 §2 预填完成（含全部位置与使用者）；P0 剩余工作：①核对 Hook 细节、canary、verify-all 三处未逐行核实的实现；②补"手工会话入口不存在"与"ownership 判定不存在"两项的正式记录；③产出 EXISTING-MAP.md 落 `docs/superpowers/spec/`（可直接转录评审报告 §2 表格）。

---

# 9. P1 — L0 Worktree Isolation

### 工作内容

复用当前自动派发机制，把相同能力扩展到手工会话。

必须实现：

```text
Create Session
    ↓
Create/Select Task
    ↓
Create Worktree
    ↓
Create Branch
    ↓
Bind Session
    ↓
Start Process
```

### 必须保证

会话启动前：

```text
WorkingDirectory is unique
Branch is unique
Task ownership is unique
```

### 不做

本阶段不修改：

* 全局 ledger
* model routing
* task state authority
* Hook 体系

这些在后续阶段完成。

**【v1.1 补充（A4）】** 入口工件定案：`start-session.py` 薄包装，组合三个既有能力——`ensure_worktree`（建工作区+分支）+ `start-task.py`（生成上下文）+ ownership 登记（写入协调根）。不新造生命周期。enforcement 按 §3.1 的 hook 校验落实施工。

---

# 10. P2 — Global Coordination Store

创建仓库级共享协调状态。

推荐结构：

```text
<coordination-root>/
    ledger
    ownership
    locks
```

这里的 `<coordination-root>` 必须满足：

```text
所有 Worktree 可访问
不属于任何一个 Worktree
不会随 branch checkout 改变
```

### 注意

它可以位于 Repository coordination root / repository metadata / 用户级 runtime root。

具体采用哪一种，以当前代码和现有运行模型为准。

禁止为了本任务设计全新的长期存储产品。

**【v1.1 定案（A5）】** 三选一定案：**仓库级，沿用 `.harness/runs/` 目录语义**（目录可更名，层级不得变）。显式排除"用户级 runtime root"，理由：①任务 ID 跨仓冲突（多仓共用一份 ownership/ledger 会互相污染）；②锁与被保护对象必须同层级（现有教训：modelswap 锁在仓库级却保护用户级文件）。禁止新建目录树——在现有 runs 目录内扩展子目录（`locks/`、`ownership/`）即为全部新增物。

---

# 11. P3 — Global Ledger + Cross-process Lock

### 任务

**【v1.1 修订（A1）】** 将（原文"Local Ledger 替换成 Shared Global Ledger"修订为）：

```text
为现有双账本（RUNS.jsonl + PIPELINE.jsonl，主树 .harness/runs/）
加上跨进程协调锁与临界区，并使其在并发写者下崩溃安全
```

账本结构、字段、追加/原子覆写语义保持现状（runs.py 的 fsync append 与 os.replace 已验证良好，缺的只是互斥）。

### 核心 API

实际名称必须复用现有抽象；若不存在，再增加最小接口。

逻辑上必须具备：

```text
Acquire()
Read()
Validate()
Mutate()
Write()
Release()
```

### 原子操作

至少保证以下操作不可并发穿透：

```text
Reserve
Release
UpdateState
ClaimTask
CompleteTask
```

### 进程崩溃

必须处理：

```text
Process killed
Process crash
Shell interrupted
Session disconnected
```

不会留下永久占用的 slot。

恢复规则必须复用现有心跳 / PID / stale detection 能力；没有则只实现最低限度 stale recovery，不得顺便重做任务系统。

**【v1.1 补充（B1）】** 崩溃恢复一并覆盖 worktree 回收：slot 释放时判定对应 worktree 可回收（任务终态 + 无未提交变更），清理 `git worktree remove`；现存 TASK-008/009/010 陈旧 worktree 即为本项必要的实证。

---

# 12. P4 — Model Override

**【v1.1 重写（A2，已实证设计）】**

### 删除共享配置写入路径

v1.0 要求找到 `SetGlobalModel()/RestoreGlobalModel()` 等价路径——已定位：`modelswap.py::swap_for_run/restore`（写 `~/.dsh/settings.yaml`）。本阶段将其从派发路径**整体退役**（swap/restore/lock/maybe_restore 链），只读函数（如 `read_selection`）去留由施工按引用情况定。

### 替代机制（评审报告 §7 已探针实证）

```text
派发时（spawn 侧，全在现有 run_dir 内）：
  1. 读全局 ~/.dsh/settings.yaml（只读）
  2. 替换 agent-default-model 为本任务模型
  3. 写 <run_dir>/settings.yaml（per-attempt 副本）
  4. 写 <run_dir>/model.patch.yml：
       - id: settings
         config: {path: <run_dir>/settings.yaml, watch: false}
  5. executor_argv 追加：--patch <run_dir>/model.patch.yml
```

依据（全部已验证）：

* `dsh --patch` 为 CLI 按次叠加层，profile 层之后生效（bin.js 参数定义）；
* settings 条目的 `config.path` 显式优先于默认主目录（dsh-settings-file `resolveSpec`）；
* 值优先级：文件层 > 组合层（dsh-settings mergeLayers 顺序），重定向副本即用户层；
* `watch: false` 关闭热发布监视器（探针实证生效）；
* 全局文件 SHA256 前后一致（零写入实证）；
* 双模型隔离与失败对照（404 精确命中副本模型 + 换模型成功返回探针令牌）。

### 手工会话

同一机制开放给手工会话：`--patch` 是普通 CLI 参数，人手可用；`start-session.py` 可代生成副本与 patch。

### 禁止写共享配置

```text
Write shared config = 禁止（机制上不再存在该路径）
```

### 必须提供两个测试

```text
A(Model=A)
B(Model=B)
```

同时启动后：

```text
A effective = A
B effective = B
Global baseline unchanged
```

**【v1.1 补充】** 测试方法直接复用探针手段放大：会话各自副本运行 + 全局文件哈希断言 + 会话产物模型断言。

---

# 13. P5 — Task Ownership Enforcement

### 建立单一事实源

任务状态不能继续由各 Worktree 内自己的卡片决定。

最少需要：

```text
TaskId
OwnerSessionId
OwnerWorktree
State
```

### 权限规则

```text
Claim:
    only if unowned

Write state:
    only Owner

Release:
    only Owner

Read:
    everyone

Execute:
    Owner only
```

### 冲突测试

必须实际制造：

```text
Task-1
Worktree A claim

Worktree B attempt claim
```

预期：

```text
B = rejected
A = remains owner
```

不能只是返回 warning。

**【v1.1 补充（A3）】** 权限规则按 Task 粒度解释（§7.1 三条硬语义）；实现载体定案：ownership 登记落协调根 `<runs>/ownership/`（P2 结构），卡状态仍走现有 commit 路径（主树，commit 前持锁）。claim 的临界区 = "持锁 → 读卡 → 验无主 → 写 in-progress → commit → 记 ownership → 释锁"。

---

# 14. P6 — 三 Worktree 真实并发验证

这一阶段不是单元测试，而是真实运行验证。

必须启动：

```text
Worktree A / Branch A / Task A
Worktree B / Branch B / Task B
Worktree C / Branch C / Task C
```

同时运行。

验证至少以下场景：

### V1 物理隔离

A 修改文件：

```text
file-X
```

B/C 不发生工作目录变化。

### V2 分支隔离

```text
A = branch-A
B = branch-B
C = branch-C
```

任何 Session 不得因为其他 Session checkout 导致 branch 改变。

### V3 全局额度

例如：

```text
MAX = 2
```

同时启动 A/B/C：

```text
A → accepted
B → accepted
C → rejected / queued
```

不能出现：

```text
A.local=1
B.local=1
C.local=1
```

然后全部运行。

### V4 模型互不污染

```text
A → Model-A
B → Model-B
C → Model-C
```

同时运行。

验证：

```text
A ≠ B ≠ C
Global baseline unchanged
```

### V5 Task Ownership

```text
A → Task-A
B → Task-B
C → Task-C
```

A 不得写 Task-B。

### V6 同任务竞争

```text
A → claim Task-X
B → claim Task-X
```

只能一个成功。

### V7 异常退出

杀死：

```text
A process
```

随后验证：

```text
Global slot eventually released
Task state recoverable
Lock released
B/C can continue
```

### V8 Hook 一致性

三个 Worktree 同时执行相关 Hook。

验证 Hook：

```text
读取正确 Session
读取正确 Task
读取正确 Worktree
读取统一 Global State
```

不得因 cwd 不同得到互相矛盾的授权结果。

**【v1.1 补充（B4）】** 新增两条：

### V9 重试链（并行负载下）

并行运行期间人为制造一次 attempt 失败：

```text
Task-A attempt-1 失败 → 复位 worktree → attempt-2 重派同 worktree
```

验证：复位语义不被并行会话破坏；其他会话不受影响。

### V10 主树卡状态提交并发

一 worktree 会话运行期间，主树发生卡状态提交：

```text
验证：卡提交（主树 git index）与 worktree 会话互不干扰
```

### 【v1.1 补充（B2）】主树只读依赖验证

V1-V10 期间附带验证：worktree 会话经绝对路径读取主树的上下文与 skills，主树分支切换不中断读取（现状 skills_dir 与上下文均为指向主树的绝对路径，只读、可接受，但须留证）。

---

# 15. 文件修改边界

这是防止项目从"小改造"漂移成"两个月重构"的核心约束。

## 允许修改

仅允许修改以下类别：

```text
A. Session / Worktree creation path
B. Runtime ledger / concurrency path
C. Model routing / startup configuration path
D. Task ownership / task state authority path
E. 直接覆盖上述功能的测试
F. 必要的少量文档/决策记录
```

## 禁止修改

除非发现明确阻塞本任务的编译问题，否则禁止碰：

```text
MCP protocol
业务功能
前端
数据库
AI model provider implementation
整体配置系统
任务系统重新设计
Git strategy 全面重构
Hook 全面重写
日志系统重构
持久化体系重构
部署系统
CI/CD
安全体系
其他无关模块
```

---

# 16. 禁止扩张的四条硬规则

### Rule 1 — 不得借题重构

发现旧代码不好看：

```text
记录问题
```

但：

```text
本任务不顺手重构
```

### Rule 2 — 不得把"未来设计"变成本轮实现

例如未来可能需要：

```text
distributed lock
database-backed coordinator
multi-host worker
cloud scheduler
```

本轮都不做。

### Rule 3 — 不得改变已经正确工作的自动派发机制

原则：

> 扩展现有能力，不另起第二套 session/worktree 生命周期。

### Rule 4 — 未通过真实并发验证，不得声称完成

```text
Unit Test PASS ≠ Parallel Safety PASS
```

必须有真实三 Worktree 运行证据。

---

# 17. 提交策略

不得最后一次提交几千行混在一起。

建议至少拆成：

```text
Commit 1
L0 Worktree / Session isolation

Commit 2
Global coordination + ledger + lock

Commit 3
Model session override

Commit 4
Task ownership

Commit 5
Tests + concurrency verification + docs
```

每个 Commit 必须：

```text
build
targeted tests
clean diff
```

**【v1.1 补充】** 每段提交走本仓铁律 13 流程（feature 分支 + PR + 架构师审核），提交面用 pathspec 限定（lessons [TASK-024]）。

---

# 18. 设计决策记录（必须新增）

本次需要新增一份 ADR / Decision Record，正式冻结：

## Decision

```text
D-Parallel-001
Worktree-local state is not authoritative for global coordination.

D-Parallel-002
Global runtime coordination uses repository-level shared authority.

D-Parallel-003
Model selection is session-scoped and does not mutate shared baseline.

D-Parallel-004
Task state has a single owner and single authoritative state source.
```

**【v1.1 补充（A2）】** 新增第五条：

```text
D-Parallel-005
Session-scoped model selection is implemented as per-attempt settings
copy + CLI patch redirection; the global settings file is read-only
to all sessions and the dispatch path.（评审报告 §7 实证依据）
```

## Explicit Rejection

记录以下方案明确废止：

```text
每 Worktree 一份并发账本
每 Worktree 一把模型锁
通过修改全局配置实现模型切换
各 Worktree 各自判断 Task authorization
用户级 runtime root 作为协调根
attempt 粒度的 ownership（重试链必须按 Task 粒度）
```

**【v1.1 补充（B6）】** 落位：`docs/adr/`（本仓事实惯例，5 份 ADR 全在此；AGENTS.md 速查表的 `docs/architecture/adr/` 表述需另行修正，不属本计划边界）。编号：ADR-006（D-Parallel-001）至 ADR-010（D-Parallel-005）。

**【v1.1 补充（B3）】** ADR 同时显式废止旧规则："同一时间只允许一个 AI 会话操作仓库"（lessons-learned [parallel-sessions] 条目），并登记其替代物（本计划的 L0/L1/L2 机制）。旧教训条目不删改，仅标注 superseded（本仓惯例，见 lessons 第 55/61 行先例）。

---

# 19. 完工验收标准

只有全部满足才允许标记：

```text
PARALLEL-SAFETY = CLOSED
```

### Gate A — Physical Isolation

```text
3 sessions
3 worktrees
3 branches
3 tasks
```

全部独立。

### Gate B — Shared Coordination

```text
single global ledger
single global quota
single cross-process lock
```

### Gate C — Model Isolation

```text
A ≠ B ≠ C
Global baseline unchanged
```

### Gate D — Ownership

```text
one task = one owner
non-owner write = rejected
```

### Gate E — Crash Recovery

```text
kill process
lock releases
slot releases
state recoverable
```

### Gate F — Regression

现有自动派发流程：

```text
must remain passing
```

**【v1.1 补充（B7）】** 回归命令固化：

```text
python -m unittest discover -s .harness/tests -t .harness
```

（`-t .` 在 Python 3.14 下因 `.harness` 点开头目录必报 `ImportError: KeyError: ''`——lessons [dispatcher-mvp]。）

### Gate G — Real Concurrent Run

真实三个 Worktree 同时运行成功。

---

# 20. 最终交付物

施工结束只允许产生以下交付物：

```text
1. Code changes
2. Automated tests
3. Concurrency verification script / procedure
4. Architecture Decision Record
5. Existing mechanism mapping
6. Final verification report
```

最终报告必须用下面格式：

```text
# Parallel Safety Completion Report

## L0 Physical Isolation
PASS/FAIL
Evidence:

## L1 Global Ledger
PASS/FAIL
Evidence:

## L1 Concurrency Quota
PASS/FAIL
Evidence:

## L1 Cross-process Lock
PASS/FAIL
Evidence:

## L1 Model Override
PASS/FAIL
Evidence:

## L2 Task Ownership
PASS/FAIL
Evidence:

## Crash Recovery
PASS/FAIL
Evidence:

## Three-Worktree Real Run
PASS/FAIL
Evidence:

## Existing Regression
PASS/FAIL
Evidence:

## Modified Files
...

## Explicitly Not Changed
...

## Remaining Known Risks
...
```

---

# 21. 本计划的完成定义

不是：

> "代码已经改完。"

而是：

> **从单 Worktree 隐含模型切换到多 Session / 多 Worktree 模型后，L0 物理隔离、L1 全局协调、Session 模型隔离、L2 Task Ownership 均有唯一事实源，并通过真实三 Worktree 并发运行验证。**

如果施工过程中发现新的第四、第五个共享状态：

```text
发现 → 记录 → 判断是否属于本计划边界
```

只有属于以下集合才允许立即修：

```text
Session isolation
Global coordination
Model isolation
Task ownership
Concurrent execution correctness
```

其他问题一律进入：

```text
FOLLOW-UP / OUT-OF-SCOPE
```

不得借本任务继续扩张。

这份计划的关键不是"写得多"，而是把**完成定义和不准做什么**同时写死了。这样 AI 工程师就不能从"改并发账本"一路漂移到"顺便重构任务系统、Hook、配置中心、MCP、Git 生命周期"。

尤其应该把这一句作为本轮施工的**总闸门**：

> **任何新增修改如果不能直接证明是在解决 L0/L1/L2 的并行安全问题，就不得进入本轮。**

另外，**L0 和 L1 必须作为一个完整施工包验收，不能出现"L0 已完成、L1 下个阶段再说"的中间状态。**

---

# 附（v1.1）：开工前边界外挂账（不属本计划，已上报待架构师处理）

1. **紧急**：派发默认模型 `openrouter/deepseek/deepseek-v4-flash-0731:free` 上游免费档已下线（404 实测），当前派发即失败；修 `dispatch.yaml` 的 model 行（付费 slug 或换 `cohere/north-mini-code:free`——后者已探针实测可用）。此为配置修复，先于本计划任何阶段处理，否则 P6 验证无法起跑。
2. headless profile 的 `mcp-codebase-memory` patch 条目组合时报 "entry not found"（TASK-041 接线实际未加载）。与 lessons [skills-mcp] "尚未端到端调通"一致；另行开卡处理。
3. ADR 目录规则矛盾（engineering-rules vs AGENTS.md 表述）：按事实惯例 `docs/adr/` 执行，AGENTS.md 表述修正另行开卡。
