# JQKJ 数采平台路线：以 Go 采集器为底座，冻结原 maiyata/saas WPF 交付

> 日期：2026-09-19
> 状态：路线草案
> 边界：`F:\maiyata\saas` 原项目冻结，不修改、不接入、不共享模块；JQKJ 仅移植/补强 Go 采集器作为新数采平台底座。

## 1. 路线结论

JQKJ 后续按下面顺序推进：

```text
阶段 1：Go 采集器进入 JQKJ，补齐现场协议与配置导入
阶段 2：明确冻结 maiyata/saas 原 WPF 交付物，仅作为客户已购买产品继续维护
阶段 3：新增 WEB 云管端，对标 iiotgateway 的 B/S 菜单能力，但不做 WPF 式曲线趋势
阶段 4：新增移动端 APP，作为演示与远程查看重点能力
```

关键原则：

- `F:\maiyata\saas\collector` 的 Go 采集器是 JQKJ 新数采平台的主干。
- `F:\maiyata\saas\desktop` 的 WPF 客户端是原客户购买交付物，**绝对不动**。
- JQKJ 不改造 WPF，不往 WPF 加功能，不把 WPF 绑进新平台。
- 如未来客户明确需要 WPF 客户端，再基于新项目单独移植/修改，不污染原交付。
- 新 WEB 云管端只做管理、配置、监控、报表、授权、日志，不做 WPF 的 WINCC 曲线深度交互。
- 移动端 APP 是后期重点，但不在 Go 采集器底座稳定前启动。

## 2. 三端定位

| 端 | 定位 | 是否属于 JQKJ 新平台 | 说明 |
|---|---|---|---|
| WPF | 原 maiyata/saas 客户交付客户端 | 否，冻结并存 | 不改造、不加功能、不接入 JQKJ 新主干 |
| WEB 云管端 | JQKJ 云端管理入口 | 是 | 对标 iiotgateway：设备/点位/协议/监控/日志/授权/运行控制 |
| 移动 APP | JQKJ 移动端标配 | 是 | 后期重点；安灯总览、报警推送、关键 KPI、远程状态查看 |
| Go 采集器 | JQKJ 数采底座 | 是 | 多租户、协议驱动、数据管道、REST/WS/SSE、授权、诊断 |

## 3. 阶段 1：Go 采集器进 JQKJ 并补强协议（2-4 周）

目标：把 Go 采集器作为 JQKJ 数采底座纳入仓库，同时补回 GenCollector/iiotgateway 侧丢失的现场协议能力。

### 3.1 最小落地目录

建议采用：

```text
JQKJ/
├─ go-collector/
│  ├─ cmd/
│  ├─ internal/
│  ├─ driver/
│  ├─ migrations/
│  ├─ go.mod
│  ├─ README.md
│  └─ Makefile 或 scripts/
├─ src/Collector/GenCollector        # 保留为协议参考/现场 PoC
└─ docs/architecture
```

注意：
- 不把 `F:\maiyata\saas\desktop` 拉进 JQKJ。
- 不把 WPF 原项目作为 JQKJ 模块。
- 只移植 collector 侧必要内容，避免把原 SaaS 商业代码库整体混入新项目。

### 3.2 阶段 1 任务

1. **Go 采集器纳管**
   - 将 `F:\maiyata\saas\collector` 需要的 Go 工程复制/迁移到 `JQKJ/go-collector/`。
   - 保留 module 边界，先验证 `go build -tags all_drivers`。
   - 增加 JQKJ 本地 CI：Linux/Windows build + `go test ./...`。
   - 保留原采集器的 S7/OPC UA/Modbus、多租户、API、pipeline、license、diagnostics 能力。

2. **现场协议补强**
   - 新增 `mitsubishi_remote` 驱动：短期封装 `RemoteComm.dll`，优先用独立 DriverHost 子进程隔离 32-bit 驱动。
   - 新增/补全 CNC 品牌变量模板：三菱、新代、广数、Fanuc、西门子。
   - 新增 `var_info_*.ini` / `device_*.ini` 导入器，将 GenCollector 侧语义变量映射迁到 Go 的 tenant/device/tag 模型。
   - 补 Modbus 完成度：TCP/RTU、读写、数据类型、地址规则、异常 quality。
   - 补 OPC UA 配置模板与现场验收样例。

3. **稳定性回归**
   - 跑原 Greenfield Smoke 等价脚本，至少覆盖 `/healthz`、`/readyz`、login、devices、tags、samples。
   - 对 S7/OPC UA/Modbus 分别做 mock 或模拟器验收。
   - 现场配置 dry-run：导入一组三菱/新代/广数设备与点位，验证不破坏稳定行为。

### 3.3 阶段 1 验收

- [ ] `JQKJ/go-collector` 可独立编译。
- [ ] `all_drivers` 构建可包含 S7/OPC UA/Modbus。
- [ ] 至少一个 CNC/三菱 RemoteComm 驱动有可用封装或 DriverHost 方案。
- [ ] `var_info_*.ini` 导入器可生成 Go 侧 devices/tags 配置。
- [ ] 原采集器的租户/API/实时/存储/授权/诊断链路不被破坏。
- [ ] `F:\maiyata\saas` 原项目文件未被修改。

## 4. 阶段 2：冻结原 WPF 交付物（0 开发，1 份治理文档）

这个阶段不是开发阶段，是边界声明。

### 4.1 规则

- `F:\maiyata\saas\desktop` 保持冻结。
- 原 WPF 客户端只按原客户合同继续维护，不与 JQKJ 共享代码。
- 新的 JQKJ WEB/移动端不依赖 WPF 工程。
- 如果未来要服务新客户 WPF 客户端，从原 WPF 项目复制或派生到新工程，再修改，不在原项目上动刀。

### 4.2 需要落地的文档

- 新增 ADR：`docs/architecture/adr/ADR-0005-Freeze-maiyata-saas-WPF-delivery.md`
- 新增部署/维护说明：`docs/deployment/wpf-frozen-delivery.md`

内容至少说明：
- 原 WPF 属于客户已购买交付物，变更需客户确认。
- JQKJ 新平台与 WPF 并存，数据平面可同接采集器，但代码仓库不共享。
- WPF 曲线/标尺/WinCC 操作能力不在 JQKJ WEB 端复刻，避免功能漂移。

## 5. 阶段 3：WEB 云管端（3-5 周）

目标：做 iiotgateway 式 B/S 菜单配置与运行控制，但不做 WPF 趋势深度交互。

### 5.1 对标 iiotgateway 的核心菜单

| 菜单 | 能力 | 是否必须 |
|---|---|---|
| 设备管理 | 设备列表、新增/删除、启停、连接参数、模板、测试连接 | 必须 |
| 点位管理 | 点位 CRUD、地址校验、批量导入/导出、协议提示 | 必须 |
| 协议/驱动 | 驱动列表、能力、连接参数、模拟模式 | 必须 |
| 实时监控 | 设备在线状态、最近样本、队列积压、重连状态 | 必须 |
| 历史查询 | 点位/设备维度的历史曲线/表格，支持导出 | 必须，但不做 WinCC 标尺 |
| 报警 | 报警事件、确认、归档、过滤 | 必须 |
| 日志诊断 | 结构化日志、trace_id、ring buffer、文件日志 | 必须 |
| 授权 | 状态、剩余天数、激活、机器码 | 必须 |
| 用户/租户 | 多租户、API key、角色、权限 | 商用必须 |
| 运行控制 | 启停设备、重载配置、诊断、降级 | 必须 |

### 5.2 技术建议

- 前端：Vue 3 + Vite + TypeScript + Ant Design Vue。
- 图表：ECharts 只做管理端/历史端轻量曲线，不追求 WPF WinCC 曲线体验。
- 实时：WebSocket/SSE，消费 Go 采集器现有 EventHub/API。
- 后端：优先直接暴露 Go 采集器 REST API；若需要 Web 专用聚合接口，新增 BFF 薄层，不重复实现业务真相。

### 5.3 阶段 3 验收

- [ ] WEB 可在浏览器完成：登录 → 设备 → 点位 → 启停 → 历史查询 → 报警 → 日志 → 授权。
- [ ] WEB 不调用任何协议客户端，所有协议能力由 Go 采集器承担。
- [ ] WEB 不做 WPF 曲线/标尺/工具栏深度交互。
- [ ] 所有配置写操作经 Go 采集器 API 落库，不直写数据库。
- [ ] 移动端预留必要只读 API，但不依赖 WEB 页面跳转。

## 6. 阶段 4：移动 APP（4-6 周，重点）

目标：让 JQKJ 数采平台具备可演示的移动端标配能力。

### 6.1 定位

移动端 APP 不追求完整管理端，重点解决“客户一演示就看有没有”的问题。

建议技术：
- 首选 Flutter。
- 若团队强 Vue/React，可用 React Native。
- 不建议做“移动端 Web/套壳 WebView”，现场体验弱，推送和离线缓存也差。

### 6.2 MVP 范围

移动端第一版只做 4 个高频场景：

1. **登录/租户**
   - API key/token 登录
   - 记住登录态
   - 切换租户（如需要）

2. **安灯/总览**
   - 产线或工厂红黄绿
   - 在线设备数
   - 当前报警数
   - 最近 1h 关键 KPI

3. **报警中心**
   - 实时报警推送
   - 历史报警列表
   - 确认/处理
   - 按设备/产线过滤

4. **设备状态与关键点位**
   - 设备列表
   - 设备在线/离线
   - 当前值
   - 最近更新时间
   - 最近 1h 迷你趋势（轻量，不做深度曲线）

### 6.3 后续增强

- 推送：FCM/APNs，依赖 Go 侧报警事件。
- 离线：最后值缓存到本地 SQLite。
- 远程操作：启停设备、确认报警、配置重载（需权限控制）。
- 报表：日报/周报导出。

### 6.4 阶段 4 验收

- [ ] APP 可安装到 Android/iOS 测试机。
- [ ] 登录 JQKJ 平台并显示当前租户。
- [ ] 安灯总览页可查看设备在线率和当前报警。
- [ ] 报警中心可实时接收新增报警。
- [ ] 断网时显示最后缓存值并提示离线。
- [ ] 不复制 WPF 趋势深度交互，只保留轻量迷你趋势。

## 7. 建议时间线

| 阶段 | 周期 | 产出 |
|---|---:|---|
| 阶段 1：Go 底座 + 协议补强 | 2-4 周 | `JQKJ/go-collector` 可编译、可运行、可导入 INI、CNC 驱动可用 |
| 阶段 2：WPF 冻结治理 | 0-1 周 | ADR + 部署文档，明确不改原 WPF |
| 阶段 3：WEB 云管端 | 3-5 周 | iiotgateway 式管理菜单 + 实时/历史/报警/授权/日志 |
| 阶段 4：移动 APP | 4-6 周 | 登录 + 安灯 + 报警 + 设备关键点位 |

总周期：约 **8-15 周**（视 CNC 协议补强深度与 WEB/APP 人力并行度）。

## 8. 风险与红线

| 风险 | 红线 |
|---|---|
| 误改原 maiyata/saas WPF | 原项目冻结，任何修改需客户授权 |
| Go 采集器进 JQKJ 后破坏现场稳定 | 先跑原 Smoke，再做协议扩展，不做核心管道大改 |
| WEB 端做成 WPF 趋势替代品 | WEB 只做管理/历史/报警/授权，不深度复刻 WinCC 曲线 |
| 移动端做成 Web 套壳 | 移动端用 Native/Flutter，不做 H5 套壳 |
| 三端各造协议栈 | 协议能力只在 Go 采集器，三端只消费 REST/WS/SSE |
