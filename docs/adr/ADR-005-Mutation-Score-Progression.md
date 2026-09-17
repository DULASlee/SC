# ADR-005: Mutation Score 阈值分阶段爬升机制

## 状态
已接受（L2-B 阶段裁决 · 2026-09-17）

## 背景
L2-B 阶段引入 Stryker.NET 变异测试作为"测试质量"门禁。架构师原始方案要求 `threshold-break: 50` —— 但实测 GenCollector mutation score 仅 **17.20%**（业务层零测试）。这是**测试覆盖率不足**问题，不是门禁机制问题。

架构师裁决 L2-B 必须是**分阶段阈值爬升机制**——阈值随业务代码和测试的成长逐步提升，**不允许通过降低阈值掩盖没有测试的事实**。

## 决策

### 1. mutate 范围随阶段变化

**核心原则：只对"已有测试覆盖"的代码层做变异测试，不为没有测试的业务层跑无意义的变异。**

### 2. 阈值爬升表

| 阶段 | 触发条件 | mutate 范围 | break | low | high | CI 行为 |
|---|---|---|---|---|---|---|
| **Phase 1 早期**（现在） | 仅 Config + Contracts 层有测试 | `["**/Config/**/*.cs", "**/Contracts/**/*.cs", "!**/obj/**"]` | 15 | 25 | 40 | `continue-on-error: true`（观察期，不阻断） |
| **Phase 1 中期** | 业务层首个模块有 50%+ 单测 | 加入该业务模块 | 25 | 40 | 55 | `continue-on-error: true`（观察期） |
| **Phase 1 后期** | 业务层 3+ 模块有 60%+ 单测 | 加入所有已测模块 | 40 | 55 | 70 | `continue-on-error: false`（开始阻断） |
| **Phase 2 生产就绪** | 全项目 70%+ 覆盖 | 全项目 | 50 | 65 | 80 | `continue-on-error: false`（严格门禁） |

### 3. 阶段推进机制

- **不自动爬升**：每个阶段由人类架构师签字推进（开新 ADR 即可）。
- **不倒回**：一旦严格门禁生效，不允许通过修改阈值回到观察期。
- **观察期输出**：变异测试报告 `continue-on-error: true` 期间**照常运行并上载 artifact**，但不阻断 merge。

### 4. 当前阶段（Phase 1 早期）的具体配置

```json
{
  "stryker-config": {
    "project": "GenCollector/GenCollector.csproj",
    "test-projects": ["GenCollector.Tests/GenCollector.Tests.csproj"],
    "reporters": ["html", "json"],
    "thresholds": { "high": 40, "low": 25, "break": 15 },
    "mutate": [
      "**/Config/**/*.cs",
      "**/Contracts/**/*.cs",
      "!**/obj/**"
    ]
  }
}
```

## 后果

- L2-B 阶段"假完成"风险被消除（拒绝通过改阈值掩盖）。
- 业务层 0 测试 → 0 变异体 → 0% 分数的"空跑陷阱"被消除（mutate 范围限制）。
- 阈值爬升需人类架构师签字，避免弱模型偷偷降低阈值。

## 关联
- ADR-001 ~ ADR-004：保留（与 L2-A 同步）。
- `docs/testing/fake-test-detection.md`：假测试检测机制（覆盖率 × 变异分数联合信号）。

## 修正记录
- L2-A 报告（`harness/l2-a-report.md`）：架构师已发现 BannedSymbols 语法错误（`M:get_Now` → `P:DateTime.Now`），已修复。
- L2-B 报告（`harness/l2-b-report.md`）：架构师已发现 4 个技术错误，包括致命的假测试机制误判。本 ADR 取代方案 X 中平铺 `threshold-*` 配置方案。
