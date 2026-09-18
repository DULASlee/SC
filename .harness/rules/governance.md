# Governance — 项目治理规则

> 本文件定义 GenCollector 项目的治理规则。所有任务卡、PR、commit 必须遵守。

---

## 规则 1：任务卡生命周期

任务卡状态机：`draft → ready → in-progress → done`（或 `blocked`）。

- **draft → ready**：架构师签发施工包后由 AI 工程师创建 `.harness/tasks/active/TASK-XXX.yaml`（status: ready）。
- **ready → in-progress**：执行者开始实现时改 status 为 `in-progress`（commit 体现状态变更）。
- **in-progress → done**：done_when 全部达成后改 status 为 `done`。
- **done → archived**：任务完成后由 `.harness/scripts/archive-task.py` 移至 `archive/`。

状态变更必须 commit。状态伪造（写 done 但代码未完成）触发铁律 3（禁止自报完成）。

---

## 规则 2：scope 强制

每个 active 任务卡有 `scope.allow_write` 与 `scope.deny_write`。

- pre-commit hook（`.harness/scripts/check-protected-paths.py`）会拦截 **超出 scope 的文件修改**。
- 即使 allow_write 列出路径，`deny_write` 优先级更高。
- 添加新路径到 scope 必须由架构师修订任务卡（状态变更需要 commit）。

---

## 规则 3：铁律不可绕过

铁律列表（`docs/ai-workspace/rules/engineering-rules.mdc`）：

- L1 总原则、L2 契约优先、L3 禁止自报完成、L4 禁止删测试掩盖问题、L5 禁止静默回退、L6 禁止跨文档字段漂移、L7 交付物入 Git、L8 平台目标固定、L9 敏感信息不存明文、L10 决策留 ADR、L11 报告可验证、L12 经验沉淀、L13 禁止直接合入 main、L14 文档与配置集中化。

**任何 commit 不得违反现行铁律**。豁免需项目负责人书面授权（chat 文本即可）并记录于本文档"豁免记录表"。

---

## 规则 4：经验沉淀触发

每个任务卡 `status: done` 时，执行者必须追加至少 1 条经验到 `docs/ai-workspace/rules/lessons-learned.md`。

格式：`[TASK-XXX] 场景 → 教训`，每条不超过 2 行。

连续 3 张卡无经验沉淀，该执行者后续卡需额外提交"经验自查说明"。

每周由执行者整理一次，合并重复项、归档已修复项（迁移到 `lessons-archived.md`）。

---

## 规则 5：豁免记录格式

豁免必须记录：
- **规则编号**（如 铁律 13）
- **豁免对象**（如 TASK-008 合并）
- **原因**（如 "经验沉淀机制尚未就位，需要先实现 lessons-learned.md"）
- **授权人**（如 项目负责人 / architect）
- **日期**（ISO 8601）
- **过期条件**（如 "经验沉淀机制 PR 合并后失效"）

格式见下方"豁免记录表"。

---

## 豁免记录表

| 日期 | 铁律 | 对象 | 原因 | 授权人 | 过期条件 | 状态 |
|---|---|---|---|---|---|---|
| 2026-09-18 | 铁律 13（禁止直接合入 main） | TASK-008 merge commit `463e2a4`（"TASK-008 lessons-learned + 铁律 12"） | 经验沉淀机制尚未就位，需先建 lessons-learned.md 才能经 PR 流程；gh CLI 首次使用前需打通工作流 | 项目负责人 | 经验沉淀机制 PR 合并后失效（PR #2 已合入 main 463e2a4，豁免已生效并关闭） | ✅ 已生效并关闭 |

---

## 一次性豁免登记模板（新增行请用此格式）

```
| YYYY-MM-DD | 铁律 N（描述） | TASK-XXX commit XXXXX | 原因 | 项目负责人 | 过期条件 | 状态 |
```
