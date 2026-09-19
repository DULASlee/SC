# TASK-031 过程记录（governance.md 事实修订）

## 开工前基准核验（架构师交接点①）

- **022 常驻覆盖态说明为 031 基准**：`TASK-022-harness-scripts-cover.yaml` notes「023 配套裁定」段
  表述 = 「.harness/** 纯 path 判定：本卡 in-progress + approver + 自覆盖 allow_write，授权
  5 个 checker/dispatcher 脚本及本卡自身文件的提交」——与 check_approval.py 现行实现逐字核对
  **准确**（024 C4 后 5 脚本，check-protected-paths.py 已删）。基准不失真，031 可执行。
- **029/023/024 closeout 记录中引用将被 031 修订的描述**（标记不改，历史快照属当时事实）：
  - `docs/superpowers/spec/TASK-024-spec.md:18,32-33`（C1/C4 行「check-protected-paths.py
    main() 从不引用 / 注释声明 CI 防御层」）——024 施工时的真实状态，不改。
  - `docs/testing/red/TASK-024/scan-report.md` C4 引用分类表——同上，不改。
  - `.harness/tasks/active/TASK-024.yaml:11` allow_write 悬空条目——024 卡本身的生命周期
    条目，随 024 卡收口处理，非 031 射程。

## 扫描方法（按架构师钉死：git grep 列全 → 逐条对码分类 → 位置 → A/B/C → 处理）

`git grep "check-protected-paths" -- .harness/ docs/ai-workspace/ AGENTS.md` 命中 7 处，
外加 governance.md 全文 023/024 后过期术语扫描（EXEMPT / 豁免前缀 / APPROVED-BY /
`TASK-XXX.yaml` 严格文件名示例 / 状态迁移图卡号）：

| 位置 | 分类 | 处理 |
|---|---|---|
| governance.md:24 | **A**（纯事实过期：工具名/脚本名，check-protected-paths.py 已删；超 scope 拦截现行承担者 = check-local-scope.py，保护路径判定 = commit-msg + check_approval） | 已改（行 24 替换为现行模型描述 + 删除注明） |
| governance.md 全文其余（规则 1/3/4/5、豁免记录表、一次性豁免登记模板） | —（扫描未命中：无 EXEMPT/豁免前缀/APPROVED-BY 旧语义；卡号示例无；状态机描述与现行为一致） | 不改 |
| `.harness/tasks/active/TASK-024.yaml:11`（allow 悬空条目） | 历史快照（024 卡生命周期） | 不改（标记） |
| `.harness/tasks/active/TASK-022-...yaml:68`（closeout 记录行） | 历史快照 | 不改（标记） |
| `docs/superpowers/spec/TASK-024-spec.md`、`docs/testing/red/TASK-024/scan-report.md` | 历史快照 | 不改（标记） |
| `.harness/tasks/archive/TASK-002.yaml:11` | 归档卡（历史工件原则） | 不改 |
| 022 常驻态 notes「5 个 checker/dispatcher 脚本」 | 基准核验（见上） | 准确，不改 |

**B 类（描述承载规则意图且与现行模型不一致）：0 条。**
**C 类（牵出规则本身是否成立）：0 条** → 未触发「>2 条上报另开治理修订卡」条件。

## 验证

- 改后 `git grep "check-protected-paths" -- .harness/rules/governance.md` 仅剩行 24 的
  「已随 TASK-024 C4 删除」删除注明（有意保留，防止读者误以为脚本仍存在）。
- governance.md 变更 = 1 行（git diff 可复核）；未触碰铁律映射/豁免表格式/规则 1-5 本体。
- 两卡合流点校验（030+031 合入后全量门禁）：见 commit 记录（validate --all + .harness/tests
  全量 + pre-commit 全绿；031 仅改 .harness/rules/ 文档，未触碰任何脚本）。
