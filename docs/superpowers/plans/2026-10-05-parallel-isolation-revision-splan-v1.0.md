# 并行隔离段修订 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把隔离段三口子、两处放水、漂移与残留逐项修死，全程功能分支，每项留红态证据。

**Architecture:** 门禁类先加后严（先告警一轮再转拒绝）；归属类改认领与比对；云端类只读账本判失败；验证类接体检进云端；线上点火为条件项。

**Tech Stack:** Python（门禁与脚本）、PowerShell 7（本地校验）、Git 功能分支 + 合请求（合入按用户当时指令）。

**对应规格：** `docs/superpowers/spec/2026-10-05-parallel-isolation-revision-spec-v1.0.md`

---

### Task 0：开分支与基线留证

**Files:** none modified (record only)

- [ ] **Step 1: 创建功能分支**

Run: `git -C F:\JQKJ checkout -b feat/isolation-revision`
Expected: `Switched to a new branch 'feat/isolation-revision'`

- [ ] **Step 2: 记录回归基线**

Run: `python -m unittest discover -s F:\JQKJ\.harness\tests -t F:\JQKJ\.harness 2>&1 | Select-Object -Last 3`
Expected: 记下 OK 数与总数（如 176 OK），写入任务记录，后续只增不减。

### Task 1：F1 提交验身份

**Files:**
- Modify: `docs/ai-workspace/hooks/check_session_registration.py`
- Modify: `.harness/tests/test_check_session_registration.py`

- [ ] **Step 1: 写红测试（先失败）**

在测试文件加两例：A 会话进 B 会话已认领树提交被拒；同一会话提交放行。先跑，确认新两例失败（功能未实现）。

Run: `python -m unittest .harness.tests.test_check_session_registration -v 2>&1 | Select-Object -Last 5`
Expected: FAIL 出现且仅为新增两例。

- [ ] **Step 2: 实现身份比对**

门禁在命中归属记录后，比对当前操作身份与登记主人：机器会话比对派发身份，手工会话比对领卡人名；不一致返回失败并打印双方身份（脱敏：只打任务与会话前缀）。

- [ ] **Step 3: 复绿**

Run: `python -m unittest .harness.tests.test_check_session_registration -v 2>&1 | Select-Object -Last 3`
Expected: 全 OK，原 6 例仍过。

### Task 2：F2 主树提交管制

**Files:**
- Modify: `docs/ai-workspace/hooks/check_session_registration.py`
- Modify: `.harness/tests/test_check_session_registration.py`

- [ ] **Step 1: 主树默认拒绝，白名单放行**

主树提交要求：主树任务归属有效，或路径落在白名单（派发占坑与状态提交、归档搬卡、人为验收凭证目录）。默认拒绝并打印申请白名单指引。

- [ ] **Step 2: 红绿验证**

红：无归属主树提交变红；绿：白名单内占坑提交放行。跑全文件测试，全 OK。

### Task 3：F3 云端归属检查

**Files:**
- Modify: `.github/workflows/ci.yml` (新增任务)
- Create: `.harness/scripts/check-cloud-ownership.py`

- [ ] **Step 1: 写只读检查脚本**

脚本只读分支提交清单、归属登记与释放记录：推送分支绑定的任务若有“他人持有中”记录且本次推送含该树提交，判失败；只读不写状态。用法：`python .harness/scripts/check-cloud-ownership.py --base origin/main`，退出码 0 过 1 拦 2 参数错。

- [ ] **Step 2: 接进云端检查**

新增任务跑该脚本（推送与合请求事件）。预期：正常分支过；构造一条冒名分支验证变红后删除验证分支。

### Task 4：F4 多卡变严

**Files:**
- Modify: `.harness/scripts/check-local-scope.py`
- Modify: `.harness/tests/` 对应测试

- [ ] **Step 1: 非唯一改拒绝**

无唯一活动卡时返回失败并打印查卡与传卡号指引（原警告跳过语义删除）。空暂存仍警告过。

- [ ] **Step 2: 红绿验证**

红：多卡下不传卡号变红；绿：传对卡号放行，单卡不受影响。全量回归数不减少。

### Task 5：F5 命令对账

**Files:** docs only + ci.yml if needed (收敛到冻结口径)

- [ ] **Step 1: 对账跑两边**

分别按冻结口径与云端口径跑回归，记录用例数。若一致，仅改云端配置收敛；若不一致，先查后改，以冻结为准。

- [ ] **Step 2: 证据入库**

对账输出存 `docs/testing/red/` 对应目录，计划中引用路径。

### Task 6：F6 体检进云端

**Files:**
- Modify: `.github/workflows/ci.yml` (新增任务)

- [ ] **Step 1: 新增体检任务**

跑三区三进程体检脚本，全绿才过；超时按现有实现。先手工跑一次确认时长可接受，超 20 分钟则拆 V 项并行。

- [ ] **Step 2: 关联触发**

动锁与归属文件的变更必须触发该任务（路径过滤）。

### Task 7：F7 推送门禁

**Files:**
- Modify: `docs/ai-workspace/hooks/pre-push`

- [ ] **Step 1: 拒绝直推与强推**

推送目标为主干或开发干直接拒绝；任何强制推送拒绝并打印“删分支重建”替代手法。功能分支普通推送不受影响。

- [ ] **Step 2: 本地演练**

用临时分支验证：直推被拒、强推被拒、普通推送过。演练后删临时分支。

### Task 8：F8 复用认主人

**Files:**
- Modify: `.harness/scripts/dispatch.py` (复用分支加归属比对)
- Modify: `.harness/tests/test_dispatch.py`

- [ ] **Step 1: 复用前比对**

目录已存在时比对归属：同主人或已释放可复用并重绑；他人持有拒绝并指引。不删任何历史分支与目录。

- [ ] **Step 2: 红绿验证**

红：他人持有复用被拒；绿：同主人复用过，释放后重绑过。

### Task 9：F9 回归与小修

**Files:**
- Modify: `.harness/tests/` (新增两例), `verify-all.py` (补导入), 空测试工程（二选一）

- [ ] **Step 1: 换行与暂存回归**

故意造换行错误文件，门禁必须变红后清理；故意混他人暂存提交，范围检查必须变红后清理。两例入库。

- [ ] **Step 2: 修验收导入与空工程**

补验收脚本缺失导入并跑一遍冒烟；空测试工程补用例或下线，不留占位。

### Task 10：F10 线上点火（条件项）

- [ ] **Step 1: 查前置**

模型线路可用则执行：真探针留证、在线三并发全链、崩溃恢复全链、常驻实跑，证据入库；前置不满足则记顺延，不硬上。

### Task 11：总验收与合请求

- [ ] **Step 1: 全量回归**

Run: 基线命令重跑。Expected: 用例数 ≥ 基线，失败 0。

- [ ] **Step 2: 开合请求**

只含本计划文件，按仓库规范开请求待审；合入按用户当时指令（含全绿自动合入终态若已生效）。

## 自检记录

- 规格覆盖：F1→T1，F2→T2，F3→T3，F4→T4，F5→T5，F6→T6，F7→T7，F8→T8，F9→T9，F10→T10；A1-A7 均有对应证据步骤
- 占位扫描：无 TBD/TODO；脚本行为描述完整可执行
- 类型一致：退出码语义 0/1/2 全计划统一；锁与归属不改结构只加比对
