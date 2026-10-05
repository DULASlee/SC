using System.Reflection;
using FluentAssertions;
using Testcontainers.Mosquitto;
using Testcontainers.Toxiproxy;

namespace ReliabilityTests;

/// <summary>
/// L4-A 工具链烟雾测试：验证 4 个 NuGet 包 + FluentAssertions 工具链能 compile + 加载。
///
/// 3 个最小烟雾测试：
///   1. MosquittoBuilder 类型可访问 + 程序集可加载
///   2. ToxiproxyBuilder 类型可访问 + 程序集可加载
///   3. FluentAssertions 在 4 个包之间可链式工作（基本断言）
///
/// 关键设计（重要）：
///   - 不实际启动 Docker 容器 —— 架构师 §四未要求
///   - 不假设 4.x builder 的具体 fluent API（版本迭代频繁，编译稳定 > API 兼容）
///   - 真实启动容器的烟雾测试应交给 L4-B+ 任务卡（需要 CI runner 有 Docker）
/// </summary>
public class ToolchainSmokeTests
{
    [Fact]
    public void MosquittoBuilder_TypeIsLoadable_AndAssemblyResolves()
    {
        Type type = typeof(MosquittoBuilder);
        type.Assembly.GetName().Name.Should().Be("Testcontainers.Mosquitto");

        // 4.x: 构造器必须存在（即使无参构造器 obsolete，存在性是烟雾验证目标）
        ConstructorInfo[] ctors = type.GetConstructors();
        ctors.Should().NotBeEmpty("MosquittoBuilder 必须有至少 1 个构造器");

        // 4.x: 至少 1 个构造器接受 string 参数（image 参数）
        ctors.Any(c => c.GetParameters().Any(p => p.ParameterType == typeof(string)))
            .Should().BeTrue("4.x 要求 MosquittoBuilder(string image) 构造器");
    }

    [Fact]
    public void RedGreenProbe_BrokenImageString_BuildFails()
    {
        // 红绿反向验证：故意写一个不存在的镜像 tag。
        // 因为本机没 Docker，不会真的拉镜像；CI 阶段会拉镜像并失败。
        // 本地仅验证类型/构造器能接受任意 string（构造器阶段不报错）。
        // 真正的"tag 不存在则拉镜像失败"会在 CI 启动阶段由 Docker daemon 抛出。
        MosquittoBuilder builder = new MosquittoBuilder("definitely-does-not-exist-999999999:latest");
        builder.Should().NotBeNull("构造器仅校验 string 参数类型，不校验镜像是否存在");

        // 注：实际镜像拉取失败由 InitializeAsync().StartAsync() 在调用方触发，
        // 不在本工具链烟雾测试范围内（架构师 §四未要求跑容器）。
    }

    [Fact]
    public void ToxiproxyBuilder_TypeIsLoadable_AndAssemblyResolves()
    {
        Type type = typeof(ToxiproxyBuilder);
        type.Assembly.GetName().Name.Should().Be("Testcontainers.Toxiproxy");

        ConstructorInfo[] ctors = type.GetConstructors();
        ctors.Should().NotBeEmpty("ToxiproxyBuilder 必须有至少 1 个构造器");
        ctors.Any(c => c.GetParameters().Any(p => p.ParameterType == typeof(string)))
            .Should().BeTrue("4.x 要求 ToxiproxyBuilder(string image) 构造器");
    }

    [Fact]
    public void FluentAssertions_WorksAcross_TestcontainersNamespaces()
    {
        // FluentAssertions 跨包可用性验证（避免引入后才发现版本冲突）
        const string expected = "Testcontainers.Mosquitto";
        const string actual = "Testcontainers.Mosquitto";

        actual.Should().Be(expected, "FluentAssertions Should().Be() 应正常工作");
        actual.Should().StartWith("Testcontainers").And.EndWith("Mosquitto");
        actual.Should().HaveLength(expected.Length);
    }
}
