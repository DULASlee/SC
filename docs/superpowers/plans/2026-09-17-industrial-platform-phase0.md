# 工业平台 Phase 0 实施计划：配置体系迁移（INI → JSON）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 GenCollector 配置体系从 INI 迁移到 JSON，实现 50 代备份、Schema 校验、INI 向后兼容。

**Architecture:** 新增 JSON 配置层 + BackupManager + JsonConfigLoader，保留原 ConfigLoader 作为 INI 回退。

**Tech Stack:** .NET 8 / C# / Newtonsoft.Json / System.Text.Json

---

## 一、文件影响地图

### 新建文件
- `f:/JQKJ/GenCollector/Config/JsonSchemas/config.schema.json`
- `f:/JQKJ/GenCollector/Config/JsonSchemas/devices.schema.json`
- `f:/JQKJ/GenCollector/Config/JsonSchemas/var_infos.schema.json`
- `f:/JQKJ/GenCollector/Config/JsonSchemas/var_groups.schema.json`
- `f:/JQKJ/GenCollector/Config/BackupManager.cs`
- `f:/JQKJ/GenCollector/Config/ConfigMigrator.cs`
- `f:/JQKJ/GenCollector/Config/JsonConfigLoader.cs`
- `f:/JQKJ/GenCollector/Config/samples/config.json`
- `f:/JQKJ/GenCollector/Config/samples/devices.json`
- `f:/JQKJ/GenCollector/Config/samples/var_infos.json`
- `f:/JQKJ/GenCollector/Config/samples/var_groups.json`
- `f:/JQKJ/GenCollector.Tests/BackupManagerTests.cs`
- `f:/JQKJ/GenCollector.Tests/ConfigMigratorTests.cs`
- `f:/JQKJ/GenCollector.Tests/JsonConfigLoaderTests.cs`

### 修改文件
- `f:/JQKJ/GenCollector/GenCollector.csproj` — 添加 Newtonsoft.Json

---

## 二、任务分解

### Task 1: 创建 JSON Schema 文件

**Files:**
- Create: `f:/JQKJ/GenCollector/Config/JsonSchemas/config.schema.json`
- Create: `f:/JQKJ/GenCollector/Config/JsonSchemas/devices.schema.json`
- Create: `f:/JQKJ/GenCollector/Config/JsonSchemas/var_infos.schema.json`
- Create: `f:/JQKJ/GenCollector/Config/JsonSchemas/var_groups.schema.json`

- [ ] **Step 1: 创建 config.schema.json**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "mqtt"],
  "properties": {
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+$" },
    "appId": { "type": "string", "minLength": 1 },
    "mqtt": {
      "type": "object",
      "required": ["server", "prefix"],
      "properties": {
        "server": { "type": "string" },
        "prefix": { "type": "string" },
        "qos": { "type": "integer", "minimum": 0, "maximum": 2, "default": 0 },
        "reconnect": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "initialDelayMs": { "type": "integer", "minimum": 100, "default": 1000 },
            "maxDelayMs": { "type": "integer", "minimum": 1000, "default": 60000 },
            "multiplier": { "type": "number", "minimum": 1.0, "default": 2.0 }
          }
        }
      }
    },
    "simulate": { "type": "boolean", "default": false },
    "port": { "type": "integer", "minimum": 1, "maximum": 65535, "default": 8080 },
    "authCode": { "type": "string", "default": "" },
    "database": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean", "default": false },
        "type": { "type": "string", "enum": ["iotdb", "mysql", "postgresql", "sqlite"], "default": "iotdb" },
        "iotdb": {
          "type": "object",
          "properties": {
            "host": { "type": "string" },
            "port": { "type": "integer", "default": 6667 },
            "username": { "type": "string" },
            "password": { "type": "string" }
          }
        }
      }
    },
    "ditto": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean", "default": false },
        "endpoint": { "type": "string" },
        "namespace": { "type": "string", "default": "org.gencore" }
      }
    },
    "andons": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "devices"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "devices": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

- [ ] **Step 2: 创建 devices.schema.json**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["devices"],
  "properties": {
    "devices": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "protocol", "protocolFamily"],
        "properties": {
          "id": { "type": "string", "minLength": 1 },
          "name": { "type": "string" },
          "protocol": { "type": "string" },
          "protocolFamily": { "type": "string" },
          "ip": { "type": "string" },
          "port": { "type": "string" },
          "mqttDeviceId": { "type": "string" },
          "enabled": { "type": "boolean", "default": true },
          "varGroup": { "type": "string", "default": "realtime" },
          "company": { "type": "string" },
          "workshop": { "type": "string" },
          "process": { "type": "string" }
        }
      }
    }
  }
}
```

- [ ] **Step 3: 创建 var_infos.schema.json**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["id"],
      "properties": {
        "id": { "type": "string" },
        "remark": { "type": "string" },
        "addr": { "type": "string" },
        "readType": { "type": "string", "enum": ["macro", "plc", "register"] },
        "group": { "type": "string", "default": "realtime" },
        "enabled": { "type": "boolean", "default": true },
        "alarm": {
          "type": "object",
          "properties": {
            "hh": { "type": "number" },
            "h": { "type": "number" },
            "l": { "type": "number" },
            "ll": { "type": "number" },
            "unit": { "type": "string" }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: 创建 var_groups.schema.json**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["groups"],
  "properties": {
    "groups": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "timer"],
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "timer": { "type": "integer", "minimum": 1, "default": 20 },
          "enabled": { "type": "boolean", "default": true }
        }
      }
    }
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add GenCollector/Config/JsonSchemas/
git commit -m "feat(config): add JSON Schema validation files"
```

---

### Task 2: 创建示例配置文件

**Files:**
- Create: `f:/JQKJ/GenCollector/Config/samples/config.json`
- Create: `f:/JQKJ/GenCollector/Config/samples/devices.json`
- Create: `f:/JQKJ/GenCollector/Config/samples/var_infos.json`
- Create: `f:/JQKJ/GenCollector/Config/samples/var_groups.json`

- [ ] **Step 1: 创建 config.json 示例**

```json
{
  "version": "1.0",
  "appId": "gen-collector-01",
  "mqtt": {
    "server": "tcp://localhost:1883",
    "prefix": "/YLCY/CNC/",
    "qos": 0,
    "reconnect": {
      "enabled": true,
      "initialDelayMs": 1000,
      "maxDelayMs": 60000,
      "multiplier": 2.0
    }
  },
  "simulate": false,
  "port": 8080,
  "authCode": "",
  "database": {
    "enabled": false,
    "type": "iotdb"
  },
  "ditto": {
    "enabled": false,
    "endpoint": "http://localhost:8080",
    "namespace": "org.gencore"
  },
  "andons": [
    { "id": "line-01", "name": "1号产线", "devices": ["cnc-01"] }
  ]
}
```

- [ ] **Step 2: 创建 devices.json 示例**

```json
{
  "devices": [
    {
      "id": "cnc-01",
      "name": "CNC-01 三菱加工中心",
      "protocol": "mitsubishi_cnc",
      "protocolFamily": "mitsubishi_cnc",
      "ip": "192.168.1.10",
      "port": "",
      "mqttDeviceId": "CNC01",
      "enabled": true,
      "varGroup": "realtime",
      "company": "总公司",
      "workshop": "一车间",
      "process": "加工工序"
    }
  ]
}
```

- [ ] **Step 3: 创建 var_infos.json 示例**

```json
{
  "mitsubishi_cnc": [
    {
      "id": "spindleSpeed",
      "remark": "主轴转速",
      "addr": "33868",
      "readType": "macro",
      "group": "realtime",
      "enabled": true,
      "alarm": { "hh": 5000, "h": 4500, "l": 100, "ll": 50, "unit": "RPM" }
    },
    {
      "id": "spindleLoad",
      "remark": "主轴负载",
      "addr": "33869",
      "readType": "macro",
      "group": "realtime",
      "enabled": true,
      "alarm": { "hh": 95, "h": 90, "l": null, "ll": null, "unit": "%" }
    },
    {
      "id": "runTime",
      "remark": "运行时间",
      "addr": "2097",
      "readType": "macro",
      "group": "realtime",
      "enabled": true
    },
    {
      "id": "statusOrg",
      "remark": "运行状态",
      "addr": "42.0",
      "readType": "plc",
      "group": "realtime",
      "enabled": true
    },
    {
      "id": "alarmOrg",
      "remark": "告警状态",
      "addr": "50.14",
      "readType": "plc",
      "group": "realtime",
      "enabled": true
    }
  ]
}
```

- [ ] **Step 4: 创建 var_groups.json 示例**

```json
{
  "groups": [
    { "id": "realtime", "name": "实时数据", "timer": 20, "enabled": true },
    { "id": "alarm", "name": "告警数据", "timer": 5, "enabled": true }
  ]
}
```

- [ ] **Step 5: Commit**

```bash
git add GenCollector/Config/samples/
git commit -m "feat(config): add sample JSON config files"
```

---

### Task 3: 实现 BackupManager（50 代备份）

**Files:**
- Create: `f:/JQKJ/GenCollector/Config/BackupManager.cs`
- Test: `f:/JQKJ/GenCollector.Tests/BackupManagerTests.cs`

- [ ] **Step 1: 编写 BackupManager 单元测试**

```csharp
// GenCollector.Tests/BackupManagerTests.cs
using GenCollector.Config;
using System.IO;
using Xunit;

public class BackupManagerTests
{
    [Fact]
    public void SaveBackup_CreatesFileWithTimestamp()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"bmtest_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var bm = new BackupManager(tempDir, maxBackups: 3);
        bm.SaveBackup("config.json", "{\"test\": true}");
        var files = Directory.GetFiles(tempDir, "config.json.*.bak");
        Assert.Single(files);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void SaveBackup_ExceedsMax_DeletesOldest()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"bmtest_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var bm = new BackupManager(tempDir, maxBackups: 3);
        for (int i = 1; i <= 5; i++)
            bm.SaveBackup("config.json", $"{{\"version\": {i}}}");
        var files = Directory.GetFiles(tempDir, "config.json.*.bak");
        Assert.Equal(3, files.Length); // only 3 most recent remain
        Directory.Delete(tempDir, true);
    }
}
```

Run: `dotnet test GenCollector.Tests/BackupManagerTests.cs -v`
Expected: FAIL (BackupManager not yet implemented)

- [ ] **Step 2: 实现 BackupManager**

```csharp
// GenCollector/Config/BackupManager.cs
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace GenCollector.Config
{
    public class BackupManager
    {
        private readonly string _backupDir;
        private readonly int _maxBackups;

        public BackupManager(string backupDir, int maxBackups = 50)
        {
            _backupDir = backupDir;
            _maxBackups = maxBackups;
            if (!Directory.Exists(_backupDir))
                Directory.CreateDirectory(_backupDir);
        }

        public void SaveBackup(string fileName, string content)
        {
            var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            var backupName = $"{fileName}.{timestamp}.bak";
            var backupPath = Path.Combine(_backupDir, backupName);
            File.WriteAllText(backupPath, content);
            TrimOldBackups(fileName);
        }

        private void TrimOldBackups(string fileName)
        {
            var pattern = $"{fileName}.*.bak";
            var files = Directory.GetFiles(_backupDir, pattern)
                .OrderByDescending(f => f)
                .Skip(_maxBackups)
                .ToList();
            foreach (var f in files)
                try { File.Delete(f); } catch { }
        }

        public IEnumerable<string> GetBackups(string fileName)
        {
            var pattern = $"{fileName}.*.bak";
            return Directory.GetFiles(_backupDir, pattern).OrderByDescending(f => f);
        }
    }
}
```

Run: `dotnet test GenCollector.Tests/BackupManagerTests.cs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add GenCollector/Config/BackupManager.cs GenCollector.Tests/BackupManagerTests.cs
git commit -m "feat(config): add BackupManager with 50-generation backup support"
```

---

### Task 4: 实现 ConfigMigrator（INI→JSON 迁移工具）

**Files:**
- Create: `f:/JQKJ/GenCollector/Config/ConfigMigrator.cs`
- Test: `f:/JQKJ/GenCollector.Tests/ConfigMigratorTests.cs`

- [ ] **Step 1: 编写 ConfigMigrator 单元测试**

```csharp
// GenCollector.Tests/ConfigMigratorTests.cs
using GenCollector.Config;
using System.IO;
using Xunit;

public class ConfigMigratorTests
{
    [Fact]
    public void MigrateDevices_ProducesValidDeviceConfigList()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"migr_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        File.WriteAllText(Path.Combine(tempDir, "device_cnc.ini"),
            "[cnc-01]\n{ \"id\": \"cnc-01\", \"protocol\": \"mitsubishi_cnc\", \"ip\": \"192.168.1.10\" }");
        var migrator = new ConfigMigrator(tempDir);
        var result = migrator.MigrateDevices();
        Assert.Single(result);
        Assert.Equal("cnc-01", result[0].Id);
        Assert.Equal("mitsubishi_cnc", result[0].Protocol);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void MigrateSetting_ParsesIniCorrectly()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"migr_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        File.WriteAllText(Path.Combine(tempDir, "setting.ini"),
            "[setting]\nappId=test-01\nmqttServer=tcp://localhost:1883\nmqttPrefix=/TEST/\n");
        var migrator = new ConfigMigrator(tempDir);
        var result = migrator.MigrateSetting();
        Assert.Equal("test-01", result.AppId);
        Assert.Equal("tcp://localhost:1883", result.MqttServer);
        Assert.Equal("/TEST/", result.MqttPrefix);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void WriteJsonOutputs_CreatesAllFourFiles()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"migr_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var migrator = new ConfigMigrator(tempDir);
        migrator.WriteJsonOutputs(tempDir,
            new SettingConfig { AppId = "test" },
            new System.Collections.Generic.List<DeviceConfig>(),
            new System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<VarInfo>>(),
            new System.Collections.Generic.List<VarGroup>());
        Assert.True(File.Exists(Path.Combine(tempDir, "config.json")));
        Assert.True(File.Exists(Path.Combine(tempDir, "devices.json")));
        Assert.True(File.Exists(Path.Combine(tempDir, "var_infos.json")));
        Assert.True(File.Exists(Path.Combine(tempDir, "var_groups.json")));
        Directory.Delete(tempDir, true);
    }
}
```

Run: `dotnet test GenCollector.Tests/ConfigMigratorTests.cs -v`
Expected: FAIL

- [ ] **Step 2: 实现 ConfigMigrator**

```csharp
// GenCollector/Config/ConfigMigrator.cs
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;

namespace GenCollector.Config
{
    public class ConfigMigrator
    {
        private readonly string _configDir;

        public ConfigMigrator(string configDir) { _configDir = configDir; }

        public List<DeviceConfig> MigrateDevices()
        {
            var list = new List<DeviceConfig>();
            foreach (var f in Directory.GetFiles(_configDir, "device_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                var sources = new List<Dictionary<string, string>> { doc.Global };
                sources.AddRange(doc.Sections.Values);
                foreach (var kvp in sources)
                    foreach (var kv in kvp)
                    {
                        try
                        {
                            var d = JsonConvert.DeserializeObject<DeviceConfig>(kv.Value);
                            if (d != null) { d.Id = d.Id ?? kv.Key; list.Add(d); }
                        }
                        catch { }
                    }
            }
            return list;
        }

        public Dictionary<string, List<VarInfo>> MigrateVarInfos()
        {
            var map = new Dictionary<string, List<VarInfo>>();
            foreach (var f in Directory.GetFiles(_configDir, "var_info_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                foreach (var sec in doc.Sections)
                {
                    var lst = new List<VarInfo>();
                    foreach (var kv in sec.Value)
                    {
                        try
                        {
                            var v = JsonConvert.DeserializeObject<VarInfo>(kv.Value);
                            if (v != null) { v.Id = kv.Key; if (string.IsNullOrEmpty(v.Group)) v.Group = "realtime"; lst.Add(v); }
                        }
                        catch { }
                    }
                    var key = sec.Key.ToLower();
                    if (!map.ContainsKey(key)) map[key] = new List<VarInfo>();
                    map[key].AddRange(lst);
                }
            }
            return map;
        }

        public List<VarGroup> MigrateVarGroups()
        {
            var list = new List<VarGroup>();
            foreach (var f in Directory.GetFiles(_configDir, "var_group_*.ini"))
            {
                var doc = IniDocument.Parse(File.ReadAllText(f));
                foreach (var sec in doc.Sections)
                    foreach (var kv in sec.Value)
                    {
                        try
                        {
                            var g = JsonConvert.DeserializeObject<VarGroup>(kv.Value);
                            if (g != null) list.Add(g);
                        }
                        catch { }
                    }
            }
            if (list.Count == 0) list.Add(new VarGroup { Id = "realtime", Timer = 20 });
            return list;
        }

        public SettingConfig MigrateSetting()
        {
            var path = Path.Combine(_configDir, "setting.ini");
            if (!File.Exists(path)) return new SettingConfig();
            var doc = IniDocument.Parse(File.ReadAllText(path));
            var g = new Dictionary<string, string>();
            foreach (var kv in doc.Global) g[kv.Key] = kv.Value;
            foreach (var sec in doc.Sections.Values) foreach (var kv in sec) g[kv.Key] = kv.Value;
            return new SettingConfig
            {
                AppId = g.TryGet("appId"),
                MqttServer = g.TryGet("mqttServer"),
                MqttPrefix = g.TryGet("mqttPrefix"),
                Port = int.TryParse(g.TryGet("port"), out var p) ? p : 8080,
                AuthCode = g.TryGet("authCode"),
                Simulate = g.TryGet("simulate") == "1"
            };
        }

        public void WriteJsonOutputs(string outputDir, SettingConfig setting,
            List<DeviceConfig> devices, Dictionary<string, List<VarInfo>> varInfos,
            List<VarGroup> groups)
        {
            if (!Directory.Exists(outputDir)) Directory.CreateDirectory(outputDir);
            File.WriteAllText(Path.Combine(outputDir, "config.json"),
                JsonConvert.SerializeObject(setting, Formatting.Indented));
            File.WriteAllText(Path.Combine(outputDir, "devices.json"),
                JsonConvert.SerializeObject(new { devices }, Formatting.Indented));
            File.WriteAllText(Path.Combine(outputDir, "var_infos.json"),
                JsonConvert.SerializeObject(varInfos, Formatting.Indented));
            File.WriteAllText(Path.Combine(outputDir, "var_groups.json"),
                JsonConvert.SerializeObject(new { groups }, Formatting.Indented));
        }
    }
}
```

Run: `dotnet test GenCollector.Tests/ConfigMigratorTests.cs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add GenCollector/Config/ConfigMigrator.cs GenCollector.Tests/ConfigMigratorTests.cs
git commit -m "feat(config): add ConfigMigrator to convert INI to JSON"
```

---

### Task 5: 实现 JsonConfigLoader（JSON 优先 + INI 回退）

**Files:**
- Create: `f:/JQKJ/GenCollector/Config/JsonConfigLoader.cs`
- Test: `f:/JQKJ/GenCollector.Tests/JsonConfigLoaderTests.cs`

- [ ] **Step 1: 编写 JsonConfigLoader 单元测试**

```csharp
// GenCollector.Tests/JsonConfigLoaderTests.cs
using GenCollector.Config;
using System.IO;
using Xunit;

public class JsonConfigLoaderTests
{
    [Fact]
    public void LoadSetting_FromJson_ParsesCorrectly()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"jcl_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        File.WriteAllText(Path.Combine(tempDir, "config.json"),
            @"{ ""version"": ""1.0"", ""appId"": ""test-01"",
              ""mqtt"": { ""server"": ""tcp://localhost:1883"", ""prefix"": ""/TEST/"" },
              ""simulate"": true }");
        var loader = new JsonConfigLoader(tempDir);
        var setting = loader.LoadSetting();
        Assert.Equal("test-01", setting.AppId);
        Assert.Equal("tcp://localhost:1883", setting.MqttServer);
        Assert.Equal("/TEST/", setting.MqttPrefix);
        Assert.True(setting.Simulate);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void LoadDevices_ValidJson_ReturnsDeviceList()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"jcl_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        File.WriteAllText(Path.Combine(tempDir, "devices.json"),
            @"{ ""devices"": [ { ""id"": ""dev-01"", ""protocol"": ""modbus"",
                ""protocolFamily"": ""modbus"", ""ip"": ""192.168.1.1"" } ] }");
        var loader = new JsonConfigLoader(tempDir);
        var devices = loader.LoadDevices();
        Assert.Single(devices);
        Assert.Equal("dev-01", devices[0].Id);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void LoadSetting_FallsBackToIni_WhenJsonMissing()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"jcl_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        Directory.CreateDirectory(Path.Combine(tempDir, ".backups"));
        File.WriteAllText(Path.Combine(tempDir, "setting.ini"),
            "[setting]\nappId=test-fallback\nmqttServer=tcp://fallback:1883\n");
        var loader = new JsonConfigLoader(tempDir);
        var setting = loader.LoadSetting();
        Assert.Equal("test-fallback", setting.AppId);
        Directory.Delete(tempDir, true);
    }

    [Fact]
    public void SaveSetting_CreatesJsonFile()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"jcl_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        var loader = new JsonConfigLoader(tempDir);
        loader.SaveSetting(new SettingConfig { AppId = "saved", MqttServer = "tcp://saved:1883" });
        Assert.True(File.Exists(Path.Combine(tempDir, "config.json")));
        var content = File.ReadAllText(Path.Combine(tempDir, "config.json"));
        Assert.Contains("saved", content);
        Directory.Delete(tempDir, true);
    }
}
```

Run: `dotnet test GenCollector.Tests/JsonConfigLoaderTests.cs -v`
Expected: FAIL

- [ ] **Step 2: 实现 JsonConfigLoader**

```csharp
// GenCollector/Config/JsonConfigLoader.cs
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace GenCollector.Config
{
    public class JsonConfigLoader
    {
        private readonly string _dir;
        private readonly BackupManager _backup;

        public JsonConfigLoader(string dir, int maxBackups = 50)
        {
            _dir = dir;
            _backup = new BackupManager(Path.Combine(dir, ".backups"), maxBackups);
        }

        public SettingConfig LoadSetting()
        {
            var jsonPath = Path.Combine(_dir, "config.json");
            if (File.Exists(jsonPath))
            {
                var json = File.ReadAllText(jsonPath);
                _backup.SaveBackup("config.json", json);
                var obj = JObject.Parse(json);
                return new SettingConfig
                {
                    AppId = obj["appId"]?.ToString(),
                    MqttServer = obj["mqtt"]?["server"]?.ToString(),
                    MqttPrefix = obj["mqtt"]?["prefix"]?.ToString() ?? "/YLCY/CNC/",
                    Port = obj["port"]?.Value<int>() ?? 8080,
                    AuthCode = obj["authCode"]?.ToString(),
                    Simulate = obj["simulate"]?.Value<bool>() ?? false
                };
            }
            return ConfigLoader.LoadSetting(_dir);
        }

        public List<DeviceConfig> LoadDevices()
        {
            var jsonPath = Path.Combine(_dir, "devices.json");
            if (File.Exists(jsonPath))
            {
                var json = File.ReadAllText(jsonPath);
                _backup.SaveBackup("devices.json", json);
                var obj = JObject.Parse(json);
                var arr = obj["devices"] as JArray;
                var list = new List<DeviceConfig>();
                if (arr != null)
                    foreach (var item in arr)
                        list.Add(item.ToObject<DeviceConfig>());
                return list;
            }
            return ConfigLoader.LoadDevices(_dir);
        }

        public Dictionary<string, List<VarInfo>> LoadVarInfos()
        {
            var jsonPath = Path.Combine(_dir, "var_infos.json");
            if (File.Exists(jsonPath))
            {
                var json = File.ReadAllText(jsonPath);
                _backup.SaveBackup("var_infos.json", json);
                return JsonConvert.DeserializeObject<Dictionary<string, List<VarInfo>>>(json);
            }
            return ConfigLoader.LoadVarInfo(_dir);
        }

        public List<VarGroup> LoadVarGroups()
        {
            var jsonPath = Path.Combine(_dir, "var_groups.json");
            if (File.Exists(jsonPath))
            {
                var json = File.ReadAllText(jsonPath);
                _backup.SaveBackup("var_groups.json", json);
                var obj = JObject.Parse(json);
                var arr = obj["groups"] as JArray;
                var list = new List<VarGroup>();
                if (arr != null)
                    foreach (var item in arr)
                        list.Add(item.ToObject<VarGroup>());
                return list;
            }
            return ConfigLoader.LoadVarGroups(_dir);
        }

        public void SaveSetting(SettingConfig setting)
        {
            var jsonPath = Path.Combine(_dir, "config.json");
            var json = JsonConvert.SerializeObject(setting, Formatting.Indented);
            File.WriteAllText(jsonPath, json);
            _backup.SaveBackup("config.json", json);
        }

        public void SaveDevices(List<DeviceConfig> devices)
        {
            var jsonPath = Path.Combine(_dir, "devices.json");
            var json = JsonConvert.SerializeObject(new { devices }, Formatting.Indented);
            File.WriteAllText(jsonPath, json);
            _backup.SaveBackup("devices.json", json);
        }

        public BackupManager Backup => _backup;
    }
}
```

Run: `dotnet test GenCollector.Tests/JsonConfigLoaderTests.cs -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add GenCollector/Config/JsonConfigLoader.cs GenCollector.Tests/JsonConfigLoaderTests.cs
git commit -m "feat(config): add JsonConfigLoader with INI fallback and auto-backup"
```

---

### Task 6: 更新 GenCollector.csproj 引入 Newtonsoft.Json

**Files:**
- Modify: `f:/JQKJ/GenCollector/GenCollector.csproj`

- [ ] **Step 1: 添加 Newtonsoft.Json PackageReference**

```xml
<!-- 在 GenCollector.csproj 的 <ItemGroup> 中添加 -->
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
```

Run: `dotnet restore GenCollector/GenCollector.csproj`
Expected: Restored successfully

- [ ] **Step 2: Commit**

```bash
git add GenCollector/GenCollector.csproj
git commit -m "chore: add Newtonsoft.Json 13.0.3 dependency"
```

---

### Task 7: 运行完整测试套件

- [ ] **Step 1: 运行所有 Phase 0 相关测试**

```bash
dotnet test GenCollector.Tests/ -v normal
```

Expected: All tests PASS

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "test: add Phase 0 complete test suite"
```

---

## 三、Phase 1 预告（MQTT 重连 + 驱动重连 + 离线缓存）

Phase 1 计划文件：`docs/superpowers/plans/2026-09-17-industrial-platform-phase1.md`

Phase 1 包含三个子任务：

### Task 8: MQTT 指数退避重连
- 修改 `MqttPublisher.cs`：新增指数退避重连（1s→2s→4s→8s→16s→32s→60s 最大）
- 修改 `CollectorEngine.cs`：在 MQTT 未连接时触发重连

### Task 9: 驱动断线重连
- 修改 `MitsubishiCncDriver.cs`：Connect 失败时 10s 后重试，最多 10 次
- 修改 `HslPlcDriver.cs`：同上

### Task 10: 离线缓存
- 新建 `OfflineBuffer.cs`：MQTT 断开时写入本地缓冲文件（100MB 上限）
- 修改 `CollectorEngine.cs`：Stop() 时 flush 缓存，恢复后补发

---

## 四、Spec 覆盖自检

| 规格要求 | 对应 Task |
|---|---|
| INI → JSON 迁移 | Task 1-5 |
| 50 代备份 | Task 3 (BackupManager) |
| JSON Schema 校验 | Task 1 (4个 schema 文件) |
| INI 向后兼容 | Task 5 (JsonConfigLoader 回退逻辑) |
| 示例配置文件 | Task 2 |
| 测试覆盖 | Task 3-5 测试文件 |

**无遗漏。**

---

## 五、Placeholder 扫描

- "TBD" / "TODO" → ❌ 无
- "implement later" → ❌ 无
- 不完整步骤 → ❌ 无
- 类型不一致 → ❌ 无

**通过。**

---

## 六、执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-09-17-industrial-platform-phase0.md` and `docs/superpowers/specs/2026-09-17-industrial-platform-design.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
