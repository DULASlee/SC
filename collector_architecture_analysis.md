# 采集器架构与可重构性分析

> 基于工作区内已发布二进制 + 反编译结果 + 配置文件 的综合分析
> 生成时间：2026-09-17

---

## 1. 采集器家族（已确认）

| 采集器 | 路径 | 语言/运行时 | 协议驱动 | 形态 |
|---|---|---|---|---|
| **iot_CNC_PLC_IMM** | `CNC\iot_CNC_PLC_IMM.exe` | **Go 64-bit** | 原生 CNC 驱动 (Fanuc/Mitsubishi/Siemens…) | 边缘网关（配置驱动）|
| **LnkCollector** | `CNC04\LnkCollector.exe` | **.NET Core 3.1** | `HslCommunication 12.3.2`（开源工业协议库）| 现代配置驱动采集器 |
| **MelCollector** | `DHH04\MelCollector.exe`、`MZS01\MelCollector.exe` | C++ (32-bit) | Paho MQTT C++ + `MknEdmRm.dll` | MQTT 数据上报 |
| **HanBaCollector** | `DHH02\HanBaCollector.exe` | C++ (32-bit) | POCO + `HslCommunication.dll` | 特定设备采集 |

**结论**：这是同一套**多协议、配置驱动**采集平台的不同实现/代次。`LnkCollector`（.NET + HslCommunication）与 `iot_CNC_PLC_IMM`（Go）是其中**最现代、最完整**的两个，且都采用「配置驱动」内核——这正是你「只差 UI」设想的基础。

---

## 2. 运行架构（三层 + 数据流向）

```
┌─ 配置层（纯文本 INI，可手写/UI 编辑）──────────────────────────┐
│ setting.ini     全局：MQTT 代理、topic 前缀、本地端口、授权码     │
│ device_*.ini    设备清单：id / ip / port / protocol / mqttId    │
│ protocol_*.ini  协议节拍：pollingInterval / tagInterval          │
│ var_info_*.ini  变量模型：按品牌给出语义变量→地址映射           │
│ var_group_*.ini 变量组 + 轮询周期（如 realtime 每 20s）         │
└───────────────────────────────────────────────────────────────┘
                          │ 加载
┌─ 引擎层（无界面核心，语言无关）────────────────────────────────┐
│ ① 解析配置 ② 每个启用设备按 protocol 启动一个驱动协程/线程     │
│ ③ 每轮询周期：读变量组 → 按 addr 读取原始值 → 归一化为语义变量 │
│ ④ 组装 payload → 发布到 MQTT: <prefix><mqttDeviceId>/<var>      │
└───────────────────────────────────────────────────────────────┘
                          │ 调用
┌─ 协议驱动层（唯一的“硬骨头”）─────────────────────────────────┐
│ fanuc_cnc / mitsubishi_cnc / siemens_cnc / haidehan620 / gsk /  │
│ syntec / brother / knd / mazak  → CNC 驱动（FOCAS/MELSEC/S7…）  │
│ modbus / siemens_plc / melsec / omron …  → PLC 驱动            │
│ 实现：HslCommunication(.NET) 或 Go 原生驱动                     │
└───────────────────────────────────────────────────────────────┘
```

数据流向（日志与 `setting.ini` 双重印证）：
`设备(PLC/CNC) ──协议──▶ 驱动 ──▶ 语义变量 ──▶ MQTT Broker(192.168.0.89:1883)`，topic 前缀 `/YLCY/CNC/`，qos=0。

---

## 3. 配置契约（已完整还原的 INI Schema）

**`setting.ini`**（样例）
```
appId=CNC
mqttServer=192.168.0.89:1883
mqttPrefix=/YLCY/CNC/
clientId=cnc
port=8080            # 本地管理/调试端口
authCode=...         # 授权（试用版限制 1 台设备）
```

**`device_cnc.ini`**（设备 = JSON 行）
```
CNC-01={"id":"CNC-01","ip":"192.168.3.11","port":"683",
        "protocol":"mitsubishi_cnc:mitsubishi_v3","mqttDeviceId":"CNC-01","use":"1"}
```
→ 协议为 `家族:版本` 格式，已见 `fanuc_cnc:fanuc_v1` / `mitsubishi_cnc:mitsubishi_v3` / `siemens_cnc:siemens_v1`。

**`var_info_cnc.ini`**（统一语义变量 × 9+ 品牌分区）—— 这是整个平台最有价值的领域知识：
```
[siemens_cnc]
STS={"id":"STS","addr":"STS","remark":"运行状态","dataType":"int","group":"realtime","use":"1"}
spindleSpeed={"...","remark":"主轴速度","dataType":"float","group":"realtime","use":"1"}
...
[fanuc_cnc]  /[mitsubishi_cnc] /[haidehan620_cnc] /[gsk_cnc] /[syntec]
[brother] /[knd] /[mazak]
```
统一语义变量集（跨品牌一致）：运行状态、操作模式、工件数、坐标 XYZ、主轴速度/负载/倍率、进给速度、刀具号、急停、告警、运行/加工/循环时间、程序号/名、生产日期、版本等 ~40 个。

**`var_group_cnc.ini`**
```
[var_group_cnc]
realtime={"id":"realtime","timer":"20"}   # 实时组每 20s 轮询
tech={"id":"tech","timer":"0"}
spc={"id":"spc","timer":"0"}
```

---

## 4. 协议驱动层（关键：为什么“可重建”）

- **`LnkCollector` 直接依赖 `HslCommunication 12.3.2`**（见 `LnkCollector.deps.json`）。这是国内最流行的**开源（MIT）工业协议库**，原生支持 Modbus、西门子、三菱、欧姆龙、Fanuc、AB 等。**意味着协议驱动几乎不需要逆向——直接引用该库即可。**
- **`iot_CNC_PLC_IMM`（Go）** 自带 CNC 原生驱动（反编译见 `internal/…`、源码路径 `machine_base.go`），覆盖 Fanuc/Mitsubishi/Siemens 等。其协议知识也可用 **公开协议规范 + 开源 Go 客户端**（如 snap7 对应 S7、FOCAS 绑定对应 Fanuc）重建。
- 两个实现**共享同一套 INI 配置契约**，协议层被干净地隔离在「驱动」里。

---

## 5. 这个采集器到底做什么（功能还原）

它是一个**边缘侧多协议数据采集网关**，面向工厂的 CNC 数控机床 / PLC / 注塑机（IMM）：
1. 按 `device_*.ini` 连接多台设备（不同品牌、不同协议）；
2. 按 `var_info_*.ini` 把各品牌私有寄存器/地址**映射为统一的语义变量**（运行状态、主轴、坐标、计数、告警…）；
3. 按 `var_group_*.ini` 的节拍**周期性采集**；
4. 将结果以 JSON 发布到 **MQTT 代理**，供上层平台/看板订阅；
5. 本地 `port=8080` 提供管理/调试接口；带授权许可（试用限制 1 台）。

---

## 6. 能否重构为“只差 UI 的可用采集器”？——**结论：可以，且比逆向二进制更优**

可行原因（皆有证据支撑）：
1. **架构已是配置驱动**：协议、设备、变量三层分离，引擎与协议解耦。新增一种设备 = 加一行 `device_*.ini` + 一份 `var_info_*.ini`，不改代码。
2. **协议驱动落在开源库上**：`HslCommunication` 已公开实现绝大多数工业协议，CNC 协议也有公开规范与开源实现——**无需从零逆向协议**。
3. **变量/设备模型已完整还原**：`var_info_cnc.ini` 的 ~40 个语义变量 × 9+ 品牌映射是可复用的最高价值资产。
4. **.NET 引擎本身可被反编译为 C# 源码**：`LnkCollector.dll` 是托管程序集，用 dnSpy/ILSpy 可近乎 1:1 还原源码——这等于“直接拿到可用源码”，在其上加 UI 即可。
5. **数据流向标准**：配置→轮询→MQTT 发布，逻辑简单、易重写。

“只需自己开发界面”具体指：引擎是无界面服务，UI 负责**设备管理（增删设备）、变量映射编辑、实时数据看板（订阅 MQTT）、授权/设置管理**。这些与采集内核正交。

---

## 7. 重建蓝图（分步）

**步骤 A — 取回 .NET 引擎源码（最快拿到“可用源码”）**
- 用 dnSpy/ILSpy 反编译 `CNC04\LnkCollector.dll` + `HslCommunication.dll` → 得到 C# 工程。
- 直接引用 NuGet 上的 `HslCommunication`/`Newtonsoft.Json`/`System.IO.Ports`，工程即可编译运行。
- 这本身就是一个**源码可用、配置驱动的采集器**。

**步骤 B — 对齐配置契约**
- 沿用已还原的 INI schema（`setting/device_*/protocol_*/var_info_*/var_group_*`）。
- 将 `var_info_cnc.ini` 的语义变量集作为“变量字典”沉淀为配置/代码常量。

**步骤 C — 补齐协议驱动**
- CNC 品牌：用 `HslCommunication` 的 `FanucSeries`/`MelsecSeries`/`SiemensSeries` 等类型实现 `fanuc_cnc/mitsubishi_cnc/siemens_cnc/…` 驱动。
- PLC：Modbus/西门子/三菱/欧姆龙 同上库直接支持。
- 如需 Go 边缘端：以 `iot_CNC_PLC_IMM` 配置契约为准，用 Go 开源协议库重实现引擎（可选，非必须）。

**步骤 D — 开发 UI（唯一需要你写的部分）**
- 设备管理页：编辑 `device_*.ini`（增/删/启停设备、选协议）。
- 变量映射编辑器：编辑 `var_info_*.ini`（变量→地址映射）。
- 实时看板：订阅 MQTT `<prefix><deviceId>/#` 展示数据。
- 设置/授权管理页：编辑 `setting.ini`（MQTT 连接、端口）。

**步骤 E — 去除/替换授权**
- `setting.ini` 的 `authCode` 与 `license.lic`/`private.pem` 是许可校验，需移除或自实现。

---

## 8. 难点与风险（诚实提示）

1. **品牌→真实地址映射**：`var_info_*.ini` 里的 `addr` 是**符号名**（如 `"STS"`），真正的寄存器/DB 地址藏在引擎代码的“符号→协议地址”表中（二进制内）。要完整复刻，需从 `LnkCollector`(C#) 或 `iot_CNC_PLC_IMM`(Go) 反编译出该映射表；或利用 `HslCommunication` 的**强类型 API**（它把这些语义直接暴露为方法/属性）来间接获得。
2. **MQTT payload 具体 JSON 结构**：需反编译发布函数确认字段名/结构（或自己定义，因两端都可控）。
3. **授权/加密**：`license.lic`/`private.pem` 涉及许可校验，重建时需处理。
4. **Go 边缘端驱动复刻成本**高于 .NET 端（无等价开源 Go 工业库全覆盖）；若边缘节点是 Windows，直接用步骤 A 的 .NET 引擎最省事。

---

## 9. 建议的下一步（可让我继续执行）

1. **反编译 `LnkCollector.dll` 为 C# 源码**（需先准备 dnSpy/ILSpy；可帮你下载或用其他方式提取）。
2. 从 `iot_CNC_PLC_IMM`(Go) 反编译提取**符号→地址映射表**，补全 9+ CNC 品牌的变量字典。
3. 基于已还原的 INI 契约，**搭一个最小可运行配置驱动采集器骨架**（Go 或 C#/HslCommunication），验证“加设备只改配置、协议驱动可插拔”。
4. 还原 MQTT 上送 payload 的 JSON 结构，作为看板对接契约。

> 一句话：**架构本就是配置驱动、协议层可复用开源库、.NET 引擎可反编译为源码——完全能重建出一个“只差 UI”的可用采集器。真正的工程量集中在“品牌地址映射表”（可反编译获得）和 UI 本身。**
