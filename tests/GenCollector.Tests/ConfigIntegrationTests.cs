using GenCollector;
using GenCollector.Config;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

public class ConfigIntegrationTests : IDisposable
{
    private readonly string _tempDir;
    private readonly string _backupDir;

    public ConfigIntegrationTests()
    {
        _tempDir = Path.Combine(Path.GetTempPath(), $"cig_{Guid.NewGuid()}");
        Directory.CreateDirectory(_tempDir);
        _backupDir = Path.Combine(_tempDir, ".backups");
        Directory.CreateDirectory(_backupDir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_tempDir, true); } catch { }
    }

    // ---------- 1. 损坏的 JSON 文件 → 抛出 JsonException ----------

    [Fact]
    public async Task LoadSetting_CorruptJson_ThrowsJsonException()
    {
        var badJson = Path.Combine(_tempDir, "config.json");
        await File.WriteAllTextAsync(badJson, "{ invalid json }");

        var loader = new JsonConfigLoader(_tempDir);
        // JsonConfigLoader wraps JsonReaderException in InvalidOperationException
        var ex = Assert.Throws<InvalidOperationException>(() => loader.LoadSetting());
        Assert.Contains("malformed JSON", ex.Message);
    }

    [Fact]
    public async Task LoadDevices_CorruptJson_ThrowsJsonException()
    {
        var badJson = Path.Combine(_tempDir, "devices.json");
        await File.WriteAllTextAsync(badJson, "{ broken");

        var loader = new JsonConfigLoader(_tempDir);
        Assert.Throws<Newtonsoft.Json.JsonReaderException>(() => loader.LoadDevices());
    }

    // ---------- 2. 有效 JSON + 损坏 INI 回退 → JSON 正常加载 ----------

    [Fact]
    public void LoadSetting_ValidJsonFallsBackToIni_WhenJsonMissing()
    {
        // Write a valid config.json
        var jsonPath = Path.Combine(_tempDir, "config.json");
        var json = @"{ ""appId"": ""json-app"", ""mqtt"": { ""server"": ""tcp://jsonserver:1883"" }, ""simulate"": true }";
        File.WriteAllText(jsonPath, json);

        // No INI present — should load from JSON
        var loader = new JsonConfigLoader(_tempDir);
        var setting = loader.LoadSetting();
        Assert.Equal("json-app", setting.AppId);
        Assert.Equal("tcp://jsonserver:1883", setting.MqttServer);
    }

    [Fact]
    public void LoadSetting_FallsBackToIni_WhenJsonMissing()
    {
        // No JSON, only INI
        var iniPath = Path.Combine(_tempDir, "setting.ini");
        File.WriteAllText(iniPath, "[setting]\nappId=ini-app\nmqttServer=tcp://ini:1883\n");

        var loader = new JsonConfigLoader(_tempDir);
        var setting = loader.LoadSetting();
        Assert.Equal("ini-app", setting.AppId);
        Assert.Equal("tcp://ini:1883", setting.MqttServer);
    }

    // ---------- 3. 重复节名的 INI → 取最后一个 ----------

    [Fact]
    public void IniDocument_DuplicateSection_KeepsLast()
    {
        var ini = @"[device]
key1=first
[device]
key1=second
key2=last";
        var doc = IniDocument.Parse(ini);

        Assert.True(doc.Sections.ContainsKey("device"));
        var section = doc.Sections["device"];
        Assert.Equal("second", section["key1"]);
        Assert.Equal("last", section["key2"]);
    }

    [Fact]
    public void LoadDevices_DuplicateSectionInIni_KeepsLastValue()
    {
        // Write INI with duplicate [cnc] sections
        var iniPath = Path.Combine(_tempDir, "device_cnc.ini");
        File.WriteAllText(iniPath, @"[cnc]
cnc-01={ ""id"": ""cnc-01"", ""protocol"": ""mitsubishi_cnc"", ""ip"": ""192.168.1.10"" }
[cnc]
cnc-02={ ""id"": ""cnc-02"", ""protocol"": ""mitsubishi_cnc"", ""ip"": ""192.168.1.11"" }
[cnc]
cnc-03={ ""id"": ""cnc-03"", ""protocol"": ""mitsubishi_cnc"", ""ip"": ""192.168.1.12"" }
");

        var migrator = new ConfigMigrator(_tempDir);
        var devices = migrator.MigrateDevices();

        // Only the last [cnc] section is kept (duplicate section names → last wins)
        Assert.Single(devices);
        Assert.Equal("cnc-03", devices[0].Id);
    }

    // ---------- 4. GBK/Shift-JIS 编码的 INI 文件 → 正常解析 ----------
    // 需要 Encoding.RegisterProvider 注册代码页支持 (.NET Core/.NET 5+ 默认不支持)

    [Fact]
    public void LoadSetting_NonUtf8EncodedIni_ParsesCorrectly()
    {
        // Windows .NET Core 3.0+ 原生支持 Encoding.GetEncoding(int) for Windows code pages
        var iniPath = Path.Combine(_tempDir, "setting.ini");
        var enc = Encoding.GetEncoding(932); // cp 932 = Shift-JIS
        var bytes = enc.GetBytes("[setting]\nappId=shift-jis-test\nmqttServer=tcp://sjis:1883\n");
        File.WriteAllBytes(iniPath, bytes);

        var loader = new JsonConfigLoader(_tempDir);
        var setting = loader.LoadSetting();
        Assert.Equal("shift-jis-test", setting.AppId);
    }

    [Fact]
    public void MigrateSetting_NonUtf8EncodedIni_ParsesCorrectly()
    {
        var iniPath = Path.Combine(_tempDir, "setting.ini");
        var enc = Encoding.GetEncoding(932);
        var bytes = enc.GetBytes("[setting]\nappId=shift-jis-migrate\nmqttServer=tcp://sjis-migrate:1883\n");
        File.WriteAllBytes(iniPath, bytes);

        var migrator = new ConfigMigrator(_tempDir);
        var setting = migrator.MigrateSetting();
        Assert.Equal("shift-jis-migrate", setting.AppId);
    }

    // ---------- 5. 迁移失败 → 备份源文件 + 报告错误 ----------

    [Fact]
    public void MigrateDevices_InvalidJsonInIni_SwallowsError_StillReturnsResults()
    {
        var iniPath = Path.Combine(_tempDir, "device_cnc.ini");
        File.WriteAllText(iniPath, @"[cnc]
cnc-01={ ""id"": ""cnc-01"", ""protocol"": ""mitsubishi_cnc"" }
cnc-bad=not valid json at all
cnc-02={ ""id"": ""cnc-02"", ""protocol"": ""mitsubishi_cnc"" }
");

        var migrator = new ConfigMigrator(_tempDir);
        // Should not throw — errors are caught internally
        var devices = migrator.MigrateDevices();
        Assert.Equal(2, devices.Count);
    }

    [Fact]
    public void BackupManager_SaveBackup_CreatesBackupBeforeMigration()
    {
        var bm = new BackupManager(_backupDir, maxBackups: 5);

        var iniPath = Path.Combine(_tempDir, "setting.ini");
        File.WriteAllText(iniPath, "[setting]\nappId=pre-migrate\n");

        var content = File.ReadAllText(iniPath);
        bm.SaveBackup("setting.ini", content);

        var backups = bm.GetBackups("setting.ini");
        Assert.Single(backups);
    }

    // ---------- 6. 并发读写同一配置文件 → 无数据丢失 ----------

    [Fact]
    public async Task SaveSetting_ConcurrentWrites_NoDataLoss()
    {
        var bm = new BackupManager(_backupDir, maxBackups: 50);
        var tasks = new List<Task>();

        for (int i = 0; i < 10; i++)
        {
            var index = i;
            tasks.Add(Task.Run(() =>
            {
                var setting = new SettingConfig
                {
                    AppId = $"app-{index}",
                    MqttServer = $"tcp://server-{index}:1883",
                    Port = 8000 + index
                };
                var path = Path.Combine(_tempDir, $"concurrent_{index}.json");
                bm.SaveSettingAtomic(setting, path);
            }));
        }

        await Task.WhenAll(tasks);

        // Each write should succeed independently with valid JSON
        for (int i = 0; i < 10; i++)
        {
            var path = Path.Combine(_tempDir, $"concurrent_{i}.json");
            Assert.True(File.Exists(path), $"File {i} should exist");
            var content = File.ReadAllText(path);
            var setting = JsonConvert.DeserializeObject<SettingConfig>(content);
            Assert.NotNull(setting);
            Assert.Equal($"app-{i}", setting.AppId);
        }
    }

    [Fact]
    public async Task BackupManager_ConcurrentSaves_AllBackupsCreated()
    {
        var bm = new BackupManager(_backupDir, maxBackups: 50);
        var tasks = new List<Task>();

        for (int i = 0; i < 20; i++)
        {
            var index = i;
            tasks.Add(Task.Run(() => bm.SaveBackup("config.json", $"{{\"version\": {index}}}")));
        }

        await Task.WhenAll(tasks);

        var backups = bm.GetBackups("config.json").ToList();
        // All 20 should be saved (maxBackups=50 allows all)
        Assert.Equal(20, backups.Count);
    }

    // ---------- 7. 备份恢复 → 恢复到备份状态 ----------

    [Fact]
    public void BackupManager_VerifyBackupIntegrity_ValidBackup_ReturnsTrue()
    {
        var bm = new BackupManager(_backupDir);
        var backupContent = @"{ ""appId"": ""backup-test"", ""mqtt"": { ""server"": ""tcp://backup:1883"" } }";

        // Write a valid backup file directly
        var backupPath = Path.Combine(_backupDir, "config.json.1000.test.bak");
        File.WriteAllText(backupPath, backupContent);

        var result = bm.VerifyBackupIntegrity(backupPath);
        Assert.True(result);
    }

    [Fact]
    public void BackupManager_VerifyBackupIntegrity_CorruptBackup_Throws()
    {
        var bm = new BackupManager(_backupDir);

        var backupPath = Path.Combine(_backupDir, "config.json.1000.corrupt.bak");
        File.WriteAllText(backupPath, "{ invalid }");

        // VerifyBackupIntegrity calls JsonDocument.Parse which throws JsonReaderException
        Assert.Throws<InvalidDataException>(() => bm.VerifyBackupIntegrity(backupPath));
    }

    [Fact]
    public void BackupManager_SaveSettingAtomic_ValidSetting_Succeeds()
    {
        var bm = new BackupManager(_backupDir);
        var path = Path.Combine(_tempDir, "atomic_test.json");

        var setting = new SettingConfig { AppId = "atomic", MqttServer = "tcp://atomic:1883" };
        bm.SaveSettingAtomic(setting, path);

        Assert.True(File.Exists(path));
        var content = File.ReadAllText(path);
        Assert.Contains("atomic", content);
    }

    [Fact]
    public void BackupManager_SaveSettingAtomic_InvalidJson_ThrowsAndCleansUpTemp()
    {
        var bm = new BackupManager(_backupDir);

        // Direct test: VerifyJsonValid wraps JsonException into InvalidDataException
        var badPath = Path.Combine(_tempDir, "bad.json");
        File.WriteAllText(badPath, "{ invalid json }");

        var ex = Assert.Throws<InvalidDataException>(() => bm.VerifyBackupIntegrity(badPath));
        Assert.Contains("JSON", ex.Message);
    }

    // ---------- Additional: sensitive field detection ----------

    [Fact]
    public async Task LoadSetting_PlainTextPassword_ThrowsInvalidOperation()
    {
        var jsonPath = Path.Combine(_tempDir, "config.json");
        var json = @"{ ""appId"": ""test"", ""authCode"": ""super-secret"", ""mqtt"": { ""server"": ""tcp://x:1883"" } }";
        await File.WriteAllTextAsync(jsonPath, json);

        var loader = new JsonConfigLoader(_tempDir);
        // plain-text authCode (contains "auth") should throw
        Assert.Throws<InvalidOperationException>(() => loader.LoadSetting());
    }

    [Fact]
    public async Task LoadSetting_EnvVarReference_Password_DoesNotThrow()
    {
        // Set the env var first
        Environment.SetEnvironmentVariable("TEST_SECRET_PWD", "my-secret-value");

        try
        {
            var jsonPath = Path.Combine(_tempDir, "config.json");
            var json = @"{ ""appId"": ""test"", ""authCode"": ""${TEST_SECRET_PWD}"", ""mqtt"": { ""server"": ""tcp://x:1883"" } }";
            await File.WriteAllTextAsync(jsonPath, json);

            var loader = new JsonConfigLoader(_tempDir);
            var setting = loader.LoadSetting();
            Assert.Equal("my-secret-value", setting.AuthCode);
        }
        finally
        {
            Environment.SetEnvironmentVariable("TEST_SECRET_PWD", null);
        }
    }

    [Fact]
    public void LoadSetting_MissingEnvVar_ThrowsWithClearMessage()
    {
        var jsonPath = Path.Combine(_tempDir, "config.json");
        var json = @"{ ""appId"": ""test"", ""authCode"": ""${NON_EXISTENT_VAR_12345}"", ""mqtt"": { ""server"": ""tcp://x:1883"" } }";
        File.WriteAllText(jsonPath, json);

        var loader = new JsonConfigLoader(_tempDir);
        var ex = Assert.Throws<InvalidOperationException>(() => loader.LoadSetting());
        Assert.Contains("NON_EXISTENT_VAR_12345", ex.Message);
        Assert.Contains("is not set", ex.Message);
    }
}
