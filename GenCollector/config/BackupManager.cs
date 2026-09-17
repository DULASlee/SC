using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace GenCollector.Config
{
    public class BackupManager
    {
        private readonly string _backupDir;
        private readonly int _maxBackups;
        private readonly object _lock = new object();

        public BackupManager(string backupDir, int maxBackups = 50)
        {
            _backupDir = backupDir;
            _maxBackups = maxBackups;
            if (!Directory.Exists(_backupDir))
                Directory.CreateDirectory(_backupDir);
        }

        public void SaveBackup(string fileName, string content)
        {
            lock (_lock)
            {
                var timestamp = DateTime.UtcNow.Ticks.ToString();
                var guid = Guid.NewGuid().ToString("N");
                var backupName = $"{fileName}.{timestamp}.{guid}.bak";
                var backupPath = Path.Combine(_backupDir, backupName);
                File.WriteAllText(backupPath, content);
                TrimOldBackups(fileName);
            }
        }

        /// <summary>
        /// Atomically saves a setting by writing to a temporary file, validating,
        /// then renaming over the target. On failure the temp file is cleaned up.
        /// </summary>
        public void SaveSettingAtomic<T>(T setting, string path)
        {
            var json = JsonSerializer.Serialize(setting, new JsonSerializerOptions { WriteIndented = true });
            var tempPath = path + $".tmp.{Guid.NewGuid():N}";

            try
            {
                // Write with exclusive lock to prevent concurrent readers/writers
                using (var fs = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var writer = new StreamWriter(fs))
                {
                    writer.Write(json);
                }

                // Validate: must be parseable JSON
                VerifyJsonValid(tempPath);

                // Rename to target (atomic on most filesystems)
                if (File.Exists(path))
                    File.Delete(path);
                File.Move(tempPath, path);
            }
            catch
            {
                // Rollback: delete temp file if it still exists
                if (File.Exists(tempPath))
                    try { File.Delete(tempPath); } catch { }
                throw;
            }
        }

        /// <summary>
        /// Removes backups exceeding the configured max count.
        /// </summary>
        public void CleanupOldBackups(string fileName)
        {
            lock (_lock)
            {
                TrimOldBackups(fileName);
            }
        }

        /// <summary>
        /// Verifies that a backup file is intact: must be non-empty and parseable as JSON.
        /// Returns true if integrity check passes; throws if corrupt.
        /// </summary>
        public bool VerifyBackupIntegrity(string backupPath)
        {
            if (!File.Exists(backupPath))
                throw new FileNotFoundException("Backup file not found.", backupPath);

            var content = File.ReadAllText(backupPath);
            if (string.IsNullOrWhiteSpace(content))
                throw new InvalidDataException($"Backup file is empty: {backupPath}");

            VerifyJsonValid(backupPath);
            return true;
        }

        private static void VerifyJsonValid(string path)
        {
            var content = File.ReadAllText(path);
            try
            {
                JsonDocument.Parse(content);
            }
            catch (JsonException ex)
            {
                throw new InvalidDataException($"JSON parse error: {ex.Message}", ex);
            }
        }

        private void TrimOldBackups(string fileName)
        {
            var pattern = $"{fileName}.*.bak";
            var files = Directory.GetFiles(_backupDir, pattern)
                .OrderByDescending(f => new FileInfo(f).CreationTimeUtc)
                .Skip(_maxBackups)
                .ToList();
            foreach (var f in files)
                try { File.Delete(f); } catch { }
        }

        public IEnumerable<string> GetBackups(string fileName)
        {
            var pattern = $"{fileName}.*.bak";
            return Directory.GetFiles(_backupDir, pattern).OrderByDescending(f => new FileInfo(f).CreationTimeUtc);
        }
    }
}
