using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace GenCollector.Config
{
    public class JsonConfigLoader
    {
        private readonly string _dir;
        private readonly BackupManager _backup;

        // Sensitive field patterns (case-insensitive)
        private static readonly string[] SensitivePatterns = new[]
        {
            "password", "token", "secret", "private", "credential", "auth"
        };

        private static readonly Regex EnvVarPattern = new Regex(
            @"\$\{([^}]+)\}",
            RegexOptions.Compiled | RegexOptions.IgnoreCase);

        public JsonConfigLoader(string dir, int maxBackups = 50)
        {
            _dir = dir;
            _backup = new BackupManager(Path.Combine(dir, ".backups"), maxBackups);
        }

        public SettingConfig LoadSetting()
        {
            var jsonPath = Path.Combine(_dir, "config.json");

            // Scenario 1: JSON exists + parse fails → throw InvalidOperationException
            // Config is corrupted; refusing to start prevents silent misconfiguration.
            if (File.Exists(jsonPath))
            {
                string json;
                try
                {
                    json = File.ReadAllText(jsonPath);
                }
                catch (IOException ex)
                {
                    throw new InvalidOperationException(
                        $"config.json exists but could not be read: {ex.Message}", ex);
                }

                object obj;
                try
                {
                    obj = JObject.Parse(json);
                }
                catch (Newtonsoft.Json.JsonException ex)
                {
                    throw new InvalidOperationException(
                        $"config.json is malformed JSON — config is corrupted and must be repaired before start. " +
                        $"Original error: {ex.Message}", ex);
                }

                _backup.SaveBackup("config.json", json);
                ResolveAndCheckSensitive((JObject)obj, "config.json");
                return new SettingConfig
                {
                    AppId = ((JObject)obj)["appId"]?.ToString(),
                    MqttServer = ResolveEnvVars(((JObject)obj)["mqtt"]?["server"]?.ToString()),
                    MqttPrefix = ((JObject)obj)["mqtt"]?["prefix"]?.ToString() ?? "/YLCY/CNC/",
                    Port = ((JObject)obj)["port"]?.Value<int>() ?? 8080,
                    AuthCode = ResolveEnvVars(((JObject)obj)["authCode"]?.ToString()),
                    Simulate = ((JObject)obj)["simulate"]?.Value<bool>() ?? false
                };
            }

            // JSON missing — check migration marker to decide between Scenario 3 and 4
            var migrationMarkerPath = Path.Combine(_dir, ".migration_complete");

            // Scenario 3: JSON missing + migration NOT complete → load INI, emit warning, set migration marker
            if (!File.Exists(migrationMarkerPath))
            {
                // Emit a warning so operators notice the fallback; set marker so next start uses Scenario 4.
                Console.Error.WriteLine($"[JsonConfigLoader] WARNING: config.json not found in {_dir}; loading legacy INI config as fallback.");
                Console.Error.WriteLine($"[JsonConfigLoader] WARNING: INI fallback used — migration marker set. Remove marker to suppress this warning.");
                try
                {
                    File.WriteAllText(migrationMarkerPath,
                        $"{{\"migratedAt\":\"{DateTime.UtcNow:O}\",\"source\":\"INI\"}}");
                }
                catch
                {
                    // Marker write failure is non-fatal; we'll warn again on next start.
                }
                return ConfigLoader.LoadSetting(_dir);
            }

            // Scenario 4: JSON missing + migration IS complete → throw InvalidOperationException
            // This is an unexpected state: JSON was deleted after migration or deployment is misconfigured.
            throw new InvalidOperationException(
                $"config.json is missing but migration marker exists — unexpected state. " +
                $"The JSON config should be present after INI migration completes. " +
                $"Either restore config.json or remove the migration marker to re-trigger INI fallback.");
        }

        public List<DeviceConfig> LoadDevices()
        {
            var jsonPath = Path.Combine(_dir, "devices.json");
            if (File.Exists(jsonPath))
            {
                var json = File.ReadAllText(jsonPath);
                _backup.SaveBackup("devices.json", json);
                var obj = JObject.Parse(json);
                ResolveAndCheckSensitive(obj, "devices.json");
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
                ResolveAndCheckSensitive(JObject.Parse(json), "var_infos.json");
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
                ResolveAndCheckSensitive(obj, "var_groups.json");
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

        /// <summary>
        /// Resolves ${ENV_VAR_NAME} placeholders in a string value.
        /// Throws InvalidOperationException if the env var is not defined.
        /// </summary>
        private string ResolveEnvVars(string value)
        {
            if (string.IsNullOrEmpty(value)) return value;

            return EnvVarPattern.Replace(value, match =>
            {
                var varName = match.Groups[1].Value;
                var envVal = Environment.GetEnvironmentVariable(varName);
                if (envVal == null)
                {
                    throw new InvalidOperationException(
                        $"Environment variable '{varName}' is not set. " +
                        $"Sensitive config values must reference existing environment variables using ${{{varName}}} syntax.");
                }
                return envVal;
            });
        }

        /// <summary>
        /// Resolves env vars in string values and then checks that sensitive fields
        /// (password/token/secret/etc.) are not plain-text.
        /// Throws InvalidOperationException if any sensitive field is plain-text or
        /// references a non-existent env var.
        /// </summary>
        private void ResolveAndCheckSensitive(JObject obj, string fileName)
        {
            ResolveAndCheckInObject(obj, fileName, "");
        }

        private void ResolveAndCheckInObject(JObject obj, string fileName, string path)
        {
            foreach (var prop in obj.Properties())
            {
                var key = prop.Name;
                var value = prop.Value;

                if (value is JObject nested)
                {
                    ResolveAndCheckInObject(nested, fileName, $"{path}{key}.");
                }
                else if (value is JArray arr)
                {
                    for (int i = 0; i < arr.Count; i++)
                    {
                        if (arr[i] is JObject itemObj)
                            ResolveAndCheckInObject(itemObj, fileName, $"{path}{key}[{i}].");
                    }
                }
                else if (value is JValue jv && jv.Value is string strVal)
                {
                    if (IsSensitiveKey(key))
                    {
                        if (strVal.StartsWith("${") && strVal.EndsWith("}"))
                        {
                            // Env-var reference: resolve it; if var not found, ResolveEnvVars throws
                            var resolved = ResolveEnvVars(strVal);
                            // Replace the value in-place so LoadSetting gets the resolved string
                            jv.Value = resolved;
                        }
                        else if (!string.IsNullOrEmpty(strVal))
                        {
                            throw new InvalidOperationException(
                                $"Sensitive field '{path}{key}' in '{fileName}' contains plain-text value. " +
                                $"Use ${{ENV_VAR_NAME}} syntax to reference environment variables instead.");
                        }
                    }
                }
            }
        }

        private static bool IsSensitiveKey(string key)
        {
            var lower = key.ToLowerInvariant();
            foreach (var p in SensitivePatterns)
            {
                if (lower.Contains(p)) return true;
            }
            return false;
        }

        private static bool IsEnvVarReference(string value)
        {
            return !string.IsNullOrEmpty(value)
                && value.StartsWith("${")
                && value.Contains("}")
                && Environment.GetEnvironmentVariable(
                    EnvVarPattern.Match(value).Groups[1].Value) != null;
        }
    }
}
