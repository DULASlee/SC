# JQKJ Go 采集器底座 + WEB 云管端 + 移动 APP 实施计划

> 依据：`docs/architecture/go-collector-jqkj-roadmap.md`
> 原则：原 `F:\maiyata\saas` 的 WPF 交付物冻结，JQKJ 只移植并补强 Go 采集器。

## 阶段 1：Go 采集器进 JQKJ

### 任务 1.1 仓库纳管

- 目标：在 JQKJ 建立独立 `go-collector/` 目录。
- 动作：
  - 从 `F:\maiyata\saas\collector` 复制 collector 必要代码。
  - 保持 Go module 可独立编译。
  - 增加 JQKJ 根目录 build/test 脚本。
- 验收：
  - `go build -tags all_drivers ./...` 通过。
  - `go test ./...` 通过。
  - `F:\maiyata\saas` 原项目未被修改。

### 任务 1.2 本地 CI

- 目标：把 Go 采集器纳入 JQKJ 门禁。
- 动作：
  - Linux 侧：build + unit test + smoke。
  - Windows 侧：build `win-x86` 或 `win-amd64`，视 DriverHost 需求。
  - 输出可执行产物到 `artifacts/`。
- 验收：
  - CI 能生成可运行的 collector 二进制。
  - CI 能跑 `/healthz`、`/readyz`、login、devices、tags、samples 冒烟。

### 任务 1.3 CNC/现场协议补强

优先级：

1. 三菱 RemoteComm
2. Modbus
3. 新代 CNC
4. 广数 CNC
5. Fanuc / OPC UA 配置模板

要求：
- 不把 32-bit `RemoteComm.dll` 直接拖进 64-bit 主进程；优先 DriverHost 子进程隔离。
- 新增驱动必须有 mock 测试。
- 未实现协议不能静默 fallback 到模拟数据；生产模式必须显式失败或明确 `simulate=true`。

### 任务 1.4 INI 导入器

- 目标：把 GenCollector 侧 `device_*.ini`、`var_info_*.ini`、`var_group_*.ini` 导入 Go 的 tenant/device/tag 模型。
- 输出：
  - 导入报告：成功设备数、成功点位数、失败原因。
  - 可选 dry-run 模式。
- 验收：
  - 一组三菱/新代/广数样例可导入为 Go 配置。
  - 原 INI 不自动删除，只做读取。

## 阶段 2：原 WPF 冻结治理

### 任务 2.1 冻结声明

- 动作：
  - 新增 ADR：原 maiyata/saas WPF 为客户交付物，冻结不改。
  - 新增部署/维护文档：原 WPF 的维护边界、客户确认要求。
- 验收：
  - 文档明确“JQKJ 不接入、不修改、不共享模块”。

## 阶段 3：WEB 云管端

### 任务 3.1 最小菜单

- 登录/租户
- 设备管理
- 点位管理
- 实时监控
- 历史查询
- 报警
- 日志诊断
- 授权

### 任务 3.2 功能边界

- 对标 iiotgateway 的 B/S 管理面。
- 不做 WPF 趋势深度交互。
- 曲线仅作为历史查询的轻量 ECharts。
- 所有写操作走 Go API。

### 任务 3.3 验收

- [ ] 浏览器完成主流程：登录 → 设备 → 点位 → 启停 → 历史 → 报警 → 日志 → 授权。
- [ ] 不直写数据库。
- [ ] 不碰协议客户端。

## 阶段 4：移动 APP

### 任务 4.1 技术选型

- 首选 Flutter。
- 不允许 H5/WebView 套壳。

### 任务 4.2 MVP

- 登录/租户
- 安灯总览
- 报警中心
- 设备状态 + 关键点位 + 最近 1h 迷你趋势

### 任务 4.3 验收

- [ ] Android/iOS 可安装。
- [ ] 可登录并显示租户。
- [ ] 可实时接收报警。
- [ ] 离线可显示最后缓存值。
