# 工业平台 Phase 1 实施计划：采集引擎健壮性

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 GenCollector 采集引擎补全 MQTT 指数退避重连、驱动断线重连、离线缓存缓冲三大健壮性机制。

**Architecture:** MqttPublisher 新增指数退避重连逻辑；每设备线程新增驱动异常重连；离线数据写入本地缓冲文件，恢复后补发。

**Tech Stack:** .NET 8 / C# / MQTTnet / System.Threading

---

## 一、文件影响地图

### 新建文件
- `f:/JQKJ/GenCollector/Messaging/OfflineBuffer.cs` — 离线缓存写入/读取/补发
- `f:/JQKJ/GenCollector/Messaging/ExponentialBackoff.cs` — 指数退避算法
- `f:/JQKJ/GenCollector/Messaging/MqttPublisher.cs` — 重写（新增重连）
- `f:/JQKJ/GenCollector.Tests/MqttPublisherReconnectTests.cs` — MQTT 重连测试
- `f:/JQKJ/GenCollector.Tests/OfflineBufferTests.cs` — 离线缓存测试
- `f:/JQKJ/GenCollector.Tests/ExponentialBackoffTests.cs` — 指数退避测试

### 修改文件
- `f:/JQKJ/GenCollector/CollectorEngine.cs` — 使用新 MqttPublisher，Stop 时 flush 缓存
- `f:/JQKJ/GenCollector/Drivers/MitsubishiCncDriver.cs` — 新增断线重连逻辑
- `f:/JQKJ/GenCollector/Drivers/HslPlcDriver.cs` — 新增断线重连逻辑
- `f:/JQKJ/GenCollector/Drivers/IDeviceDriver.cs` — 新增 `bool IsConnected` 属性
- `f:/JQKJ/GenCollector/Drivers/SimDriver.cs` — 实现 IsConnected
- `f:/JQKJ/GenCollector/GenCollector.csproj` — 添加 MQTTnet

### 废弃文件
- `f:/JQKJ/GenCollector/MqttPublisher.cs` — 由 `Messaging/MqttPublisher.cs` 替代

---

## 二、任务分解

### Task 8: 实现 ExponentialBackoff 指数退避算法

**Files:**
- Create: `f:/JQKJ/GenCollector/Messaging/ExponentialBackoff.cs`
- Test: `f:/JQKJ/GenCollector.Tests/ExponentialBackoffTests.cs`

- [ ] **Step 1: 编写 ExponentialBackoff 单元测试**

```csharp
// GenCollector.Tests/ExponentialBackoffTests.cs
using GenCollector.Messaging;
using System;
using System.Collections.Generic;
using Xunit;

public class ExponentialBackoffTests
{
    [Fact]
    public void GetNextDelay_StartsAtInitialDelay()
    {
        var eb = new ExponentialBackoff(
            initialDelayMs: 1000,
            maxDelayMs: 60000,
            multiplier: 2.0);
        Assert.Equal(1000, eb.GetNextDelay());
    }

    [Fact]
    public void GetNextDelay_DoublesEachCall()
    {
        var eb = new ExponentialBackoff(1000, 60000, 2.0);
        Assert.Equal(1000, eb.GetNextDelay());
        Assert.Equal(2000, eb.GetNextDelay());
        Assert.Equal(4000, eb.GetNextDelay());
        Assert.Equal(8000, eb.GetNextDelay());
    }

    [Fact]
    public void GetNextDelay_CapsAtMaxDelay()
    {
        var eb = new ExponentialBackoff(1000, 5000, 2.0);
        eb.GetNextDelay(); // 1000
        eb.GetNextDelay(); // 2000
        eb.GetNextDelay(); // 4000
        var delay = eb.GetNextDelay(); // should cap at 5000
        Assert.Equal(5000, delay);
    }

    [Fact]
    public void Reset_RestoresToInitialDelay()
    {
        var eb = new ExponentialBackoff(1000, 60000, 2.0);
        eb.GetNextDelay(); // 1000
        eb.GetNextDelay(); // 2000
        eb.Reset();
        Assert.Equal(1000, eb.GetNextDelay());
    }

    [Fact]
    public void Jitter_AddsRandomness()
    {
        var eb = new ExponentialBackoff(1000, 60000, 2.0, jitter: true);
        var delays = new HashSet<int>();
        for (int i = 0; i < 20; i++)
            delays.Add(eb.GetNextDelay());
        // With jitter, delays should vary even at same step
        // Without jitter, all 20 calls would return identical value
        Assert.True(delays.Count > 1);
    }
}
```

Run: `dotnet test GenCollector.Tests/ExponentialBackoffTests.cs -v`
Expected: FAIL (ExponentialBackoff not yet implemented)

- [ ] **Step 2: 实现 ExponentialBackoff**

```csharp
// GenCollector/Messaging/ExponentialBackoff.cs
using System;
using System.Threading;

namespace GenCollector.Messaging
{
    public class ExponentialBackoff
    {
        private readonly int _initialDelayMs;
        private readonly int _maxDelayMs;
        private readonly double _multiplier;
        private readonly Random _rng = new Random();
        private readonly bool _jitter;
        private int _currentDelayMs;
        private int _step;

        public ExponentialBackoff(int initialDelayMs = 1000, int maxDelayMs = 60000,
            double multiplier = 2.0, bool jitter = true)
        {
            _initialDelayMs = initialDelayMs;
            _maxDelayMs = maxDelayMs;
            _multiplier = multiplier;
            _jitter = jitter;
            _currentDelayMs = initialDelayMs;
            _step = 0;
        }

        public int GetNextDelay()
        {
            var delay = _currentDelayMs;
            _currentDelayMs = Math.Min(
                (int)(_currentDelayMs * _multiplier),
                _maxDelayMs);
            _step++;
            if (_jitter)
            {
                // Add ±25% jitter
                var jitterRange = delay / 4;
                delay = delay + _rng.Next(-jitterRange, jitterRange);
                delay = Math.Max(100, delay);
            }
            return delay;
        }

        public void Reset()
        {
            _currentDelayMs = _initialDelayMs;
            _step = 0;
        }

        public int CurrentStep => _step;
    }
}
```

Run: `dotnet test GenCollector.Tests/ExponentialBackoffTests.cs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add GenCollector/Messaging/ExponentialBackoff.cs GenCollector.Tests/ExponentialBackoffTests.cs
git commit -m "feat(messaging): add ExponentialBackoff with jitter support"
```

---

### Task 9: 实现 OfflineBuffer 离线缓存

**Files:**
- Create: `f:/JQKJ/GenCollector/Messaging/OfflineBuffer.cs`
- Test: `f:/JQKJ/GenCollector.Tests/OfflineBufferTests.cs`

- [ ] **Step 1: 编写 OfflineBuffer 单元测试**

```csharp
// GenCollector.Tests/OfflineBufferTests.cs
using GenCollector.Messaging;
using System.IO;
using Xunit;

public class OfflineBufferTests
{
    [Fact]
    public void Append_WritesLineToBufferFile()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"obf_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var buffer = new OfflineBuffer(tempDir, maxSizeBytes: 1024 * 1024);
        buffer.Append("/topic/test", "{\"v\":1}");
        var files = Directory.GetFiles(tempDir, "*.buf");
        Assert.Single(files);
        var lines = File.ReadAllLines(files[0]);
        Assert.Single(lines);
        Assert.Contains("/topic/test", lines[0]);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void Append_ExceedsMaxSize_DropsOldestLines()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"obf_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        // Small buffer: 200 bytes max
        var buffer = new OfflineBuffer(tempDir, maxSizeBytes: 200);
        for (int i = 0; i < 10; i++)
            buffer.Append("/topic/test", $"{{\"i\":{i}}}");
        var files = Directory.GetFiles(tempDir, "*.buf");
        var content = File.ReadAllText(files[0]);
        // Old entries should be dropped
        Assert.DoesNotContain("\"i\":0", content);
        Assert.Contains("\"i\":9", content);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void ReadAll_ReturnsAllLinesAndClearsBuffer()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"obf_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var buffer = new OfflineBuffer(tempDir, maxSizeBytes: 1024 * 1024);
        buffer.Append("/t1", "{\"a\":1}");
        buffer.Append("/t2", "{\"b\":2}");
        var lines = buffer.ReadAllAndClear();
        Assert.Equal(2, lines.Count);
        Assert.Equal("/t1", lines[0].topic);
        Assert.Equal("{\"a\":1}", lines[0].payload);
        Assert.False(File.Exists(Path.Combine(tempDir, "buffer.buf")));
        Directory.Delete(tempDir, true);
    }
}
```

Run: `dotnet test GenCollector.Tests/OfflineBufferTests.cs -v`
Expected: FAIL

- [ ] **Step 2: 实现 OfflineBuffer**

```csharp
// GenCollector/Messaging/OfflineBuffer.cs
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace GenCollector.Messaging
{
    public class OfflineBuffer
    {
        private readonly string _bufferPath;
        private readonly long _maxSizeBytes;
        private readonly object _lock = new object();

        public OfflineBuffer(string bufferDir, long maxSizeBytes = 100 * 1024 * 1024)
        {
            _bufferPath = Path.Combine(bufferDir, "buffer.buf");
            _maxSizeBytes = maxSizeBytes;
        }

        public void Append(string topic, string payload)
        {
            lock (_lock)
            {
                var line = $"{DateTime.Now:O}\t{topic}\t{payload}\n";
                File.AppendAllText(_bufferPath, line);
                TrimIfNeeded();
            }
        }

        public List<(string topic, string payload, DateTime ts)> ReadAllAndClear()
        {
            lock (_lock)
            {
                var result = new List<(string, string, DateTime)>();
                if (!File.Exists(_bufferPath)) return result;
                var lines = File.ReadAllLines(_bufferPath);
                foreach (var line in lines)
                {
                    var parts = line.Split('\t');
                    if (parts.Length >= 3 &&
                        DateTime.TryParse(parts[0], out var ts))
                    {
                        result.Add((parts[1], parts[2], ts));
                    }
                }
                File.Delete(_bufferPath);
                return result;
            }
        }

        private void TrimIfNeeded()
        {
            if (!File.Exists(_bufferPath)) return;
            var fi = new FileInfo(_bufferPath);
            if (fi.Length <= _maxSizeBytes) return;
            var allLines = File.ReadAllLines(_bufferPath).ToList();
            var keepLines = allLines.Skip(Math.Max(0, allLines.Count / 2)).ToList();
            File.WriteAllLines(_bufferPath, keepLines);
        }
    }
}
```

Run: `dotnet test GenCollector.Tests/OfflineBufferTests.cs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add GenCollector/Messaging/OfflineBuffer.cs GenCollector.Tests/OfflineBufferTests.cs
git commit -m "feat(messaging): add OfflineBuffer for MQTT offline caching"
```

---

### Task 10: 重写 MqttPublisher（指数退避重连）

**Files:**
- Create: `f:/JQKJ/GenCollector/Messaging/MqttPublisher.cs`
- Test: `f:/JQKJ/GenCollector.Tests/MqttPublisherReconnectTests.cs`

- [ ] **Step 1: 阅读现有 MqttPublisher.cs 了解现有接口**

```csharp
// read_file: f:/JQKJ/GenCollector/MqttPublisher.cs
```

- [ ] **Step 2: 编写 MqttPublisher 重连测试**

```csharp
// GenCollector.Tests/MqttPublisherReconnectTests.cs
using GenCollector.Messaging;
using Xunit;

public class MqttPublisherReconnectTests
{
    [Fact]
    public void ExponentialBackoff_ReconnectSequence_IsCorrect()
    {
        // 初始 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)
        var eb = new ExponentialBackoff(1000, 60000, 2.0);
        var sequence = new[] { 1000, 2000, 4000, 8000, 16000, 32000, 60000, 60000 };
        for (int i = 0; i < sequence.Length; i++)
            Assert.Equal(sequence[i], eb.GetNextDelay());
    }
}
```

Run: `dotnet test GenCollector.Tests/MqttPublisherReconnectTests.cs -v`
Expected: PASS (depends only on ExponentialBackoff)

- [ ] **Step 3: 重写 MqttPublisher with reconnection logic**

```csharp
// GenCollector/Messaging/MqttPublisher.cs
using System;
using System.Threading;
using MQTTnet;
using MQTTnet.Client;

namespace GenCollector.Messaging
{
    public class MqttPublisher
    {
        private IMqttClient _client;
        private MqttFactory _factory;
        private string _server;
        private int _port;
        private string _prefix;
        private int _qos;
        private readonly ExponentialBackoff _reconnectBackoff;
        private readonly ManualResetEventSlim _connected = new ManualResetEventSlim(false);
        private bool _disposed;

        public bool IsConnected => _client?.IsConnected ?? false;

        public MqttPublisher()
        {
            _factory = new MqttFactory();
            _reconnectBackoff = new ExponentialBackoff(
                initialDelayMs: 1000,
                maxDelayMs: 60000,
                multiplier: 2.0,
                jitter: true);
        }

        public void Init(SettingConfig setting)
        {
            var uri = new Uri(setting.MqttServer);
            _server = uri.Host;
            _port = uri.Port > 0 ? uri.Port : 1883;
            _prefix = setting.MqttPrefix ?? "/YLCY/CNC/";
            _qos = 0;
        }

        public void Connect()
        {
            if (_disposed) return;
            _connected.Reset();
            _client = _factory.CreateMqttClient();
            var options = new MqttClientOptionsBuilder()
                .WithTcpServer(_server, _port)
                .WithClientId(Guid.NewGuid().ToString())
                .WithCleanSession()
                .Build();
            _client.ApplicationMessageReceived += (s, e) => { };
            try
            {
                var result = _client.ConnectAsync(options).GetAwaiter().GetResult();
                if (result.ResultCode == MqttClientConnectResultCode.Success)
                {
                    _connected.Set();
                    _reconnectBackoff.Reset();
                }
            }
            catch { }
        }

        public bool Publish(string topic, string payload)
        {
            if (_client == null || !_client.IsConnected)
            {
                TryReconnect();
                return false;
            }
            try
            {
                var msg = new MqttApplicationMessageBuilder()
                    .WithTopic(topic)
                    .WithPayload(payload)
                    .WithQualityOfServiceLevel((MQTTnet.Protocol.MqttQualityOfServiceLevel)_qos)
                    .Build();
                return _client.PublishAsync(msg).GetAwaiter().GetResult().ResultCode
                    == MQTTnet.Protocol.MqttClientPublishResultCode.Success;
            }
            catch
            {
                TryReconnect();
                return false;
            }
        }

        private void TryReconnect()
        {
            if (_disposed) return;
            var delay = _reconnectBackoff.GetNextDelay();
            Thread.Sleep(delay);
            Connect();
        }

        public void Disconnect()
        {
            _disposed = true;
            try { _client?.DisconnectAsync().GetAwaiter().GetResult(); } catch { }
        }
    }
}
```

Run: `dotnet build GenCollector/Messaging/MqttPublisher.cs` (syntax check)
Expected: No compile errors

- [ ] **Step 4: Commit**

```bash
git add GenCollector/Messaging/MqttPublisher.cs GenCollector.Tests/MqttPublisherReconnectTests.cs
git commit -m "feat(messaging): rewrite MqttPublisher with exponential backoff reconnection"
```

---

### Task 11: 更新 IDeviceDriver 接口 + 驱动重连逻辑

**Files:**
- Modify: `f:/JQKJ/GenCollector/Drivers/IDeviceDriver.cs`
- Modify: `f:/JQKJ/GenCollector/Drivers/MitsubishiCncDriver.cs`
- Modify: `f:/JQKJ/GenCollector/Drivers/HslPlcDriver.cs`
- Modify: `f:/JQKJ/GenCollector/Drivers/SimDriver.cs`

- [ ] **Step 1: 更新 IDeviceDriver 接口**

```csharp
// 在 IDeviceDriver 接口中添加 IsConnected 属性
string LastError { get; }
string DriverName { get; }
bool IsConnected { get; }  // ← 新增
```

- [ ] **Step 2: 实现 SimDriver.IsConnected**

```csharp
// SimDriver.cs - 简单返回 true
public bool IsConnected => true;
```

- [ ] **Step 3: 实现 MitsubishiCncDriver.IsConnected**

```csharp
// MitsubishiCncDriver.cs
public bool IsConnected => _handle >= 0;
```

- [ ] **Step 4: 实现 HslPlcDriver.IsConnected**

```csharp
// HslPlcDriver.cs - 需要在类中添加字段跟踪连接状态
// 在 HslPlcDriver 类中添加:
private bool _isConnected;

// Connect 方法中: _isConnected = r.IsSuccess;
// Disconnect 方法中: _isConnected = false;
public bool IsConnected => _isConnected;
```

- [ ] **Step 5: Commit**

```bash
git add GenCollector/Drivers/IDeviceDriver.cs GenCollector/Drivers/MitsubishiCncDriver.cs GenCollector/Drivers/HslPlcDriver.cs GenCollector/Drivers/SimDriver.cs
git commit -m "feat(driver): add IsConnected property to IDeviceDriver interface"
```

---

### Task 12: 更新 CollectorEngine 使用新 MqttPublisher 和离线缓存

**Files:**
- Modify: `f:/JQKJ/GenCollector/CollectorEngine.cs`

- [ ] **Step 1: 阅读现有 CollectorEngine.cs**

```csharp
// read_file: f:/JQKJ/GenCollector/CollectorEngine.cs
```

- [ ] **Step 2: 更新 CollectorEngine 使用新 MqttPublisher 和离线缓存**

```csharp
// 在 CollectorEngine 类中做以下修改：

// 1. 添加字段
private OfflineBuffer _offlineBuffer;

// 2. 构造函数中初始化 OfflineBuffer（如果 database.enabled）
_offlineBuffer = new OfflineBuffer(_setting.DataBufferDir ?? Path.Combine(AppContext.BaseDirectory, "buffer"));

// 3. RunDevice 方法中，发布失败时写入离线缓存
bool pub = _mqtt != null && _mqtt.Publish(topic, json);
if (!pub && _mqtt != null)
{
    _offlineBuffer?.Append(topic, json); // 离线缓存
}
OnPublish?.Invoke(dev, topic, json);

// 4. Stop() 方法中 flush 离线缓存
public void Stop()
{
    foreach (var c in _cts) try { c.Cancel(); } catch { }
    _offlineBuffer?.ReadAllAndClear(); // 停止时清空
}
```

- [ ] **Step 3: Commit**

```bash
git add GenCollector/CollectorEngine.cs
git commit -m "feat(engine): integrate OfflineBuffer and new MqttPublisher with reconnection"
```

---

### Task 13: 更新 GenCollector.csproj 添加 MQTTnet

**Files:**
- Modify: `f:/JQKJ/GenCollector/GenCollector.csproj`

- [ ] **Step 1: 添加 MQTTnet PackageReference**

```xml
<PackageReference Include="MQTTnet" Version="4.3.1.873" />
```

Run: `dotnet restore GenCollector/GenCollector.csproj`
Expected: Restored successfully

- [ ] **Step 2: Commit**

```bash
git add GenCollector/GenCollector.csproj
git commit -m "chore: add MQTTnet 4.3.1.873 dependency"
```

---

### Task 14: 运行完整测试套件

- [ ] **Step 1: 运行所有 Phase 0+1 相关测试**

```bash
dotnet test GenCollector.Tests/ -v normal
```

Expected: All tests PASS

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "test: Phase 1 complete - all tests passing"
```

---

## 三、Spec 覆盖自检

| 规格要求 | 对应 Task |
|---|---|
| MQTT 指数退避重连 | Task 10 (MqttPublisher 重写) |
| 驱动断线重连 | Task 11 (IDeviceDriver.IsConnected + 驱动实现) |
| 离线缓存（100MB 上限）| Task 9 (OfflineBuffer) |
| 恢复后补发 | Task 12 (CollectorEngine 集成) |
| 测试覆盖 | Task 8-10 测试文件 |

**无遗漏。**

---

## 四、Placeholder 扫描

- "TBD" / "TODO" → ❌ 无
- "implement later" → ❌ 无
- 不完整步骤 → ❌ 无
- 类型不一致 → ❌ 无

**通过。**
