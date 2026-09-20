# TASK-023 Spec — E1 移除：保护门改纯 path 判定

> 状态：工程师起草，待架构师签发。裁定顺序 024 → 029 → 023（已满足：024 已完成，
> 029/④ 已落 commit `95fa69c`）。签发后由 AI 工程师执行。

## 背景

- **E1 洞**：`docs/ai-workspace/hooks/commit-msg:22` `EXEMPT_TYPES=(chore docs feat fix style test ci build)`
  → 行 35 `exit 0`，**跳过** TASK grep（行 40）与 check_approval（行 67）。
  八种常规前缀全穿透：AI 可合法自造 `.harness/**` 新卡，保护门实际覆盖率接近 0
  （仅「裸 TASK-XXX:」类非规范提交受检）。
- **029 裁定钉死的耦合**：tests/** 一旦被 acceptance-touch 纳入，须同步 `allow_write + approver`。
- **前提已满足**：④ 常驻测试已落地（023 后 ④ 卡仍合法——执行不触 tests/），023 不再造成新卡死锁。
- 机器提交形态（023 后全部命中 `.harness/**` 保护，需卡 + approver 覆盖）：
  - dispatch 占坑/回滚：`dispatch.py:319-322`（`chore(harness): TASK-XXX … [APPROVED-BY]`，首行含 TASK-XXX，grep 可过）
  - poll 状态标记：`poll.py:155`（同上格式）
  - pipeline 机器验收：`pipeline.py:311-313`（`chore(harness): TASK-XXX pipeline accept done`，故意不带批标记，行 310 注释在 023 后失效）

## 方案

1. **commit-msg 去豁免**（改 `docs/ai-workspace/hooks/commit-msg`；`.githooks/commit-msg` 转发器不动）：
   - 删 `EXEMPT_TYPES` 判定块（行 21-38）与 `EXEMPT_PREFIXES` 声明（行 9-19，声明未执行项，同病一并删）；
   - 统一流程：首行必须含 `TASK-[0-9]{3,}` → `check_approval.py --staged` 纯 path 判定
     （`check_approval.py:17-26` PROTECTED_PATTERNS + status ready/in-progress + allow_write 覆盖 +
     非空 approver + deny 优先，语义零改动）；
   - 保留 `SKIP_PROTECTED_CHECK=1`（架构师本人通道，行 71）；
   - 后果（明示）：docs/** 人类提交从此也须引用 TASK-XXX（形如 `docs: TASK-029 追加沉淀行`）。
2. **机器提交迁移**（acceptance-touch 耦合，架构师钉死项）：
   - 迁移步骤：所有 active 且 status ∈ {ready, in-progress} 的卡，签发时盖 `approver:` 字段
     并保证 allow_write 含自身卡文件（自覆盖，TASK-021:8-10 既有先例）；
   - 一次性迁移 commit：现存 ready/in-progress 卡批量补 approver + 自覆盖；
   - 同步修订 `pipeline.py:310` 失效注释（“hook 放行 done 路径”在 023 后不成立）。
3. **acceptance-touch 判据固化**（spec 级，零代码）：
   - 卡验收/diff 触碰 tests/** 时，该卡 allow_write 必须覆盖具体测试路径 + 非空 approver
     （`check_approval.py:99` 既有语义；023 只固化判据 + 红态证据，不加新代码）；
   - ④ 类沉淀卡（021/029）执行 diff 仅 docs/ → 不受影响。

## 验收（红态证据入 `docs/testing/red/TASK-023/`）

| # | 场景 | 期望 |
|---|---|---|
| R1 | `chore: bump` 无 TASK 提交（023 前穿透） | 拒绝（首行无 TASK-XXX） |
| R2 | `TASK-030: 新卡` + staged `.harness/**`，无覆盖卡 | 拒绝（check_approval FAIL） |
| R3 | 占坑卡缺 approver → dispatch 占坑 | commit 失败，回滚 ready（`dispatch.py:400-404` 既有路径） |
| G1 | approver + 自覆盖卡占坑 | 通过 |
| G2 | ④ 卡（021/029）执行 diff 仅 docs/ | 不受 023 影响 |
| G3 | diff 触 tests/**，approver 卡覆盖该路径 | 通过；无覆盖 → 拒绝 |
| G4 | `validate-task-card.py --all` + `.harness/tests` 全绿 | 通过（回归） |

## 待架构师裁定的开放决策

- **D1**：pipeline 机器验收 commit（`pipeline.py:311-313`）保持“无人工批标记”（推荐：保持，
  门禁靠卡 + approver；批标记仅保留给 dispatch 占坑约定），并同步改行 310 注释。
- **D2**：approver 签发权 = 架构师签发时人工盖章（推荐；不做默认自动盖章——029 裁定原则：
  分类权/授权权不让渡）。

---

## 实施补遗（工程师，2026-09-19，D1/D2 已裁定 PASS）

签发后实施中推导出的规则细节（均在 D1/D2 框架内，未削弱保护范围）：

1. **自生命周期规则**（check_approval）：done/已归档卡只可覆盖「自身卡文件」的
   生命周期路径（active 侧卡文件提交、archive 侧归档 rename），条件 = 该卡非空 approver
   + 自覆盖 allow_write + deny 优先 + f 按卡 id 命名。无此规则则机器验收 done commit 与
   归档 rename 在纯 path 判定下死锁（done 卡主判定不授权，归档后卡离开 active/ 不可见）。
   第三方路径一律仍不覆盖。
2. **SKIP_PROTECTED_CHECK=1** 由「声明未执行」转为已执行：只跳过受保护路径判定，
   不跳过 TASK-XXX 引用（最小特权解读）。
3. **hook 解释器回退**：`PYTHON=$(command -v python3 || command -v python)`
   （023 后 python 判定是唯一路径，Windows Git Bash 环境 python3 不保证存在）。
4. **卡文件 id 前缀解析**：pipeline `_mark_done_and_archive` 与 dispatch 前置检查按
   `TASK-XXX*.yaml` 前缀 + 卡内 id 字段唯一解析（029 check-pr-scope v3.1 同规则，
   兼容后缀文件名）。
5. **一次性迁移**：现存 12 张 ready/in-progress 卡补 `approver: architect`
   + 自覆盖 allow_write；TASK-023 自身 allow_write 精确枚举 12 张卡路径
   （不用 `.harness/tasks/active/*.yaml` 通配——通配即 E1 旧病复发，022 先例：精确到文件）。
