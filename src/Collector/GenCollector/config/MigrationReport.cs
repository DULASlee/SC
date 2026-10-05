using System;
using System.Collections.Generic;
using System.Linq;

namespace GenCollector.Config
{
    public class MigrationReport : IMigrationReport
    {
        public string SourceFile { get; set; }
        public string TargetFile { get; set; }
        public DateTime MigratedAt { get; set; }
        public Dictionary<string, string> FieldMappings { get; set; } = new Dictionary<string, string>();
        public List<string> Warnings { get; set; } = new List<string>();
        public bool Success { get; set; }
        public string Message { get; set; }

        // explicit interface implementation
        IReadOnlyDictionary<string, string> IMigrationReport.FieldMappings => FieldMappings;
        IReadOnlyList<string> IMigrationReport.Warnings => Warnings;

        public static MigrationReport Skipped(string sourceFile, string targetFile, string reason)
        {
            return new MigrationReport
            {
                SourceFile = sourceFile,
                TargetFile = targetFile,
                MigratedAt = DateTimeOffset.UtcNow.UtcDateTime,
                Success = true,
                Message = $"Skipped: {reason}"
            };
        }

        public static MigrationReport Failed(string sourceFile, string targetFile, string reason, IEnumerable<string> warnings = null)
        {
            return new MigrationReport
            {
                SourceFile = sourceFile,
                TargetFile = targetFile,
                MigratedAt = DateTimeOffset.UtcNow.UtcDateTime,
                Success = false,
                Message = $"Failed: {reason}",
                Warnings = warnings?.ToList() ?? new List<string>()
            };
        }

        public static MigrationReport Succeeded(string sourceFile, string targetFile,
            Dictionary<string, string> fieldMappings, IEnumerable<string> warnings = null)
        {
            return new MigrationReport
            {
                SourceFile = sourceFile,
                TargetFile = targetFile,
                MigratedAt = DateTimeOffset.UtcNow.UtcDateTime,
                Success = true,
                Message = "Migrated successfully",
                FieldMappings = fieldMappings ?? new Dictionary<string, string>(),
                Warnings = warnings?.ToList() ?? new List<string>()
            };
        }
    }
}
