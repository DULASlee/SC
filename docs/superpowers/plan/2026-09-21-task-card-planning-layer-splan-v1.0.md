# 任务卡规划层改造 — 实施计划 v1.0

> 状态：待执行
> 日期：2026-09-21
> 配套规格：docs/superpowers/spec/2026-09-21-task-card-planning-layer-spec-v1.0.md
> 配套契约：docs/superpowers/spec/2026-09-21-task-card-planning-layer-contracts-v1.0.md
> 执行方：M3（弱模型，只写实现，不写验收标准）
> 验收方：强模型 / 架构师

---

## 1. 依赖图

```
Phase 1  P0 验收信号真实化  ──┬──> Phase 2  P1 依赖图校验
（含 CI 接线，先建立验证回路） │
                              ├──> Phase 3  P2+P3 追溯与契约
                              │
                              └──> Phase 4  卡生成器冒烟
```

**为什么 Phase 1 必须最先做**：它把"验收信号"这条回路接通。Phase 1 之前，任何阶段都没有可信的 CI 判据；Phase 1 之后，后续阶段各自有真实的红绿信号。

**Phase 2 与 Phase 3 可并行**（改动面不相交：前者只碰依赖图函数，后者只碰登记表函数）。

---

## 2. 引导期（Bootstrap）说明

存在一个先有鸡后有蛋的问题：

- Phase 1 的改动之一是"放开 `.harness/tests/` 作为 acceptance_tests 根"
- 但 Phase 1 自己的验收测试就位于 `.harness/tests/`
- 于是 Phase 1 的卡在**旧校验器**下无法通过

**处理方式**：Phase 1 的卡与其校验器改动**必须落在同一个 PR**。CI 的 validate job 跑的是该 PR 内的新校验器，因此卡在新校验器下合法。

**引导期注意事项**：

1. Phase 1 的卡需 `pre_approved: true`，notes 中写明"本卡为引导卡，校验器放宽与卡同 PR 落地"
2. Phase 1 的 PR 在合入前，本地预检须显式使用新校验器：
   `python .harness/scripts/validate-task-card.py --all`
3. Phase 1 合入后，Phase 2/3/4 的卡按常规流程走，无引导期

---

## 3. 各阶段施工说明

### Phase 1 — P0 验收信号真实化

| 项 | 内容 |
|---|---|
| 目标 | 占位测试模式被拒；harness 测试进入 CI |
| 改动文件 | `.harness/scripts/validate-task-card.py`、`.github/workflows/ci.yml` |
| allow_write | `.harness/scripts/validate-task-card.py`、`.github/workflows/ci.yml`、`.harness/tests/test_card_acceptance_integrity.py`、`docs/ai-workspace/rules/lessons-learned.md` |
| 验收测试 | `.harness/tests/test_card_acceptance_integrity.py` |
| done_when | `ci: harness_tests`、`ci: build` |
| 完成判据 | 该测试文件全绿 **且** CI 出现名为 harness_tests 的 job 且为绿 |

**实现要点**（详见契约 §2.1 / §2.2 / §5 / §6.1）：

1. `ALLOWED_TEST_ROOTS` 增加 `.harness/tests/`
2. `validate_card` 增加 `repo_root` 参数（默认 None，保持向后兼容），非 None 时校验测试文件存在性
3. 新增纯函数 `check_test_sharing(cards, threshold=2)`
4. `VALID_GATES` 增加 `harness_tests`
5. `.github/workflows/ci.yml` 新增 job：对 `.harness/tests/` 跑 `python -m unittest discover`

**风险前置检查**（M3 必须执行）：接线 CI 前先本地跑一遍
`python -m unittest discover -s .harness/tests -t .harness/tests`
若基线存在失败用例，**停下报告**，不得为了让新 job 变绿而修改既有测试。

### Phase 2 — P1 依赖图校验

| 项 | 内容 |
|---|---|
| 目标 | 自依赖 / 悬空依赖 / 环 被拒 |
| 改动文件 | `.harness/scripts/validate-task-card.py` |
| allow_write | `.harness/scripts/validate-task-card.py`、`.harness/tests/test_card_dependency_graph.py`、`docs/ai-workspace/rules/lessons-learned.md` |
| 验收测试 | `.harness/tests/test_card_dependency_graph.py` |
| done_when | `ci: harness_tests` |
| 完成判据 | 该测试文件全绿 |
| depends_on | Phase 1 |

**实现要点**：新增纯函数 `check_dependency_graph(cards, known_ids)`，实现自依赖、悬空、环检测（含环路径输出）。

### Phase 3 — P2+P3 追溯与契约

| 项 | 内容 |
|---|---|
| 目标 | 需求与契约引用完整可校验 |
| 改动文件 | `.harness/scripts/validate-task-card.py`、`.harness/schema/task-card.schema.json`、`.harness/registry/requirements.yaml`、`.harness/registry/contracts.yaml` |
| allow_write | `.harness/scripts/validate-task-card.py`、`.harness/schema/task-card.schema.json`、`.harness/registry/**`、`.harness/tests/test_card_traceability.py`、`docs/ai-workspace/rules/lessons-learned.md` |
| 验收测试 | `.harness/tests/test_card_traceability.py` |
| done_when | `ci: harness_tests`、`ci: build` |
| 完成判据 | 该测试文件全绿 |
| depends_on | Phase 1 |

**实现要点**：

1. schema 增加 `covers`（items pattern `^REQ-[0-9]{3,}$`）与 `contracts`（items pattern `^CTR-[0-9]{3,}$`）
2. 新建两张登记表，`items` 可为空数组
3. 新增 `load_registry` / `check_requirement_refs` / `check_contract_refs`

**注意**：登记表初版可为空（`items: []`）。空表下 `check_requirement_refs` 对"未覆盖需求"不报错（无 active 需求即无未覆盖）。

### Phase 4 — 卡生成器冒烟

| 项 | 内容 |
|---|---|
| 目标 | gen-task-cards.py 能生成合法卡并被校验器接受 |
| 改动文件 | `.harness/tests/test_gen_task_cards.py`（新建冒烟测试） |
| allow_write | `.harness/tests/test_gen_task_cards.py`、`.harness/scripts/gen-task-cards.py`、`docs/ai-workspace/rules/lessons-learned.md` |
| 验收测试 | `.harness/tests/test_gen_task_cards.py` |
| done_when | `ci: harness_tests` |
| 完成判据 | 冒烟测试全绿 |
| depends_on | Phase 1 |

**冒烟测试须覆盖**：

1. 从最小清单生成卡 → 通过校验器
2. 缺 acceptance_tests 的条目 → 生成失败（非零退出）
3. `--dry-run` 不写文件
4. 生成卡的 `deny_write` 必含 `ALWAYS_DENY` 全部条目

---

## 4. 施工包清单（可直接喂给生成器）

```yaml
batch: task-card-planning-layer
created_by: strong-model
defaults:
  done_when: ["ci: harness_tests"]
  constraints: {max_lines_changed: 300, max_files_changed: 10}
tasks:
  - id: TASK-050
    title: "P0 验收信号真实化：放开 .harness/tests 根 + 存在性检查 + 共享占位拒绝 + CI 接线"
    acceptance_tests: [".harness/tests/test_card_acceptance_integrity.py"]
    allow_write:
      - .harness/scripts/validate-task-card.py
      - .github/workflows/ci.yml
      - .harness/tests/test_card_acceptance_integrity.py
      - docs/ai-workspace/rules/lessons-learned.md
    notes: |
      引导卡：校验器放宽与本卡同 PR 落地（见 splan §2）。
      pre_approved: true

  - id: TASK-051
    title: "P1 依赖图校验：自依赖 + 悬空依赖 + 环检测"
    acceptance_tests: [".harness/tests/test_card_dependency_graph.py"]
    allow_write:
      - .harness/scripts/validate-task-card.py
      - .harness/tests/test_card_dependency_graph.py
      - docs/ai-workspace/rules/lessons-learned.md
    depends_on: [TASK-050]

  - id: TASK-052
    title: "P2+P3 追溯与契约：covers/contracts 字段 + 两张登记表 + 引用完整性"
    acceptance_tests: [".harness/tests/test_card_traceability.py"]
    allow_write:
      - .harness/scripts/validate-task-card.py
      - .harness/schema/task-card.schema.json
      - .harness/registry/**
      - .harness/tests/test_card_traceability.py
      - docs/ai-workspace/rules/lessons-learned.md
    done_when: ["ci: harness_tests", "ci: build"]
    depends_on: [TASK-050]

  - id: TASK-053
    title: "P4 卡生成器冒烟：gen-task-cards 生成合法卡并通过校验"
    acceptance_tests: [".harness/tests/test_gen_task_cards.py"]
    allow_write:
      - .harness/tests/test_gen_task_cards.py
      - .harness/scripts/gen-task-cards.py
      - docs/ai-workspace/rules/lessons-learned.md
    depends_on: [TASK-050]
```

生成命令：

```
python .harness/scripts/gen-task-cards.py --manifest <本清单路径> --dry-run
python .harness/scripts/gen-task-cards.py --manifest <本清单路径>
```

---

## 5. 执行方（M3）须知

**你只需要做一件事：让验收测试从红变绿。**

1. **不要读设计规格** —— 你不需要它。你的输入是验收测试文件 + 接口契约。
2. **不要修改验收测试** —— 测试文件已冻结，改它等于作弊。
3. **不要修改接口契约** —— 遇到冲突，停下报告。
4. **不要自己写测试** —— 本批次所有测试已由架构师预先写好。
5. **完成判据是 CI 全绿**，不是你的自我判断。

**每阶段的标准动作**：

```
1. 读该阶段的验收测试文件，理解每个断言在要求什么
2. 读接口契约的对应小节（§2 签名、§5 常量、§6 判定表）
3. 实现
4. 本地跑：python -m unittest discover -s .harness/tests -t .harness/tests
5. 全绿后提交，不要发表完成声明
```

**如果测试怎么都过不去**：停在第 3 次失败，报告失败签名，不要反复试同一种做法。

---

## 6. 验收方（强模型）须知

M3 提交后，验收动作：

1. 确认 `.harness/tests/` 三个新测试文件**未被修改**（diff 中不应出现）
2. 确认接口契约文件**未被修改**
3. 跑一遍全量测试确认绿
4. 确认改动面未越出 `allow_write`
5. 抽查实现是否符合契约 §6 判定表（尤其环检测是否真的检测环，而不是只查了自依赖）

**验收判据**：测试全绿 **且** 测试文件未被篡改 **且** 改动面合规。三者缺一即为不通过。

---

## 7. 完成后的效果

本批次完成后：

| 能力 | 之前 | 之后 |
|---|---|---|
| harness 卡能否引用真实测试 | 不能（结构性强制作假） | 能 |
| harness 测试是否被 CI 执行 | 否 | 是 |
| 占位测试能否被机器识别 | 不能 | 能 |
| 依赖成环能否被机器识别 | 不能 | 能 |
| 需求是否可追溯 | 否 | 是（登记表 + covers） |
| 契约是否可冻结 | 否 | 是（登记表 + frozen） |
| 建卡是否需手工撰写 | 是 | 否（生成器） |

**这批只立机制，不还历史债。** 现有 27 张卡的占位问题另行批次处理。
