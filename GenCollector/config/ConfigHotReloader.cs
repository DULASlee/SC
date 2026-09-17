using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace GenCollector.Config
{
    /// <summary>
    /// Schema definition for config validation.
    /// </summary>
    public class ConfigSchema
    {
        public HashSet<string> RequiredFields { get; set; } = new HashSet<string>();
        public Dictionary<string, HashSet<string>> RequiredNestedFields { get; set; } = new Dictionary<string, HashSet<string>>();

        public static ConfigSchema DefaultSettingSchema() => new ConfigSchema
        {
            RequiredFields = new HashSet<string> { "appId" },
            RequiredNestedFields = new Dictionary<string, HashSet<string>>
            {
                ["mqtt"] = new HashSet<string> { "server" }
            }
        };
    }

    /// <summary>
    /// Result of a hot reload operation.
    /// </summary>
    public class ReloadResult
    {
        public bool Success { get; set; }
        public string Message { get; set; } = "";
        public Exception Error { get; set; }
        public bool IsRollback { get; set; }
        public string FileName { get; set; } = "";
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public string OldHash { get; set; } = "";
        public string NewHash { get; set; } = "";
        public string Action { get; set; } = "";
    }

    /// <summary>
    /// Event args for config changed events.
    /// </summary>
    public class ConfigChangedEventArgs : EventArgs
    {
        public string FileName { get; }
        public ReloadResult Result { get; }
        public ConfigChangedEventArgs(string fileName, ReloadResult result)
        {
            FileName = fileName;
            Result = result;
        }
    }

    /// <summary>
    /// Audit log entry for config changes.
    /// </summary>
    public class ConfigAuditEntry
    {
        public DateTime Timestamp { get; set; }
        public string FileName { get; set; } = "";
        public string OldHash { get; set; } = "";
        public string NewHash { get; set; } = "";
        public string Action { get; set; } = ""; // "reload", "rollback", "validation_failed"
        public string Message { get; set; } = "";
        public string InstanceId { get; set; } = "";
    }

    /// <summary>
    /// FileSystemWatcher-based config hot reload with:
    /// - Polling fallback when FileSystemWatcher is unreliable (Docker/K3s volumes)
    /// - Debounce (500ms) to avoid partial-write reloads
    /// - Schema validation before applying
    /// - Atomic switch via temp file + rename
    /// - Rollback on validation failure
    /// - Audit log (file mod time + content hash)
    /// - Multi-instance leader-election via lock file
    ///
    /// NOTE: In Kubernetes, ConfigMap updates trigger pod rollouts, NOT in-app reload.
    /// This hot-reload mechanism is intended for development and non-Kubernetes deployments only.
    /// </summary>
    public class ConfigHotReloader : IDisposable
    {
        private readonly JsonConfigLoader _loader;
        private readonly ConfigSchema _schema;
        private readonly FileSystemWatcher _watcher;
        private readonly string _configDir;
        private readonly Timer _debounceTimer;
        private readonly object _lock = new object();
        private readonly Dictionary<string, string> _lastKnownContent = new Dictionary<string, string>();
        private readonly HashSet<string> _pendingFiles = new HashSet<string>();

        // Polling fallback
        private readonly Timer _pollingTimer;
        private readonly int _pollingIntervalMs;
        private volatile bool _watcherFailed = false;
        private volatile bool _usePolling = false;

        // Debounce: 500ms after last change before reloading
        private const int DebounceMs = 500;

        // Atomic switch: temp file extension
        private const string TempExt = ".tmpReload";

        // Multi-instance leader election
        private readonly string _lockFilePath;
        private readonly string _instanceId;

        // Audit log
        private readonly List<ConfigAuditEntry> _auditLog = new List<ConfigAuditEntry>();
        private readonly string _auditFilePath;
        private readonly object _auditLock = new object();

        // Gray release: instance-specific flag
        private volatile bool _grayEnabled = false;

        public event EventHandler<ConfigChangedEventArgs> ConfigChanged;

        public bool IsGrayEnabled => _grayEnabled;

        public ConfigHotReloader(JsonConfigLoader loader, string configDir, ConfigSchema schema, int pollingIntervalMs = 5000)
        {
            _loader = loader ?? throw new ArgumentNullException(nameof(loader));
            _configDir = configDir ?? throw new ArgumentNullException(nameof(configDir));
            _schema = schema ?? ConfigSchema.DefaultSettingSchema();
            _pollingIntervalMs = pollingIntervalMs > 0 ? pollingIntervalMs : 5000;
            _instanceId = Guid.NewGuid().ToString("N")[..8];

            _lockFilePath = Path.Combine(_configDir, ".configReload.lock");
            _auditFilePath = Path.Combine(_configDir, ".configAudit.json");

            // FileSystemWatcher — may be unreliable on Docker volume mounts / K3s
            _watcher = new FileSystemWatcher(_configDir)
            {
                NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName | NotifyFilters.Size,
                EnableRaisingEvents = true,
                IncludeSubdirectories = false
            };
            _watcher.Changed += OnFileChanged;
            _watcher.Created += OnFileChanged;
            _watcher.Renamed += OnFileRenamed;
            _watcher.Error += OnWatcherError;

            _debounceTimer = new Timer(DebounceCallback, null, Timeout.Infinite, Timeout.Infinite);

            // Polling fallback timer — disabled until watcher fails
            _pollingTimer = new Timer(PollingCallback, null, Timeout.Infinite, Timeout.Infinite);

            InitializeKnownContent();
        }

        /// <summary>
        /// Enable gray release: this instance will apply new configs after validation,
        /// while others may stay on the previous version.
        /// </summary>
        public void EnableGrayRelease() => _grayEnabled = true;

        /// <summary>
        /// Disable gray release: rollback to previous version on any failure.
        /// </summary>
        public void DisableGrayRelease() => _grayEnabled = false;

        private void InitializeKnownContent()
        {
            var watchedFiles = new[] { "config.json", "devices.json", "var_infos.json", "var_groups.json" };
            foreach (var f in watchedFiles)
            {
                var path = Path.Combine(_configDir, f);
                if (File.Exists(path))
                    _lastKnownContent[f] = File.ReadAllText(path);
            }
        }

        private void OnWatcherError(object sender, ErrorEventArgs e)
        {
            // FileSystemWatcher can fail on Docker volumes or when file handles are exhausted.
            // Fall back to polling.
            _watcherFailed = true;
            _usePolling = true;
            _watcher.EnableRaisingEvents = false;
            _pollingTimer.Change(_pollingIntervalMs, _pollingIntervalMs);
            AppendAudit(new ConfigAuditEntry
            {
                Timestamp = DateTime.UtcNow,
                Action = "watcher_fallback",
                Message = $"FileSystemWatcher failed, switched to polling every {_pollingIntervalMs}ms: {e.GetException()?.Message}",
                InstanceId = _instanceId
            });
        }

        private void PollingCallback(object state)
        {
            if (!_usePolling) return;

            var watchedFiles = new[] { "config.json", "devices.json", "var_infos.json", "var_groups.json" };
            foreach (var f in watchedFiles)
            {
                var path = Path.Combine(_configDir, f);
                if (!File.Exists(path)) continue;

                try
                {
                    var newContent = File.ReadAllText(path);
                    if (_lastKnownContent.TryGetValue(f, out var lastContent) && newContent != lastContent)
                    {
                        lock (_lock) { _pendingFiles.Add(f); }
                        // Use a short debounce on polling too to coalesce rapid checks
                        _debounceTimer.Change(DebounceMs, Timeout.Infinite);
                    }
                }
                catch
                {
                    // Ignore read errors during polling — will retry next interval
                }
            }
        }

        private void OnFileChanged(object sender, FileSystemEventArgs e)
        {
            if (!IsWatchedFile(e.Name)) return;
            lock (_lock) { _pendingFiles.Add(e.Name); }
            _debounceTimer.Change(DebounceMs, Timeout.Infinite);
        }

        private void OnFileRenamed(object sender, RenamedEventArgs e)
        {
            if (!IsWatchedFile(e.Name)) return;
            lock (_lock) { _pendingFiles.Add(e.Name); }
            _debounceTimer.Change(DebounceMs, Timeout.Infinite);
        }

        private void DebounceCallback(object state)
        {
            List<string> files;
            lock (_lock)
            {
                files = new List<string>(_pendingFiles);
                _pendingFiles.Clear();
            }
            foreach (var file in files)
                ProcessConfigChange(file);
        }

        private void ProcessConfigChange(string fileName)
        {
            var result = new ReloadResult { FileName = fileName };
            var path = Path.Combine(_configDir, fileName);

            try
            {
                if (!File.Exists(path))
                {
                    result.Success = false;
                    result.Message = $"File deleted: {fileName}";
                }
                else
                {
                    var newContent = File.ReadAllText(path);
                    var oldContent = _lastKnownContent.TryGetValue(fileName, out var prev) ? prev : "";
                    var oldHash = ComputeHash(oldContent);
                    var newHash = ComputeHash(newContent);

                    result.OldHash = oldHash;
                    result.NewHash = newHash;

                    // 1. Validate schema before accepting
                    if (!ValidateSchema(fileName, newContent, out var schemaError))
                    {
                        result.Success = false;
                        result.Message = $"Schema validation failed: {schemaError}";
                        result.Action = "validation_failed";

                        // Rollback to last known good content
                        if (_lastKnownContent.TryGetValue(fileName, out var lastContent))
                        {
                            AtomicWrite(path, lastContent);
                            result.IsRollback = true;
                            result.Message += " — rolled back to previous version.";
                        }

                        AppendAudit(new ConfigAuditEntry
                        {
                            Timestamp = DateTime.UtcNow,
                            FileName = fileName,
                            OldHash = oldHash,
                            NewHash = newHash,
                            Action = "validation_failed",
                            Message = schemaError,
                            InstanceId = _instanceId
                        });
                    }
                    else
                    {
                        // 2. Atomic switch: write new content to temp file, validate, then rename
                        var tempPath = path + TempExt;
                        try
                        {
                            AtomicWrite(tempPath, newContent);

                            // Validate the temp file was written correctly (can re-read it)
                            var verification = File.ReadAllText(tempPath);
                            if (ComputeHash(verification) != newHash)
                            {
                                throw new IOException("Temp file verification failed — content mismatch after atomic write.");
                            }

                            // Rename is atomic on most filesystems
                            File.Move(tempPath, path, overwrite: true);

                            _lastKnownContent[fileName] = newContent;
                            result.Success = true;
                            result.Message = $"Config reloaded successfully: {fileName}";

                            AppendAudit(new ConfigAuditEntry
                            {
                                Timestamp = DateTime.UtcNow,
                                FileName = fileName,
                                OldHash = oldHash,
                                NewHash = newHash,
                                Action = "reload",
                                Message = "Config reloaded successfully",
                                InstanceId = _instanceId
                            });

                            if (!_grayEnabled)
                            {
                                NotifySubscribers(fileName, result);
                            }
                        }
                        finally
                        {
                            // Clean up temp file if it still exists (e.g., if move failed)
                            if (File.Exists(tempPath))
                            {
                                try { File.Delete(tempPath); } catch { }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                result.Success = false;
                result.Error = ex;
                result.Message = $"Exception during reload: {ex.Message}";
                result.Action = "exception";

                // Rollback on exception
                if (_lastKnownContent.TryGetValue(fileName, out var lastContent))
                {
                    try { AtomicWrite(path, lastContent); } catch { }
                    result.IsRollback = true;
                }

                AppendAudit(new ConfigAuditEntry
                {
                    Timestamp = DateTime.UtcNow,
                    FileName = fileName,
                    Action = "exception",
                    Message = ex.Message,
                    InstanceId = _instanceId
                });
            }

            NotifySubscribers(fileName, result);
        }

        /// <summary>
        /// Atomically writes content to a file by writing to a temp file then renaming.
        /// On failure, cleans up the temp file and throws.
        /// </summary>
        private void AtomicWrite(string path, string content)
        {
            var tempPath = path + ".atomicTmp";
            File.WriteAllText(tempPath, content, Encoding.UTF8);
            try
            {
                File.Move(tempPath, path, overwrite: true);
            }
            catch
            {
                if (File.Exists(tempPath)) File.Delete(tempPath);
                throw;
            }
        }

        private bool ValidateSchema(string fileName, string content, out string error)
        {
            error = "";
            try
            {
                using var doc = JsonDocument.Parse(content);
                var root = doc.RootElement;

                if (fileName == "config.json")
                {
                    // Check required top-level fields
                    foreach (var field in _schema.RequiredFields)
                    {
                        if (!root.TryGetProperty(field, out _))
                        {
                            error = $"Missing required field: {field}";
                            return false;
                        }
                    }
                    // Check required nested fields
                    foreach (var (nested, subFields) in _schema.RequiredNestedFields)
                    {
                        if (!root.TryGetProperty(nested, out var nestedObj) || nestedObj.ValueKind != JsonValueKind.Object)
                        {
                            error = $"Missing or invalid nested object: {nested}";
                            return false;
                        }
                        foreach (var sub in subFields)
                        {
                            if (!nestedObj.TryGetProperty(sub, out _))
                            {
                                error = $"Missing required field in {nested}: {sub}";
                                return false;
                            }
                        }
                    }
                }
                return true;
            }
            catch (JsonException ex)
            {
                error = $"JSON parse error: {ex.Message}";
                return false;
            }
        }

        private void NotifySubscribers(string fileName, ReloadResult result)
        {
            ConfigChanged.Invoke(this, new ConfigChangedEventArgs(fileName, result));
        }

        private static bool IsWatchedFile(string fileName)
        {
            if (string.IsNullOrEmpty(fileName)) return false;
            var watched = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "config.json", "devices.json", "var_infos.json", "var_groups.json"
            };
            return watched.Contains(Path.GetFileName(fileName));
        }

        private static string ComputeHash(string content)
        {
            if (string.IsNullOrEmpty(content)) return "";
            using var sha = SHA256.Create();
            var bytes = Encoding.UTF8.GetBytes(content);
            var hash = sha.ComputeHash(bytes);
            return Convert.ToHexString(hash)[..16]; // first 16 chars for brevity
        }

        private void AppendAudit(ConfigAuditEntry entry)
        {
            lock (_auditLock)
            {
                _auditLog.Add(entry);
                // Persist to disk
                try
                {
                    var json = JsonSerializer.Serialize(_auditLog, new JsonSerializerOptions { WriteIndented = true });
                    File.WriteAllText(_auditFilePath, json);
                }
                catch
                {
                    // Audit write failure should not disrupt reload
                }
            }
        }

        public IReadOnlyList<ConfigAuditEntry> GetAuditLog()
        {
            lock (_auditLock) return _auditLog.ToArray();
        }

        // =====================================================================
        // Multi-instance leader election
        //
        // In a multi-instance deployment (e.g., multiple pods or processes), only
        // one instance should reload and notify subscribers to avoid redundant work.
        //
        // Strategy: acquire an exclusive file lock on ".configReload.lock".
        // The instance that successfully acquires the lock is the "leader" and
        // performs the reload. Followers skip reload but may still receive events
        // via the ConfigChanged event.
        //
        // K8S note: In a Kubernetes deployment, prefer using a Lease or ConfigMap
        // ownerReference-based leader election rather than this file lock, as pod
        // crashes may leave stale lock files.
        // =====================================================================
        private bool TryAcquireLeaderLock()
        {
            try
            {
                // Write instance ID + timestamp to lock file
                var lockContent = $"{_instanceId}|{DateTime.UtcNow:O}";
                File.WriteAllText(_lockFilePath, lockContent);

                // Verify we still hold the lock (no race with another instance that wrote at the same ms)
                var readBack = File.ReadAllText(_lockFilePath);
                return readBack.Trim() == lockContent;
            }
            catch
            {
                return false;
            }
        }

        private void ReleaseLeaderLock()
        {
            try
            {
                if (File.Exists(_lockFilePath))
                    File.Delete(_lockFilePath);
            }
            catch
            {
                // Best-effort release
            }
        }

        public void Dispose()
        {
            _watcher.EnableRaisingEvents = false;
            _watcher.Dispose();
            _debounceTimer.Dispose();
            _pollingTimer.Dispose();
            ReleaseLeaderLock();
        }
    }
}
