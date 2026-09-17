# 假测试检测机制（覆盖率 × 变异分数联合信号）

> **目的**：记录"假测试如何被检测"的真实机制，作为后续 L2-B/C 设计的依据。
> **修订时间**：2026-09-17（L2-B 阶段裁决）

## 错误认知

原始 L2-B 方案假设："Stryker 会变异测试代码，`Assert.True(true)` 假测试会被标记为 Survived → 分数下降 → 门禁报警。"

**这是错的。** 实测验证：
- Stryker **只变异生产代码**（project 项目），**不变异测试代码**（test-projects 项目）。
- `Assert.True(true)` 永远是 `Assert.True(true)`，没有变异体可检测。
- 加 `L2BHackingTest.cs` 与删除它，Stryker 输出的 Killed/Survived 计数**完全一致**（129/91）。

## 真实机制

**Stryker 检测的是"测试对生产代码变异的杀伤力"，不是"测试本身是真的假的"。**

假测试（如 `Assert.True(true)`）的真实特征：

| 场景 | 行覆盖率 | 变异分数 | 真实含义 |
|---|---|---|---|
| 假测试（`Assert.True(true)`） | 高（假测试会执行生产代码） | **低**（不能杀死任何变异体） | **假测试** |
| 真测试但漏测部分 | 中 | 中 | 覆盖不足 |
| 高质量测试 | 高 | 高 | 健康 |

**关键推论**：
- 单独看覆盖率：假测试可堆到 90%+（因为假测试会跑完生产代码）
- 单独看变异分数：没有基线，不知道多少是正常
- **组合看**：覆盖率 ≥ 80% 但变异分数 < 30% → **大概率存在假测试或低质量测试**

## 检测规则

### 规则 1：覆盖率 × 变异分数联合判定

```text
IF   line_coverage >= 80%
AND  mutation_score < 30%
THEN  suspicion = HIGH  # 疑似假测试或低质量测试
ELIF line_coverage < 50%
THEN  suspicion = MEDIUM  # 测试覆盖不足
ELSE  suspicion = LOW
```

### 规则 2：增量比对（推荐）

| 指标 | 健康范围 | 警告范围 | 触发调查 |
|---|---|---|---|
| 新增测试数 vs 覆盖率增量 | 每 10 个新测试应带来 ≥ 5% 覆盖率 | 每 10 个新测试覆盖率 < 2% | 假测试泛滥 |
| 新增测试数 vs 新增变异体 Killed | 每 10 个新测试应杀死 ≥ 20 个变异体 | 每 10 个新测试杀死 < 5 个 | 假测试或低质量测试 |

### 规则 3：L2-B 触发条件的"反例"

L2-B 原始触发条件："测试数量 ≥ 30 且业务代码 ≥ 3000 行"——**这个条件不够**。

**正确的触发条件**：
> 测试数量 ≥ 30，**且核心业务模块（非配置、非工具类）有基本单测覆盖**。

当前 GenCollector 状态：35 个测试全在配置层（ConfigMigrator/BackupManager/JsonConfigLoader），业务层（CollectorEngine、Drivers）零测试 → **不符合 L2-B 触发条件**。

## 实施路径

### 当前（Phase 1 早期）
- ✅ 覆盖率收集（Coverlet）已配
- ✅ 变异测试基础设施（Stryker.NET）已配
- ⚠️ 阈值低（break=15），业务层不在 mutate 范围内
- ⚠️ CI 用 `continue-on-error: true`（观察期）

### Phase 1 中期（业务层首个模块有 50%+ 单测）
- 把该模块加入 `mutate` 范围
- 阈值 break=25
- 仍 `continue-on-error: true`

### Phase 1 后期（业务层 3+ 模块有 60%+ 单测）
- 加入所有已测模块
- 阈值 break=40
- **`continue-on-error: false`**（开始阻断）

### Phase 2 生产就绪
- 全项目 mutate
- 阈值 break=50
- 严格门禁

## 关联

- ADR-005：阈值爬升表（4 个阶段 + 触发条件）
- `harness/l2-b-report.md`：报告原始错误认知
- L2-B 报告 §三 B2：架构师误判假测试机制的过程
