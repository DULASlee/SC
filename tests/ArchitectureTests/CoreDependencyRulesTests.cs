using System.Linq;
using System.Reflection;
using IoTPlatform.Core.Abstractions;
using NetArchTest.Rules;
using Xunit;

namespace ArchitectureTests
{
    /// <summary>
    /// 架构规则 1：IoTPlatform.Core 作为平台无关的核心 / 抽象层，
    /// 不得依赖 Adapters / UI / Host —— 依赖方向只能由外向内指向 Core。
    /// 说明：UI.Wpf -&gt; Adapters 的现存违规属于 Phase 1 待清偿技术债，
    /// 见 docs/tech-debt/ui-depends-on-adapters.md，本文件不将其写成红测试污染骨架 CI。
    /// </summary>
    public class CoreDependencyRulesTests
    {
        // 使用已知的 Core 公开类型定位其所在程序集（不用 InCurrentDomain，避免加载噪声）。
        private static readonly Assembly CoreAssembly = typeof(ICollector).Assembly;

        // 每条规则前断言类型数 > 0：防止因程序集为空而产生"假绿"。
        private static void AssertCoreAssemblyIsPopulated()
        {
            Assert.True(
                CoreAssembly.GetTypes().Length > 0,
                "IoTPlatform.Core 程序集必须包含类型，否则本架构测试无意义（假绿防护）。");
        }

        [Fact]
        public void Core_should_not_depend_on_Adapters()
        {
            AssertCoreAssemblyIsPopulated();
            var result = Types
                .InAssembly(CoreAssembly)
                .Should()
                .NotHaveDependencyOn("IoTPlatform.Adapters")
                .GetResult();
            Assert.True(result.FailingTypes == null || !result.FailingTypes.Any(), "Core 不得依赖 Adapters，违规类型: " + DescribeFailures(result.FailingTypes));
        }

        [Fact]
        public void Core_should_not_depend_on_UI()
        {
            AssertCoreAssemblyIsPopulated();
            var result = Types
                .InAssembly(CoreAssembly)
                .Should()
                .NotHaveDependencyOn("IoTPlatform.UI")
                .GetResult();
            Assert.True(result.FailingTypes == null || !result.FailingTypes.Any(), "Core 不得依赖 UI，违规类型: " + DescribeFailures(result.FailingTypes));
        }

        [Fact]
        public void Core_should_not_depend_on_Host()
        {
            AssertCoreAssemblyIsPopulated();
            var result = Types
                .InAssembly(CoreAssembly)
                .Should()
                .NotHaveDependencyOn("IoTPlatform.Host")
                .GetResult();
            Assert.True(result.FailingTypes == null || !result.FailingTypes.Any(), "Core 不得依赖 Host，违规类型: " + DescribeFailures(result.FailingTypes));
        }

        private static string DescribeFailures(System.Collections.Generic.IEnumerable<System.Type> failingTypes)
        {
            if (failingTypes == null)
            {
                return "(none)";
            }

            return string.Join(", ", failingTypes.Select(t => t.FullName));
        }
    }
}
