# RemoteCommHost 隔离计划（RemoteCommHost Isolation Plan）

> 本文档定义将 32-bit `RemoteComm.dll` 隔离到独立 `RemoteCommHost` 进程的实施方案。

---

## 1. 当前状态评估（Current State Assessment）

### 1.1 接口抽象层

| 组件 | 状态 | 说明 |
|------|------|------|
| `IDeviceDriver` 接口 | **已存在** | `GenCollector/Drivers/IDeviceDriver.cs`，定义 Connect/ReadVariables/Disconnect/LastError/DriverName |
| `DriverFactory` | **已存在** | `GenCollector/Drivers/DriverFactory.cs`，根据 protocol 字符串创建对应驱动 |
| `MitsubishiCncDriver` | **直接 PInvoke** | 第 10-17 行直接 `[DllImport("RemoteComm.dll")]` 调用，未通过抽象层 |
| `CollectorEngine` | **已解耦** | 第 59 行 `DriverFactory.Create()`，业务逻辑完全不感知具体驱动 |

**结论**：接口抽象层 **已存在**，但 `MitsubishiCncDriver` 内部直接绑定 `RemoteComm.dll`，未实现传输层解耦。

### 1.2 可替换性分析

| 问题 | 答案 | 说明 |
|------|------|------|
| RemoteComm 是否已抽象？ | **否** | MitsubishiCncDriver 直接 PInvoke，无法替换为 IPC |
| 能否不修改业务逻辑？ | **可以** | CollectorEngine 通过 DriverFactory 使用 IDeviceDriver，驱动替换不影响业务 |
| 需要修改 CollectorEngine 吗？ | **不需要** | 引擎已通过 IDeviceDriver 接口解耦 |

### 1.3 当前项目配置

```
GenCollector.csproj:
- PlatformTarget: x86（强制 32-bit 编译）
- AllowUnsafeBlocks: true（PInvoke 需要）
- RemoteComm.dll: CopyToOutputDirectory（随项目发布）
```

---

## 2. 接口抽象层（Interface Abstraction Layer）

### 2.1 现有 IDeviceDriver 接口

```csharp
// GenCollector/Drivers/IDeviceDriver.cs
public interface IDeviceDriver
{
    bool Connect(DeviceConfig dev, SettingConfig setting);
    Dictionary<string, List<double>> ReadVariables(List<VarInfo> vars);
    void Disconnect();
    string LastError { get; }
    string DriverName { get; }
}
```

### 2.2 建议扩展：IDriverTransport 接口

**目标**：将"如何通信"（PInvoke vs gRPC vs NamedPipe）与"做什么"（读写变量）分离。

```csharp
// GenCollector/Drivers/Transports/IDriverTransport.cs
public interface IDriverTransport
{
    bool Connect(string endpoint);
    void Disconnect();
    byte[] SendReceive(byte[] request);  // 底层 SendReceive
    string LastError { get; }
}

// 本地 PInvoke 传输（当前方式，保持兼容）
public class LocalPInvokeTransport : IDriverTransport { ... }

// gRPC 传输（Phase 2）
public class GrpcTransport : IDriverTransport { ... }

// NamedPipe 传输（Phase 2 备选）
public class NamedPipeTransport : IDriverTransport { ... }
```

### 2.3 重构 MitsubishiCncDriver

```csharp
// Phase 1: 注入传输层，不改变行为
public class MitsubishiCncDriver : IDeviceDriver
{
    private readonly IDriverTransport _transport;
    
    public MitsubishiCncDriver(IDriverTransport transport) 
    { 
        _transport = transport ?? new LocalPInvokeTransport(); 
    }
    
    // 现有方法不变，内部改为 _transport.SendReceive(...)
}
```

**推荐文件**：`GenCollector/Drivers/MitsubishiCncDriver.cs`（重构现有文件）
**新增文件**：`GenCollector/Drivers/Transports/IDriverTransport.cs`
**新增文件**：`GenCollector/Drivers/Transports/LocalPInvokeTransport.cs`

---

## 3. RemoteCommHost 隔离方案（RemoteCommHost Isolation Plan）

### 3.1 触发条件

| 条件 | 状态 | 说明 |
|------|------|------|
| x64 依赖出现 | **未触发** | 当前 GenCollector 强制 x86 |
| Phase 2 开始 | **未开始** | 当前 Phase 0.5 刚验收 |
| 32-bit 驱动需求 | **已存在** | DHH-04 设备需要 RemoteComm.dll |

### 3.2 目标架构

```
Phase 2 目标架构：

┌─────────────────────────────────────────────────────────────────┐
│  GenCollector.exe (64-bit .NET 8)                               │
│     │                                                           │
│     │ gRPC / NamedPipe (localhost)                              │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RemoteCommHost.exe (32-bit x86)                         │   │
│  │     ├── MitsubishiCncDriver (重构后)                     │   │
│  │     └── RemoteComm.dll (32-bit native driver)           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 消息格式

**推荐：gRPC + proto3**

```protobuf
// Protos/device_driver.proto
syntax = "proto3";
package gencollector;

service DeviceDriverService {
    rpc Connect(ConnectRequest) returns (ConnectResponse);
    rpc ReadVariables(ReadVariablesRequest) returns (ReadVariablesResponse);
    rpc Disconnect(DisconnectRequest) returns (DisconnectResponse);
}

message ConnectRequest {
    string device_id = 1;
    string ip = 2;
    int32 port = 3;
}

message ConnectResponse {
    bool success = 1;
    string error = 2;
}

message VarInfo {
    string id = 1;
    string addr = 2;
    string read_type = 3;  // "plc" 或 "macro"
}

message ReadVariablesRequest {
    repeated VarInfo vars = 1;
}

message ReadVariablesResponse {
    map<string, VariableValue> values = 1;
    string error = 2;
}

message VariableValue {
    repeated double values = 1;
}
```

### 3.4 Fallback 策略

当 RemoteCommHost 不可用时：

```csharp
// DriverFactory.cs 逻辑
public static IDeviceDriver Create(string protocol, bool simulate)
{
    if (simulate) return new SimDriver();
    
    // 检查是否需要远程驱动
    if (protocol.StartsWith("mitsubishi_cnc") && RequiresRemoteHost(protocol))
    {
        try {
            return new GrpcDeviceDriver("localhost:50051");  // gRPC 驱动
        }
        catch (Exception ex) {
            Log($"[WARN] RemoteCommHost 不可用，使用模拟驱动: {ex.Message}");
            return new SimDriver();  // 降级模式
        }
    }
    // ... 现有逻辑
}
```

**降级模式**：记录错误日志，使用 SimDriver 继续运行，不阻塞主流程。

---

## 4. 迁移路径（Migration Path）

### Phase 1：接口抽象层（预计 1-2 天）

| 任务 | 输入 | 输出 | 文件 |
|------|------|------|------|
| 1.1 创建 IDriverTransport 接口 | IDeviceDriver 现有定义 | IDriverTransport.cs | `GenCollector/Drivers/Transports/IDriverTransport.cs` |
| 1.2 实现 LocalPInvokeTransport | RemoteComm.dll PInvoke 逻辑 | LocalPInvokeTransport.cs | `GenCollector/Drivers/Transports/LocalPInvokeTransport.cs` |
| 1.3 重构 MitsubishiCncDriver | 现有 MitsubishiCncDriver | 注入传输层的驱动 | `GenCollector/Drivers/MitsubishiCncDriver.cs` |
| 1.4 添加单元测试 | 重构后驱动 | 测试用例 | `GenCollector.Tests/` |

**验收标准**：
- [ ] 现有功能测试通过（编译通过，模拟模式正常）
- [ ] LocalPInvokeTransport 与直接 PInvoke 行为一致
- [ ] 接口可替换（注入 GrpcTransport 即支持远程）

### Phase 2：RemoteCommHost 进程（预计 3-5 天）

| 任务 | 输入 | 输出 | 文件 |
|------|------|------|------|
| 2.1 创建 RemoteCommHost 项目 | proto3 定义 | RemoteCommHost.csproj | `RemoteCommHost/RemoteCommHost.csproj` |
| 2.2 定义 proto 契约 | 设备驱动服务 | device_driver.proto | `RemoteCommHost/Protos/device_driver.proto` |
| 2.3 实现 gRPC 服务 | proto 契约 | GrpcDriverService.cs | `RemoteCommHost/Services/GrpcDriverService.cs` |
| 2.4 集成 MitsubishiCncDriver | 现有驱动 | RemoteCommHost.exe | `RemoteCommHost/Program.cs` |
| 2.5 实现 GrpcTransport | IDriverTransport | GrpcTransport.cs | `GenCollector/Drivers/Transports/GrpcTransport.cs` |
| 2.6 端到端测试 | GenCollector + RemoteCommHost | 集成测试 | `GenCollector.Tests/` |

**验收标准**：
- [ ] RemoteCommHost 可独立启动
- [ ] GenCollector 通过 gRPC 调用 RemoteCommHost
- [ ] 降级模式正常（RemoteCommHost 不可用时使用 SimDriver）
- [ ] 性能基线测试（延迟 < 10ms）

### Phase 3：平台迁移（预计 2-3 天）

| 任务 | 输入 | 输出 |
|------|------|------|
| 3.1 修改 GenCollector.csproj | x86 → x64 | 64-bit 构建 |
| 3.2 发布 RemoteCommHost | x86 独立部署包 | RemoteCommHost.zip |
| 3.3 更新部署文档 | 新的部署架构 | deployment-topology.md |

---

## 5. 文件清单

### 5.1 需修改文件

| 文件 | 变更 |
|------|------|
| `GenCollector/Drivers/MitsubishiCncDriver.cs` | 重构为接受 IDriverTransport |
| `GenCollector/GenCollector.csproj` | Phase 3 移除 PlatformTarget=x86 |

### 5.2 需新增文件

| 文件 | 说明 |
|------|------|
| `GenCollector/Drivers/Transports/IDriverTransport.cs` | 传输层接口 |
| `GenCollector/Drivers/Transports/LocalPInvokeTransport.cs` | 本地 PInvoke 实现 |
| `GenCollector/Drivers/Transports/GrpcTransport.cs` | gRPC 传输实现 |
| `GenCollector/Drivers/Transports/NamedPipeTransport.cs` | NamedPipe 传输（备选） |
| `RemoteCommHost/RemoteCommHost.csproj` | x86 控制台项目 |
| `RemoteCommHost/Protos/device_driver.proto` | gRPC 契约 |
| `RemoteCommHost/Services/GrpcDriverService.cs` | gRPC 服务实现 |
| `RemoteCommHost/Program.cs` | 主机进程入口 |
| `docs/architecture/remote-comm-host-plan.md` | 本文档 |

### 5.3 已读取文件

| 文件 | 用途 |
|------|------|
| `GenCollector/Drivers/IDeviceDriver.cs` | 接口定义参考 |
| `GenCollector/Drivers/MitsubishiCncDriver.cs` | PInvoke 逻辑分析 |
| `GenCollector/Drivers/DriverFactory.cs` | 工厂模式分析 |
| `GenCollector/Drivers/SimDriver.cs` | 模拟驱动参考 |
| `GenCollector/Drivers/HslPlcDriver.cs` | 驱动实现参考 |
| `GenCollector/Core/CollectorEngine.cs` | 业务逻辑分析 |
| `GenCollector/GenCollector.csproj` | 项目配置分析 |
| `docs/architecture/deployment-topology.md` | 部署拓扑参考 |
| `docs/architecture/phase-0-5-acceptance.md` | Phase 0.5 验收状态 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| gRPC 延迟增加 | 采集周期可能延长 | 本地 localhost 延迟 < 1ms，使用连接池 |
| RemoteCommHost 崩溃 | 设备数据中断 | 自动重启机制 + 降级模式 |
| 32-bit/64-bit 进程通信 | 复杂marshalling | 使用 protobuf 自动化序列化 |
| 现有测试失败 | 功能回归 | Phase 1 必须通过所有测试 |

---

## 7. 后续工作

- [ ] Phase 1: 实现 IDriverTransport 接口抽象
- [ ] Phase 2: 创建 RemoteCommHost gRPC 服务
- [ ] Phase 3: GenCollector 迁移到 x64
- [ ] 更新 `deployment-topology.md` 反映新架构
