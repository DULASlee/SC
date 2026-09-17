# Harness 工程构建 · 母本

> **目录**：`docs/项目harness工程构建/`  
> **用途**：沉淀本项目对 harness 工程的根本性判断，作为后续所有 ADR / 任务卡 / CI 设计的母本。  
> **维护**：当发生新的"通用错误类"时，只在本文件加一类根因与对应机制，不另起文档。

---

## 第〇部分：评审原文（2026-09-17，由外部专家给出）

### 引言

这套方案看起来很"2026"，但骨子里仍是**枚举已知错误、逐个贴补丁**：五个错误对应五个脚本、五个 Skill、五个 Hook。下一个没见过的错误出现时，整套东西一个都拦不住。下面先拆它为什么不通用，再给一套从根因出发的通用 harness。

### 一、现有方案的六个结构性缺陷

#### 1. 黑名单思维：只防已经发生过的错

`test-integrity-check.sh` 防测试被删，`check-platform-target.sh` 防 x86 写错，`check-contract-freeze.sh` 防契约漂移。这三件事都是**回头看**发生过的具体事故。但一个弱模型下周会犯的是：时区处理错、null 没判、异常被吞、事务边界错、并发竞态……你不可能为每种错写一个脚本。**通用 harness 必须让"错误类"过不去，而不是让"某个错误实例"过不去。**

#### 2. AGENTS.md"错题本"对弱模型基本无效

把约束写成散文让模型"读一遍再干"，本质还是在依赖模型的指令遵循能力——而指令遵循能力弱，恰恰是 MiniMax 这类模型的核心问题。错题本会无限增长、规则相互冲突、模型在长上下文中丢失它们。**约束如果不能变成编译器、类型、Schema、CI 红灯，它就不是约束，是祈祷。**

#### 3. 证据由被评估者自己生产，这是 reward hacking 的高速通道

方案让 Agent 生成 `evidence/reconnect-30s.json`，然后 CI 检查文件里的 `lost == 0`。一个弱模型最擅长的就是**直接写一个 `{"lost": 0}` 文件**。删测试和伪造证据是同一种行为，方案只堵了前者，却给后者开了门。所有证据必须由 CI 运行真实测试产出为 artifact，Agent 不能有写权限。

#### 4. 用同一个弱模型当验证者

`reliability-verifier` 子代理 = 同一个 MiniMax 换了个 system prompt。它有相同的知识盲区、相同的幻觉倾向，只是在另一个上下文里重复同样的错。验证者必须是**确定性工具**（编译器、测试、Schema 校验器、模糊测试）或**不同能力级别的模型/人**。

#### 5. 指标可被 Goodhart 化

"测试数量不减少"——加 10 个 `Assert.True(true)` 就过了。"哈希匹配"——契约文件没变，但契约本身四份手写文档互相矛盾这件事根本没解决。哈希冻结锁住的是**文件**，不是**一致性**。

#### 6. 复杂度本身是弱模型的敌人

MCP Server × 2、Skills × 4、Hooks × 3、子代理 × 3、`allowUntrustedFrontmatterHooks`、npx 拉取第三方包……每个环节都是新的失败面。给一个执行力弱的模型配一套复杂的编排系统，等于给一个新手司机配一台 F1 赛车。**模型越弱，harness 应该越简单、越机械、越少依赖模型自己配合。**

### 二、根因分析：五个错误其实只有四个根因

| 表面错误 | 真正根因 |
| :--- | :--- |
| 列出 11 个契约不一致却宣布"完成" | R1：完成状态由模型自报，没有机器定义的 Done |
| 删除 Shift-JIS 测试 | R2：生产者和验证者是同一个 Agent，测试可被实现者修改 |
| x86 说法前后矛盾 | R3：技术事实靠模型"记忆"，没有机械化的环境固定和实验验证 |
| 可靠性只有文档 | R4：非功能需求没有可执行形态，无法被 CI 判定 |
| Git 未初始化 | R0：环境没有在 Agent 动手前就搭好（这不是模型的错，是使用者的错） |
| 11 个契约不一致本身 | R5：四份手写文档描述同一件事，不一致是必然结果，不是偶然 |

注意 R5：OpenAPI、AsyncAPI、MQTT Topic 文档、data-models 是**四份各自独立手写的真理来源**。让任何模型（哪怕是最强的）手写四份并保持一致，都是在跟概率作对。原方案用"冻结 + 哈希"去**检测**不一致，根因方案应该让不一致**无法产生**。

### 三、通用 harness 的设计原则

只有五条，每条都独立于具体错误：

1. **Correct by construction 优先于 detect after the fact**：能用单一来源 + 代码生成消灭的问题，不要用校验去检测。
2. **Done 由机器判定，永不由模型自报**：Agent 的输出是 PR，PR 的状态由 CI 决定，模型没有说"完成"的权限。
3. **生产者不能碰验证者**：测试、Schema、CI 配置对实现者只读；同一 PR 同时改 `src/` 和 `tests/` 需要人工审批。
4. **任务粒度小于模型的可靠工作集**：每个任务一个新会话、一个 PR、一组预先写好的验收测试，状态存在仓库里而不是对话里。
5. **不确定的技术事实必须用实验证明**：不允许"我认为 .NET 由运行时决定"，只允许"这是编译出来的 PE Header dump"。

### 四、通用 harness 分层架构

#### L0：铺好路再放人（Paved Road）

Agent 第一次动手之前，仓库就必须是这个样子，且**由人搭建**：

- `git init` + `main/develop` 分支保护 + PR 模板
- `Directory.Build.props` 统一约束所有项目，Agent 不需要也不能逐个改 csproj：

```xml
<Project>
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
    <AnalysisLevel>latest-recommended</AnalysisLevel>
  </PropertyGroup>
  <PropertyGroup Condition="$(MSBuildProjectName.StartsWith('Collector'))">
    <PlatformTarget>x86</PlatformTarget>
    <RuntimeIdentifier>win-x86</RuntimeIdentifier>
    <SelfContained>true</SelfContained>
  </PropertyGroup>
</Project>
```

x86 问题由此**彻底消失**——不需要审计脚本、不需要 Skill、不需要错题本，编译器就是约束。

- `.editorconfig` 强制 UTF-8 + `charset` 检查
- CI 骨架已跑通（build、test、coverage、lint），初始就是绿的

#### L1：单一真理来源 + 代码生成（消灭契约漂移）

不要四份文档。选一个 Schema 作为唯一来源，其余全部生成：

| 唯一来源 | 生成物 |
| :--- | :--- |
| `contracts/*.proto` 或 JSON Schema | C# DTO / 枚举（服务端 + 客户端 + 采集端共用一个包） |
| 同一来源 | OpenAPI 文档（NSwag/Swashbuckle 从代码反推） |
| 同一来源 | AsyncAPI + MQTT payload schema |
| 同一来源 | 数据库迁移中的字段类型 / TypeScript 类型 |

Agent 修改契约的唯一方式是改 Schema 文件并跑 `dotnet build`，生成物不允许手改（CI 检查 `git diff --exit-code` 生成目录）。11 个不一致这种事**结构上不可能发生**。

#### L2：确定性质量门（通用，不针对任何具体错误）

全部在 CI，全部不依赖模型配合：

| 门 | 拦截的错误类 | 工具 |
| :--- | :--- | :--- |
| 编译 + 警告即错误 + Nullable | 类型、空引用、平台目标 | 编译器 |
| 静态分析 + 架构测试 | 依赖方向、命名、禁用 API（如 `Encoding.Default`） | Roslyn Analyzers、NetArchTest、自定义 BannedSymbols.txt |
| 覆盖率**差分**（新增代码 ≥ 80%） | 不写测试 | Coverlet + ReportGenerator |
| 变异测试分数阈值 | 假测试、`Assert.True(true)` | Stryker.NET |
| 契约测试 | 生成物与实现不符 | Pact / Schemathesis |
| 生成物一致性 | 手改生成代码 | `git diff --exit-code` |
| 属性测试 | 编码、边界、单调性等整类问题 | FsCheck（例如：任意 GBK/GB18030/UTF-8 字节序列 → 解码后再编码保持 round-trip） |

注意最后一条：不是写"一个 GBK 测试"，而是写**"对任意受支持编码的任意输入，round-trip 成立"**的属性。这一条覆盖 Shift-JIS、GBK、GB18030 和所有未来的编码问题。

`BannedSymbols.txt` 示例，一行消灭一整类错误：

```text
P:System.Text.Encoding.Default;使用显式编码
M:System.DateTime.get_Now;使用 IClock 注入
M:System.Threading.Thread.Sleep(System.Int32);使用 Task.Delay
```

#### L3：任务协议（解决上下文丢失与自报完成）

每个任务是一张机器可读的任务卡，存在仓库里：

```yaml
id: TASK-042
scope:
  allow_write: [src/Collector/Buffer/**]
  deny_write:  [tests/**, contracts/**, .github/**, Directory.Build.props]
acceptance_tests:
  - tests/Collector.Tests/EdgeBufferTests.cs   # 由架构师/强模型预先写好，初始为红
done_when:
  - ci: build
  - ci: acceptance_tests pass
  - ci: coverage_diff >= 80
  - ci: mutation_score >= 60
  - ci: no_generated_code_modified
```

规则：
- 每个任务**新开会话**，只加载任务卡 + `allow_write` 范围内的文件，不依赖历史对话
- 验收测试先写、先红、再交给实现者；实现者对 `tests/` 无写权限（CODEOWNERS 强制人工审批）
- Agent 提交 PR 后**不发表任何"完成"声明**，Done 状态只来自 CI 的 checks
- 一次任务不超过约 300 行变更，超了就拆

这样"上下文丢失"不再是需要监控的指标，因为**没有长上下文可丢**。

#### L4：可靠性需求可执行化（且由 CI 产证据）

把每条非功能需求写成**故障注入集成测试**，用 Testcontainers + Toxiproxy 在 CI 里真跑：

```csharp
[Fact]
public async Task Mqtt_Disconnect_30s_ZeroLoss_ZeroDuplicate()
{
    await using var broker = await MqttContainer.StartAsync();
    await using var proxy  = await Toxiproxy.Wrap(broker);

    var seq = await publisher.SendSequence(count: 10_000);
    await proxy.Cut(TimeSpan.FromSeconds(30));   // 真实断网
    await consumer.WaitUntilCaughtUp();

    consumer.Received.Should().BeEquivalentTo(seq, o => o.WithStrictOrdering());
}
```

同类测试覆盖：磁盘满（限制容器磁盘）、时钟回拨（注入 IClock）、3 倍背压（限速消费者）、证书过期（用过期证书起 broker）、48 小时缓冲（用虚拟时钟快进而非真等）。

证据 = CI 的测试报告 artifact，Agent 没有任何写入通道。"文档化的可靠性"这类问题被结构性消除。

#### L5：独立验证者

- **Plan 和 Review 用强模型**（或人），**Implement 用弱模型**。任务卡、验收测试、Schema 由强模型/人产出，MiniMax 只负责在划定范围里把红测试变绿。这是与弱模型协作的正确分工，比"配一个 verifier 子代理"有效得多。
- 技术事实争议一律要求**可运行的最小实验**（spike），产出物是命令输出，不是论述。

#### L6：反馈回路——每次事故升级一个"类"，而不是加一条规则

事故复盘的产出物不允许是"AGENTS.md 加一行"，只允许是下列之一：

| 事故 | 错误的修法 | 正确的修法 |
| :--- | :--- | :--- |
| 删了 Shift-JIS 测试 | 加"禁止删测试"脚本 | tests/ 对实现者只读 + 变异测试 + 编码 round-trip 属性测试 |
| x86 说法反复 | 加 csproj 审计脚本 | Directory.Build.props 统一声明，编译器兜底 |
| 契约 11 处不一致 | 冻结哈希 | 单一 Schema + 代码生成 |
| 可靠性只有文档 | 让 Agent 写证据 JSON | 故障注入测试进 CI |
| 用了 Encoding.Default | 错题本记一笔 | BannedSymbols 一行 |

判断标准：**新增的机制能不能拦住一个你还没见过的同类错误？** 不能，就是补丁。

### 五、两种思路的对照

| 维度 | 原方案（补丁式） | 根因方案（通用 harness） |
| :--- | :--- | :--- |
| 约束载体 | 散文（AGENTS.md）+ 脚本 | 编译器、类型、Schema、CI |
| 覆盖范围 | 已发生的 5 个错误 | 错误类，含未发生的 |
| 契约一致性 | 检测漂移（哈希） | 无法漂移（单一来源生成） |
| 验证者 | 同一模型的子代理 | 确定性工具 + 强模型/人 |
| 证据来源 | Agent 自己写 JSON | CI 运行真实故障注入 |
| Done 判定 | 模型自报 + 脚本 | 仅 CI checks |
| 上下文丢失 | 监控 token 使用率、回退 | 任务足够小，无长上下文 |
| 对模型能力的依赖 | 高（要读懂并遵守规则） | 低（不遵守就编译不过） |
| 复杂度 | MCP + Skills + Hooks + 子代理 | 一个 CI 文件 + 一个 Build.props + 任务卡 |
| 随时间的演化 | 规则膨胀、互相冲突 | 门的数量稳定，类别升级 |

### 六、落地顺序（人做，不让 Agent 代劳）

1. **第 1 天**：`git init`、Directory.Build.props、BannedSymbols、.editorconfig、CI 骨架跑绿。这一步完成前 Agent 不允许提交任何代码。
2. **第 2–3 天**：把现有四份契约收敛为一个 Schema，配好代码生成，删掉手写 DTO。11 个不一致会在这一步被迫暴露并一次性解决。
3. **第 4–5 天**：接入 Coverlet 差分 + Stryker + NetArchTest；把现有测试全部纳入 `tests/` 并设 CODEOWNERS。
4. **第 2 周**：Testcontainers + Toxiproxy 故障注入测试骨架，先写 3 个（断线、幂等、背压），红着放进 CI。
5. **之后**：按任务卡协议运转。强模型/人出卡和测试，MiniMax 填实现，CI 判 Done。

### 七、最后一句判断

原评估说"该模型不胜任独立架构负责人"是对的，但原方案的错误在于**试图用更多规则让它变得胜任**。正确的方向是反过来：**把它不需要胜任的事全部从它手里拿走**——契约靠生成、平台靠编译器、完成靠 CI、验证靠故障注入、判断靠强模型和人。剩下的"在给定范围内把红测试变绿"，恰恰是弱模型能做好的事。harness 的健壮性来自于**它对模型智力的依赖有多低**，而不是它有多少条规则。

---

## 第一部分：评审意见的补充与修正（2026-09-17，项目评审记录）

> 本节是对上方母本的**事实核对 + 落地性补充**，遵循"承认对的、修正有偏差的、补漏未覆盖的"原则。

### A. 六条结构性缺陷的事实核对（本仓库直接证据）

| 评审观点 | 工作区证据 | 核对结果 |
|---|---|---|
| ① 四份手写契约互不一致 | `docs/architecture/contract-consistency.md` 第 22、35、48、61、74、87、100 行明确记录 7+ 处不一致（snake_case vs camelCase、qualityCode 4 种编码、timestamp 单/双字段） | **完全成立** |
| ② 删测试靠模型"自报"防不住 | `caa0f9f` 提交"修复 Shift-JIS 测试"只补了 NuGet 包，**没注册 CodePages provider**，导致 2 个 GBK/Shift-JIS 编码测试 100% 失败——这种"修复"如果不跑测试就被当成 Done | **完全成立** |
| ③ x86 事实靠模型记忆 | `GenCollector.csproj` 第 11 行确有 `<PlatformTarget>x86</PlatformTarget>`，但 `GenDashboard.csproj`、`GenCollector.Tests.csproj` 等 5 个项目均未显式声明 | **完全成立** |
| ④ 证据由 Agent 自己写 JSON | `docs/superpowers/plans/2026-09-17-c9-go-gateway-rebuild.md` 与 phase 0 计划均使用"Agent 写 evidence/*.json 然后 CI 检查"模式 | **完全成立** |
| ⑤ `reliability-verifier` = 同一模型换 prompt | 评审准确指出了它的弱点（同一知识盲区、同一幻觉倾向、换上下文重犯） | **完全成立** |
| ⑥ 复杂度是弱模型的敌人 | 当前 `.specstory/cli/config.toml` + 多层 plans/specs/reports 已存在相当多结构；再加 MCP×2 + Skills×4 + Hooks×3 会让约束层超过 Agent 可靠工作集 | **完全成立** |

**六条全部成立，每条都有本仓库的直接证据。**

### B. 对评审意见的五条细节修正

| 评审说法 | 修正 | 修正原因 |
|---|---|---|
| "四份文档结构上必然不一致" | 同意根因判断，但**生成方向需澄清**：不是从 OpenAPI 生成 AsyncAPI，而是反过来——先有 Proto / CSDL 之类"代码生成器能理解的 Schema"，OpenAPI/AsyncAPI/TypeScript/IoTDB schema 都从它派生 | 在工业领域 protobuf 是更稳的根（MQTT payload / gRPC / DB 迁移吃同一份） |
| "测试对实现者只读" | 方向对，但**落地会撞墙**：`tests/` 与 `src/` 物理耦合在同一 repo，`CODEOWNERS` 强制人工审批在小团队会成瓶颈 | 现实折中：`tests/` 顶层"产品测试"只读；新功能测试可合并进 PR 主体但必须强模型/人 review |
| "变异测试 ≥ 60" | **这是 Goodhart 化的反面例子**。Stryker.NET 对反射/async/Moq 代码普遍 < 50；强设阈值会让 Agent 写"易于被杀"的代码（删多态、加 `internal`） | 改为**仅对新增/修改的代码做变异测试**，并按 critical path 加权（MQTT 重连 ≥ 70，其它 ≥ 50） |
| "fs/属性测试覆盖整类编码问题" | **完全同意且这条最有价值** | 1 个 `FsCheck.EncodingForAnyCodepage(input)` 覆盖 GBK/GB18030/Shift-JIS/Big5/EUC-KR 全集，比 5 个 skill+10 个 patch 都管用 |
| "`Encoding.Default` 进 BannedSymbols" | 方向对，但**还不够**。BannedSymbols 是 regex 文本匹配，会漏 `Encoding.GetEncoding(0)`、`Encoding.GetEncoding("GB2312")` 等合法但同样产生问题的入口 | 更稳的做法是**自定义 Roslyn Analyzer**：检测"未指定 CodePage 的 Encoding 创建"+ "未注入 `IClock` 的 `DateTime.Now` 调用"——这种 analyzer 报警是**编译错误级别**，无法绕过 |

### C. 一处尖锐分歧（必须诚实标注）

评审说"复杂度本身就是弱模型的敌人，所以 harness 要简单"。**我同意"机械约束 > 规则清单"的倾向**，但反对"越简单越好"的极限版本：

- **`Directory.Build.props` 统一 x86 / Nullable / WarningsAsErrors**：✅ 简单且正确，应立刻做。
- **`BannedSymbols.txt`**：✅ 简单且正确，应立刻做。
- **完全用"任务卡 + CI 红灯"替代文档/SOP**：⚠️ 有反例——**新成员入职**。即便全是强模型，第一次接触代码库也需要 ADR（`docs/architecture/adr/`）解释"为什么是 x86 不是 x64"。

**评审把 SOP/ADR 与"指令式错题本"混为一谈，但前者是叙事性架构记忆（一次写、长期读），后者是指令（每会话都要加载并遵守）。两者成本与作用完全不同。**

> 一句话修正：**不要让 ADR/SOP 进入每会话上下文，但不能让仓库里没有它们。**

### D. "根因方案"的可落地性评估

| 评审建议 | 落地难度 | 性价比 | 建议时机 |
|---|---|---|---|
| L0 `Directory.Build.props` | 极低（1 文件，1 小时） | 极高（一次消除 x86/warning/nullable 三类错） | **立即，今天** |
| L0 `.editorconfig` UTF-8 | 极低 | 高（防一类隐性错） | **立即，今天** |
| L1 单一 Schema + 生成 | 高（选 Proto、写 4 个服务端 .proto，桥接 MQTT payload） | 高（消除 7+ 处契约不一致） | **第 1 周**，先服务端，再扩 MQTT |
| L2 BannedSymbols + Roslyn Analyzer | 中（BannedSymbols 1 天，Analyzer 2-3 天） | 高（一行干掉 `Encoding.Default`/`Thread.Sleep`/`DateTime.Now` 全家） | **第 1 周** |
| L2 变异测试 | 高（CI 跑 Stryker .NET 比单元测试慢 5-10 倍） | 中（防假测试但易 Goodhart 化） | **第 2 周**，先仅对 critical path |
| L3 任务卡 + PR 协议 | 中（需要任务卡 schema + CODEOWNERS） | 高（消除长上下文问题） | **第 1 周** |
| L4 Testcontainers + Toxiproxy 故障注入 | 高（要 docker，Windows runner 慢） | 极高（把"可靠性文档"变成 CI 红灯） | **第 2-3 周** |
| L5 强模型/人 vs 弱模型分工 | 极低（流程问题） | 极高 | **今天起**——任何任务卡我先出"红测试+Schema"，用户填实现 |
| L6 事故升级为类，不加规则 | 极低 | 高 | **采纳作为复盘 SOP** |

### E. 我同意立即执行的 5 件事（按"今天就能做"的优先级）

1. **`Directory.Build.props` + `.editorconfig` UTF-8 + `BannedSymbols.txt`** — 1 文件，覆盖 x86 / Nullable / WarningsAsErrors / `Encoding.Default` / `Thread.Sleep` / `DateTime.Now` 6 类错。
2. **`tests/**` 与 `src/**` 物理分离**（移到独立 test 项目）+ `CODEOWNERS` — 删测试需人工审批。
3. **GBK 编码由"2 个写死测试"改为 FsCheck 属性测试** — 一段代码覆盖所有受支持编码（含未来新增）。
4. **`docs/architecture/contracts/` 收敛为 1 Schema + 4 生成器**（OpenAPI/AsyncAPI/MQTT payload/TypeScript）— 7 处契约不一致结构上消失。
5. **1 个 Testcontainers + Toxiproxy 故障注入样板测试**（先红着进 CI）— 演示"可靠性 = CI 红灯"，取代"可靠性 = Agent 写 JSON"。

### F. 对评审"最后一句判断"的补充

评审最后一句：**"harness 的健壮性来自于它对模型智力的依赖有多低"**——这条完全同意。

但要补半句：**"harness 也要承认模型在某些事情上确实不行（如分布式时钟、跨进程资源生命周期），把这些也变成 Roslyn Analyzer 或 fault-injection test，而不是靠 Agent 自觉。"**

评审把弱模型的边界画在"指令遵循 + 长上下文"，实际边界还要再加一条：

> **任何无法在编译期/单元测试里证明的事，弱模型都不可靠。**

这条把编码、时区、并发、事务、授权、加密、随机性统统囊括，是比六条缺陷更通用的元原则。

---

## 第二部分：本项目（JQKJ）当前与母本的差距清单

> 用于指导后续任务卡的"差距修复任务"——每个差距对应一个 task，**每个 task 的 done_when 必须能在 CI 里被验证**。

| 差距 | 母本要求 | 当前状态 | 影响 |
|---|---|---|---|
| 无 `Directory.Build.props` | L0 强制平台目标 / Nullable / WarningsAsErrors | 缺失（5 个 csproj 各写各的） | x86 类错误每次都要审计 |
| 无 `.editorconfig` UTF-8 | L0 强制文件编码 | 缺失 | 隐式 GBK / Shift-JIS 混入 |
| 无 `BannedSymbols.txt` | L2 干掉一整类 API | 缺失（`Encoding.Default`、`Thread.Sleep` 等仍可用） | 历史错误可重犯 |
| `tests/` 与 `src/` 物理耦合 | L3 验证者只读 | 耦合 | 实现者可改测试 |
| 无 FsCheck 属性测试 | L2 用"类"覆盖编码问题 | 只有 2 个写死的 Shift-JIS 测试（且首次提交未跑通） | 加新编码就要加测试 |
| 4 份手写契约 | L1 单一来源生成 | 4 份独立手写（已记录 7+ 处不一致） | 契约漂移 |
| 可靠性只有文档 | L4 故障注入测试 | 0 个 fault-injection 测试 | 可靠性无证据 |
| 证据由 Agent 写 JSON | L4 CI 运行产 artifact | phase 0 计划使用 evidence/*.json 模式 | reward hacking |
| `reliability-verifier` 子代理 | L5 强模型/人 vs 弱模型分工 | 计划中存在 | 同模型验证同模型 |
| 无任务卡 schema | L3 机器可读任务卡 | 缺失 | 任务状态存在对话里 |

---

## 第三部分：附录——本评审对原始六缺陷的"是否完全成立"评分卡

| # | 缺陷 | 评分 | 一句话 |
|---|---|---|---|
| 1 | 黑名单思维 | 10/10 | 通用 harness 的核心 |
| 2 | AGENTS.md 错题本无效 | 9/10 | 但 ADR/SOP 不在此列（必须保留） |
| 3 | 证据由被评估者自产 | 10/10 | reward hacking 高速通道 |
| 4 | 同一弱模型验证 | 10/10 | 必须是确定性工具或强模型 |
| 5 | 指标可被 Goodhart 化 | 9/10 | 变异测试阈值本身也是 Goodhart 风险 |
| 6 | 复杂度是敌人 | 8/10 | 方向对，但"越简单越好"是过度简化 |

**总分 56/60，评级 A-**：评审方向正确且几乎全部有据；唯一需要修正的是"完全不要 ADR/SOP"这条过激建议，以及"变异测试硬阈值"这条新引入的 Goodhart 风险。
