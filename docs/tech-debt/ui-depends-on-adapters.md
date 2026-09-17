# 技术债：IoTPlatform.UI.Wpf 依赖 IoTPlatform.Adapters

## 状态
Phase 1 待清偿（本文件仅登记，不在骨架 CI 中写成红测试）。

## 事实
`IoTPlatform.UI.Wpf` 目前直接依赖 `IoTPlatform.Adapters`：

- 工程引用：`src/Frontend/IoTPlatform.UI.Wpf/IoTPlatform.UI.Wpf.csproj`（ProjectReference → IoTPlatform.Adapters）
- IL 层真实依赖：`src/Frontend/IoTPlatform.UI.Wpf/MainWindow.xaml.cs:6` `using IoTPlatform.Adapters;`

## 目标架构
UI（View / ViewModel）不应直接依赖 Adapters。采集能力应通过 `IoTPlatform.Core`
的抽象（`ICollector` / `IDeviceAdapter` / `CollectorRegistry`）注入，Adapters 只在
组合根（`IoTPlatform.Host`）装配。依赖方向应始终由外向内指向 Core。

## 为什么本轮不作为架构测试
架构规则 "UI.Wpf 不依赖 Adapters" 若写成测试，会以现有代码为反例直接红灯，
污染 Harness 骨架的 CI 通道。裁决为：先记录债务，Phase 1 重构 UI 依赖注入后再补该规则。

## Phase 1 清偿动作（预览）
1. MainWindow / ViewModel 改为依赖 Core 抽象，不再 `using IoTPlatform.Adapters`。
2. 在 `IoTPlatform.Host` 组合根完成 Adapter→Collector 的装配。
3. 解除 `IoTPlatform.UI.Wpf.csproj` 对 `IoTPlatform.Adapters` 的 ProjectReference。
4. 在 `tests/ArchitectureTests` 增加规则 2：`Types.InAssembly(uiAssembly).Should().NotHaveDependencyOn("IoTPlatform.Adapters")`，并断言 UI 程序集类型数 > 0。
