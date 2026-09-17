# L4-A 状态说明（部分完成）

## TL;DR

`l4a-complete` tag 存在（commit `211e6b3`），但 **L4-A 实际上只完成了"工具链骨架"**，**未完成"真跑容器验证"**。tag 命名存在误导性。

## 真实状态

| 维度 | 完成情况 | 证据 |
|---|---|---|
| 4 个 NuGet 包就位 | ✅ | Testcontainers 4.15.0 + Mosquitto 4.15.0 + Toxiproxy 4.15.0 + FluentAssertions 6.12.1 |
| 编译通过（TreatWarningsAsErrors + L2-A 严格门禁） | ✅ | 0 errors 0 warnings |
| 烟雾测试 4/4 通过 | ✅ | MosquittoBuilder / ToxiproxyBuilder 类型可加载 + FluentAssertions 跨包工作 + RedGreenProbe |
| **容器真正启动** | ❌ | 4 个测试全部**不接触 Docker**——纯反射（Type.GetConstructors）+ 字符串断言 |
| **断网 / 带宽限制** | ❌ | 架构师 §三 S3 要求运行时操作，本地未执行（未装 Docker daemon） |
| **CI 真跑容器** | ❌ | 本机无 GitHub remote，仓库从未 push，CI yaml 是配置层不是运行层 |

## 为什么 tag 命名误导

`l4a-complete` 来自前轮 AI 工程师的 commit message（`211e6b3`），但实际只完成"工具链编译就位"——**未到架构师 §四原意"真跑容器 + 断网注入 + 带宽限制"**。

按 L5 规则 2："任务卡 status 改为 done 之前，必须存在 docs/verification/VERIFY-*.md 文件"——**L4-A 没有任何 VERIFY 凭证**。当前 `l4a-complete` tag **没有 L5 凭证支撑**。

## 后续路线

| 项 | 时机 |
|---|---|
| 真跑容器烟雾测试（验证 Testcontainers 实际启 Docker + 握手） | Phase 1 中期，CI runner 有 Docker 时 |
| 断网 / 带宽限制的故障注入测试 | Phase 1 中后期 |
| 重新打 `l4a-complete` tag 覆盖（基于 VERIFY 凭证） | 上述完成后 |

## 诚实声明

- L4-A 不是"完成"——是"工具链骨架就位"
- 后续需要在补证轮 / Phase 1 中期补完后再正式标 done
- 本文档**不**试图掩盖前轮 tag 的误导命名

## 相关证据

- commit `211e6b3 feat(l4-a): reliability toolchain scaffold...`
- harness/l4-a-partial-report.md（前轮 partial 验收报告）
- harness/round1-supplemental-evidence.md（Q1-Q4 答卷）
