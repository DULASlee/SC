# GenCollector —— 通用、配置驱动、无授权的工业采集器

基于工作区既有采集器族（Go `iot_CNC_PLC_IMM` / .NET `LnkCollector` / `MelCollector` / `HanBaCollector`）
的反编译与分析重建而来。目标是：**配置驱动、协议可插拔、去掉授权墙、保留原 MQTT 报文契约**，
让你只需在其上开发界面即可。

## 已实现

- ✅ **配置驱动**：完全复用既有 INI 契约（`setting / device_* / var_info_* / var_group_* / protocol_*`）
- ✅ **统一语义变量模型**：跨品牌一致的 `STS / spindleSpeed / products / machXYZ / alarms …`（~40 项，见 `var_info_cnc.ini`）
- ✅ **MQTT 报文契约**与原 `LnkCollector` 一致：
  ```json
  { "properties": [ { "MeasEncoding":"STS", "MeasName":"运行状态", "value":[0.0],
                      "TimeStamp":1789617308883, "DeviceEncoding":"CNC-02" } ] }
  ```
  发布主题：`<mqttPrefix><mqttDeviceId>/<group>`（如 `/YLCY/CNC/CNC-01/realtime`）
- ✅ **协议驱动（可插拔）**：
  - `MitsubishiCncDriver`：直接复用原机 `RemoteComm.dll`（PInvoke），真实可读三菱 CNC
  - `HslPlcDriver`：基于开源 `HslCommunication`，覆盖 Modbus / 三菱PLC / 西门子PLC / 欧姆龙
  - `SimDriver`：无硬件时合成数据，便于 UI / 平台联调
- ✅ **授权已移除**：`setting.ini` 中的 `authCode / sn / devId / authMsg` 仅作信息保留，**引擎不再做任何设备数或授权校验**，可作为通用采集器部署任意数量设备。

## 目录结构

```
GenCollector/
├─ GenCollector.csproj        # net8.0 / win-x86 / 自包含
├─ Models.cs                  # 配置模型 + 极简 INI 解析器
├─ ConfigLoader.cs            # 加载全部 INI
├─ MqttPublisher.cs           # MQTT 发布（HslCommunication.MQTT）
├─ Program.cs                 # 入口
├─ Drivers/
│  ├─ IDeviceDriver.cs        # 驱动接口（协议与引擎解耦）
│  ├─ MitsubishiCncDriver.cs  # 三菱 CNC（RemoteComm.dll）
│  ├─ HslPlcDriver.cs         # 通用 PLC（HslCommunication）
│  ├─ SimDriver.cs            # 模拟驱动
│  └─ DriverFactory.cs        # 协议族 → 驱动 的路由表
├─ Core/CollectorEngine.cs     # 主循环（每设备每变量组按节拍采集并发布）
├─ RemoteComm.dll             # 原机三菱驱动（32 位，已随包复制）
└─ config/                    # 由既有 INI 复制而来（可编辑）
```

## 构建与运行

> 本工程为 **win-x86 自包含**，因 `RemoteComm.dll` 是 32 位原生库；发布包自带 x86 运行时，任意 Windows 可直接运行。

```powershell
cd GenCollector
dotnet publish -c Release -r win-x86 --self-contained true
# 产物在 bin\Release\net8.0\win-x86\publish\
.\bin\Release\net8.0\win-x86\publish\GenCollector.exe --simulate --no-mqtt
```

常用参数：
- `--simulate`：所有设备用模拟数据（无硬件也能出数，便于开发 UI）
- `--no-mqtt`：不连 MQTT broker，仍生成数据并触发 `OnPublish`（本地联调用）
- `--config <dir>`：指定配置目录（默认 `./config`）

正常运行（需可达的 MQTT broker）：
```powershell
GenCollector.exe            # 读 config/setting.ini 的 mqttServer
```

## 如何新增一台设备（只改配置，不改代码）

编辑 `config/device_cnc.ini`，新增一行（节内）：
```
CNC-99={"id":"CNC-99","ip":"192.168.3.99","port":"8193","protocol":"fanuc_cnc:fanuc_v1","mqttDeviceId":"CNC-99","use":"1"}
```
重启即可。协议族 `fanuc_cnc` 目前由 `SimDriver` 兜底（见下方“扩展协议”）。

## 如何新增 / 修正变量映射

编辑 `config/var_info_<family>.ini`，每个变量：
```
spindleSpeed={"id":"spindleSpeed","addr":"<真实地址>","remark":"主轴速度","dataType":"float","group":"realtime","use":"1"}
```
- `addr`：真实协议地址（宏号 / PLC 地址 / 寄存器地址）
- `ReadType`（扩展字段）：`macro` / `plc` / `reg`，供 `MitsubishiCncDriver` 判断读取方式
- `group`：`realtime` / `tech` / `spc`（对应 `var_group_*.ini` 的轮询节拍）

### 三菱 CNC 已知地址速查（来自原 `LnkCollector`  demonstr 实证）
| 语义变量 | 读取方式 | 地址 |
|---|---|---|
| 加工时间 WorkTime | macro | 33868 |
| 运行时间 RunTime | macro | 2097 |
| 切削时间 CutTime | macro | 33565 |
| 零件数 Products | macro | 33869 |
| 运行中 RunStatus | plc | 42.0 |
| 暂停中 StopStatus | plc | 42.1 |
| 告警 WarnStatus | plc | 50.14 |

把上述 `addr` 填进 `var_info_cnc.ini` 的 `[mitsubishi_cnc]` 对应项即可让三菱设备直连真实数据。

## 扩展新协议（只写驱动，不动引擎）

1. 在 `Drivers/` 实现 `IDeviceDriver`（Connect / ReadVariables / Disconnect）。
2. 在 `Drivers/DriverFactory.cs` 的 `switch` 里注册协议族。
3. 在 `var_info_<family>.ini` 写好变量→地址映射。
完成。引擎会自动按 `device_*.ini` 的 `protocol` 选用。

## 已知限制 / 下一步

- 非三菱的 CNC 品牌（`fanuc_cnc` / `siemens_cnc` / `haidehan620` / `gsk` / `syntec` / `brother` / `knd` / `mazak`）
  的“符号变量 → 真实寄存器地址”映射表原本内嵌在 Go 二进制 `iot_CNC_PLC_IMM.exe` 中。
  当前由 `SimDriver` 兜底；要直连真实数据，需：
  - 从设备手册获取各品牌寄存器地址填入 `var_info_*.ini`，**或**
  - 对 `iot_CNC_PLC_IMM.exe` 反编译提取品牌地址映射表（Ghidra 已就绪，可继续做）。
- UI 由你侧实现：引擎已通过 `OnPublish(device, topic, json)` 事件暴露实时数据，
  也可直接订阅 MQTT `<prefix>#` 做看板。

## 授权说明

原 `setting.ini` 含 `authCode / sn / authMsg=试用版本，限制1台设备` 等授权字段。
本工程**不读取、不校验**这些字段，因此不存在设备数或授权限制，可作为通用采集器自由部署。
