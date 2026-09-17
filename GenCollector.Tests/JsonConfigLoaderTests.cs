using GenCollector;
using GenCollector.Config;
using System;
using System.IO;
using Xunit;

public class JsonConfigLoaderTests
{
    [Fact]
    public void LoadSetting_FromJson_ParsesCorrectly()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"jcl_{Guid.NewGuid()}");
        Directory.CreateDirectory(tempDir);
        Directory.CreateDirectory(Path.Combine(tempDir, ".backups"));
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
        Directory.CreateDirectory(Path.Combine(tempDir, ".backups"));
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
        Directory.CreateDirectory(Path.Combine(tempDir, ".backups"));
        var loader = new JsonConfigLoader(tempDir);
        loader.SaveSetting(new SettingConfig { AppId = "saved", MqttServer = "tcp://saved:1883" });
        Assert.True(File.Exists(Path.Combine(tempDir, "config.json")));
        var content = File.ReadAllText(Path.Combine(tempDir, "config.json"));
        Assert.Contains("saved", content);
        Directory.Delete(tempDir, true);
    }
}