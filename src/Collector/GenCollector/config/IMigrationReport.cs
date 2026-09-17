using System;
using System.Collections.Generic;

namespace GenCollector.Config
{
    /// <summary>
    /// Represents the result of a single config migration operation.
    /// </summary>
    public interface IMigrationReport
    {
        /// <summary>Full path to the source file that was migrated.</summary>
        string SourceFile { get; }

        /// <summary>Full path to the destination file that was written.</summary>
        string TargetFile { get; }

        /// <summary>UTC timestamp when migration was performed.</summary>
        DateTime MigratedAt { get; }

        /// <summary>Describes how fields were mapped from source to target.</summary>
        IReadOnlyDictionary<string, string> FieldMappings { get; }

        /// <summary>Non-fatal issues encountered during migration.</summary>
        IReadOnlyList<string> Warnings { get; }

        /// <summary>True if migration succeeded; false if it was skipped or failed.</summary>
        bool Success { get; }

        /// <summary>Human-readable message describing the outcome.</summary>
        string Message { get; }
    }
}
