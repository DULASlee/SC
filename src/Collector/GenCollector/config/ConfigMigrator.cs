using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;

namespace GenCollector.Config
{
    public class ConfigMigrator
    {
        private readonly string _configDir;
        private readonly BackupManager _backupManager;
        private readonly string _outputDir;

        public ConfigMigrator(string configDir, string outputDir = null, BackupManager backupManager = null)
        {
            _configDir = configDir;
            _outputDir = outputDir ?? Path.Combine(_configDir, "output");
            _backupManager = backupManager;
        }

        /// <summary>
        /// Returns true if the target file exists and is valid (non-empty, parseable JSON).
        /// </summary>
        private bool IsTargetValid(string targetPath)
        {
            if (!File.Exists(targetPath)) return false;
            try
            {
                var content = File.ReadAllText(targetPath);
                if (string.IsNullOrWhiteSpace(content)) return false;
                JsonConvert.DeserializeObject(content);
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Migrates all four config file types and writes JSON outputs.
        /// Returns a report for each migrated or skipped file.
        /// </summary>
        public List<IMigrationReport> MigrateAll(bool force = false)
        {
            var reports = new List<IMigrationReport>();

            if (!Directory.Exists(_outputDir))
                Directory.CreateDirectory(_outputDir);

            var configPath = Path.Combine(_outputDir, "config.json");
            var devicesPath = Path.Combine(_outputDir, "devices.json");
            var varInfosPath = Path.Combine(_outputDir, "var_infos.json");
            var varGroupsPath = Path.Combine(_outputDir, "var_groups.json");

            // --- setting ---
            var settingSrc = Path.Combine(_configDir, "setting.ini");
            var settingFieldMappings = new Dictionary<string, string>
            {
                ["appId"] = "AppId", ["mqttServer"] = "MqttServer",
                ["mqttPrefix"] = "MqttPrefix", ["port"] = "Port",
                ["authCode"] = "AuthCode", ["simulate"] = "Simulate"
            };
            if (File.Exists(settingSrc))
            {
                if (!force && IsTargetValid(configPath))
                {
                    reports.Add(MigrationReport.Skipped(settingSrc, configPath, "Target already exists and is valid"));
                }
                else
                {
                    try
                    {
                        if (_backupManager != null)
                            _backupManager.SaveBackup("setting.ini", File.ReadAllText(settingSrc));

                        var setting = MigrateSetting();
                        var json = JsonConvert.SerializeObject(setting, Formatting.Indented);
                        File.WriteAllText(configPath, json);
                        reports.Add(MigrationReport.Succeeded(settingSrc, configPath, settingFieldMappings));
                    }
                    catch (UnauthorizedAccessException ex)
                    {
                        reports.Add(MigrationReport.Failed(settingSrc, configPath, ex.Message));
                    }
                    catch (IOException ex)
                    {
                        reports.Add(MigrationReport.Failed(settingSrc, configPath, ex.Message));
                    }
                }
            }

            // --- devices ---
            var deviceFiles = Directory.GetFiles(_configDir, "device_*.ini");
            if (deviceFiles.Length > 0)
            {
                if (!force && IsTargetValid(devicesPath))
                {
                    foreach (var f in deviceFiles)
                        reports.Add(MigrationReport.Skipped(f, devicesPath, "Target already exists and is valid"));
                }
                else
                {
                    try
                    {
                        foreach (var f in deviceFiles)
                            if (_backupManager != null)
                                _backupManager.SaveBackup(Path.GetFileName(f), File.ReadAllText(f));

                        var devices = MigrateDevices();
                        var json = JsonConvert.SerializeObject(new { devices }, Formatting.Indented);
                        File.WriteAllText(devicesPath, json);
                        reports.Add(MigrationReport.Succeeded(deviceFiles[0], devicesPath,
                            new Dictionary<string, string> { ["device_*.ini"] = "devices" }));
                    }
                    catch (IOException ex)
                    {
                        foreach (var f in deviceFiles)
                            reports.Add(MigrationReport.Failed(f, devicesPath, ex.Message));
                    }
                }
            }

            // --- var_infos ---
            var varInfoFiles = Directory.GetFiles(_configDir, "var_info_*.ini");
            if (varInfoFiles.Length > 0)
            {
                if (!force && IsTargetValid(varInfosPath))
                {
                    foreach (var f in varInfoFiles)
                        reports.Add(MigrationReport.Skipped(f, varInfosPath, "Target already exists and is valid"));
                }
                else
                {
                    try
                    {
                        foreach (var f in varInfoFiles)
                            if (_backupManager != null)
                                _backupManager.SaveBackup(Path.GetFileName(f), File.ReadAllText(f));

                        var varInfos = MigrateVarInfos();
                        var json = JsonConvert.SerializeObject(varInfos, Formatting.Indented);
                        File.WriteAllText(varInfosPath, json);
                        reports.Add(MigrationReport.Succeeded(varInfoFiles[0], varInfosPath,
                            new Dictionary<string, string> { ["var_info_*.ini"] = "var_infos" }));
                    }
                    catch (IOException ex)
                    {
                        foreach (var f in varInfoFiles)
                            reports.Add(MigrationReport.Failed(f, varInfosPath, ex.Message));
                    }
                }
            }

            // --- var_groups ---
            var varGroupFiles = Directory.GetFiles(_configDir, "var_group_*.ini");
            if (varGroupFiles.Length > 0)
            {
                if (!force && IsTargetValid(varGroupsPath))
                {
                    foreach (var f in varGroupFiles)
                        reports.Add(MigrationReport.Skipped(f, varGroupsPath, "Target already exists and is valid"));
                }
                else
                {
                    try
                    {
                        foreach (var f in varGroupFiles)
                            if (_backupManager != null)
                                _backupManager.SaveBackup(Path.GetFileName(f), File.ReadAllText(f));

                        var groups = MigrateVarGroups();
                        var json = JsonConvert.SerializeObject(new { groups }, Formatting.Indented);
                        File.WriteAllText(varGroupsPath, json);
                        reports.Add(MigrationReport.Succeeded(varGroupFiles[0], varGroupsPath,
                            new Dictionary<string, string> { ["var_group_*.ini"] = "var_groups" }));
                    }
                    catch (IOException ex)
                    {
                        foreach (var f in varGroupFiles)
                            reports.Add(MigrationReport.Failed(f, varGroupsPath, ex.Message));
                    }
                }
            }

            return reports;
        }

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
