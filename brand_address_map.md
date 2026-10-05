# 全品牌地址映射表（从 Go 二进制 iot_CNC_PLC_IMM.exe 反编译提取）

> 来源：Ghidra 反编译 `decompile.txt` 中各品牌 `map[string]cnc.<Brand>KeyData` 映射。
> 每个语义变量对应一个 KeyData 结构，其中 `addrCode` 为该变量在对应 CNC 协议栈中的命令/地址码。

## 结构说明

- 每个 `KeyData` 条目：`f0` 指向一个 64 字节结构，内含该变量的协议地址码（addrCode 列）。
- `f3/f4` 为结构内的类型/长度标记。
- 三菱（MitsubishiCNC）地址码落在 `74803~74806` 区间，按变量组分；可直接用于 `RemoteComm` 宏/PLC 读取（见 GenCollector 已知地址速查）。
- 发那科（Fanuc）地址码为 `40` / `68` 两组（对应 FOCAS 函数族）。

## fanuc  （16 个语义变量）

| 语义变量 (MeasEncoding) | addrCode | f3 | f4 |
|---|---|---|---|
| systemInfo | 40 | 0x10 |  |
| spindleSpeed | 40 | 0xd | 0x1c |
| spindleLoad | 40 | 0xd | 0x1c |
| spindleSpeedSet | 40 |  | 0x1c |
| feedRate | 40 | 0xd | 0x1c |
| feedRateSet | 40 | 0xd | 0x1c |
| runInfo | 40 | 0x20 |  |
| progNum | 40 | 0x11 |  |
| runTime | 68 | 0x12 |  |
| powerOnTime | 40 | 0xe | 0x24 |
| cutTime | 68 | 0x12 |  |
| cycleTime | 68 | 0x12 | 0x24 |
| alarms | 40 | 0x21 |  |
| toolNum | 40 | 0xd | 0x1c |
| products | 40 | 0xd | 0x1c |
| input_start | 6496 |  |  |

## mitsubishi  （15 个语义变量）

| 语义变量 (MeasEncoding) | addrCode | f3 | f4 |
|---|---|---|---|
| modeOrg | 74803 |  |  |
| statusOrg | 74803 |  |  |
| alarmOrg | 74740 |  |  |
| spindleSpeed | 74804 |  |  |
| spindleSpeedSet | 74804 |  |  |
| spindleLoad | 74805 |  |  |
| spindleTemp | 74805 |  |  |
| spindleCurrent | 74805 |  |  |
| feedRate | 74806 |  |  |
| feedRateSet | 74806 |  |  |
| runTime | 74807 |  |  |
| powerOnTime | 74808 |  |  |
| progName | 74809 |  |  |
| products | 74806 |  |  |
| toolNum | 74807 |  |  |

## simens  （43 个语义变量）

| 语义变量 (MeasEncoding) | addrCode | f3 | f4 |
|---|---|---|---|
| CNC_ID | 74755 |  |  |
| ncType | 74756 |  |  |
| versionInfo | 74756 |  |  |
| manufactureDate | 74778 |  |  |
| modeOrg | 74778 |  |  |
| statusOrg | 74756 |  |  |
| products | 74756 |  |  |
| setProducts | 74757 |  |  |
| feedRateSet | 74757 |  |  |
| feedRateAct | 74757 |  |  |
| feedRate | 74757 |  |  |
| spindleSpeedSet | 74758 |  |  |
| spindleSpeed | 74758 |  |  |
| spindleRate | 74758 |  |  |
| runTime | 74758 |  |  |
| remainTime | 74759 |  |  |
| progName | 74759 |  |  |
| currentPro | 78183 |  |  |
| axisName | 74762 |  |  |
| machX | 74761 |  |  |
| machY | 74761 |  |  |
| machZ | 74761 |  |  |
| relX | 74761 |  |  |
| relY | 74761 |  |  |
| relZ | 74761 |  |  |
| resX | 74761 |  |  |
| resY | 74761 |  |  |
| resZ | 74761 |  |  |
| toolNum | 74759 |  |  |
| toolDNum | 74759 |  |  |
| toolHNum | 74760 |  |  |
| toolXLen | 74760 |  |  |
| toolZLen | 74760 |  |  |
| toolRadiu | 74760 |  |  |
| toolEdge | 74761 |  |  |
| driveVoltage | 74762 |  |  |
| driverCurrent | 74762 |  |  |
| driverLoad1 | 74762 |  |  |
| driverLoad2 | 74763 |  |  |
| driverLoad3 | 74763 |  |  |
| driverTemp | 74763 |  |  |
| almCount | 74769 |  |  |
| alarms | 74763 |  |  |

## 已知真实地址（已验证可直连）

- **Mitsubishi CNC（RemoteComm.dll）**：宏 33868=加工时间、2097=运行时间、33565=切削时间、33869=零件数；PLC 42.0=运行、42.1=暂停、50.14=告警。
- 其余品牌（fanuc/simens/haidehan/gsk/syntec/brother/knd/mazak）的寄存器级地址需结合设备手册或 Go 源码（`E:/workspace/.../cnc/<brand>_commands.go`，二进制内仅保留路径）做二次解码；本表给出的 `addrCode` 即 Go 协议栈内部寻址码，可作为驱动实现的索引。

## 原始数据

完整逐字段（含 f0/f1/f2 原始字节）见 `brand_address_raw.csv`。
