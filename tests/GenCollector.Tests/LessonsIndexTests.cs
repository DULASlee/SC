using Newtonsoft.Json.Linq;
using System;
using System.IO;
using Xunit;

// 029 ④ parameterized settlement acceptance (resident test, architect-authorized).
// Settlement cards write the index + lessons (both under docs/, AI-writable) and
// point their acceptance_tests at this file; no card ever creates tests/ files.
public class LessonsIndexTests
{
    private const string IndexRelativePath = "docs/ai-workspace/rules/lessons-index.json";
    private const string DefaultLessonsRelativePath = "docs/ai-workspace/rules/lessons-learned.md";

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir != null)
        {
            if (Directory.Exists(Path.Combine(dir.FullName, ".harness")))
            {
                return dir.FullName;
            }
            dir = dir.Parent;
        }
        throw new DirectoryNotFoundException(
            "Cannot locate repo root (directory containing .harness/) from " + AppContext.BaseDirectory);
    }

    private static JObject LoadIndex()
    {
        var indexPath = Path.Combine(FindRepoRoot(), ToPath(IndexRelativePath));
        if (!File.Exists(indexPath))
        {
            return null;
        }
        return JObject.Parse(File.ReadAllText(indexPath));
    }

    private static string ToPath(string forwardSlashed)
    {
        return forwardSlashed.Replace('/', Path.DirectorySeparatorChar);
    }

    [Fact]
    public void Index_Missing_Or_WithoutEntries_IsVacuousPass()
    {
        var index = LoadIndex();
        if (index == null)
        {
            Assert.True(true, "lessons-index.json not written yet: settlement acceptance vacuously passes");
            return;
        }
        var entries = index["entries"] as JArray;
        Assert.NotNull(entries);
        if (entries.Count == 0)
        {
            Assert.True(true, "lessons-index.json has no entries yet: settlement acceptance vacuously passes");
        }
    }

    [Fact]
    public void Index_WhenPresent_EachEntry_IsAssertedInLessonsFile()
    {
        var index = LoadIndex();
        if (index == null)
        {
            return;
        }

        var root = FindRepoRoot();
        var lessonsRelative = index["lessons_file"]?.Value<string>() ?? DefaultLessonsRelativePath;
        var lessonsPath = Path.Combine(root, ToPath(lessonsRelative));
        Assert.True(File.Exists(lessonsPath), "lessons file missing: " + lessonsRelative);
        var content = File.ReadAllText(lessonsPath);

        var entries = index["entries"] as JArray;
        Assert.NotNull(entries);
        foreach (var entry in entries)
        {
            var task = entry?["task"]?.Value<string>() ?? "";
            var keyConclusion = entry?["key_conclusion"]?.Value<string>() ?? "";
            Assert.False(string.IsNullOrWhiteSpace(task), "index entry missing task field");
            Assert.False(string.IsNullOrWhiteSpace(keyConclusion),
                "index entry missing key_conclusion: " + task);
            Assert.Contains(task, content, StringComparison.Ordinal);
            Assert.Contains(keyConclusion, content, StringComparison.Ordinal);
        }
    }
}
