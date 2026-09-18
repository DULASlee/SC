using System.Net.Sockets;
using DotNet.Testcontainers.Builders;       // 4.x: NetworkBuilder 在顶层 DotNet.Testcontainers
using DotNet.Testcontainers.Networks;
using Testcontainers.Mosquitto;
using Testcontainers.Toxiproxy;

namespace ReliabilityTests;

/// <summary>
/// L4-A 工具链 Fixture：Mosquitto broker + Toxiproxy 容器骨架。
///
/// 当前是"按需构造"——不实际启动 Docker 容器，由调用方在 InitializeAsync 决定
/// 何时触发 Docker（架构师 §四未要求本地跑容器）。
///
/// 真实业务可靠性场景（断网 30s 零丢失等）留给 L4-B+ 任务卡。
/// </summary>
public sealed class MqttBrokerFixture : IAsyncLifetime
{
    private readonly INetwork _network = new NetworkBuilder()
        .WithName($"reliability-{Guid.NewGuid():N}")
        .Build();

    private MosquittoContainer? _broker;
    private ToxiproxyContainer? _toxiproxy;

    /// <summary>Toxiproxy HTTP 控制端口（4.x 用 FirstProxiedPort 常量；未启动容器时为 null）。</summary>
    public ushort? ToxiproxyMappedPort => _toxiproxy?.GetMappedPublicPort(ToxiproxyBuilder.FirstProxiedPort);

    /// <summary>Toxiproxy 主机名（未启动容器时返回 null）。</summary>
    public string? ToxiproxyHostname => _toxiproxy?.Hostname;

    public async Task InitializeAsync()
    {
        // Testcontainers 4.x：构造器强制传 image（无参构造器已 obsolete → CS0618）
        _broker = new MosquittoBuilder("eclipse-mosquitto:2.0")
            .WithNetwork(_network)
            .WithNetworkAliases("mqtt-broker")
            .Build();

        await _broker.StartAsync();

        _toxiproxy = new ToxiproxyBuilder("ghcr.io/shopify/toxiproxy:2.9.0")
            .WithNetwork(_network)
            .Build();

        await _toxiproxy.StartAsync();
    }

    public async Task DisposeAsync()
    {
        if (_broker is not null)
        {
            await _broker.DisposeAsync();
        }

        if (_toxiproxy is not null)
        {
            await _toxiproxy.DisposeAsync();
        }

        await _network.DisposeAsync();
    }

    /// <summary>TCP 端口可达性测试（不依赖 Mosquitto/Toxiproxy 业务协议）。</summary>
    public async Task<bool> CanHandshakeAsync()
    {
        if (_toxiproxy is null)
        {
            return false;
        }

        ushort port = ToxiproxyMappedPort ?? 0;
        if (port == 0)
        {
            return false;
        }

        using TcpClient tcp = new TcpClient();
        Task connect = tcp.ConnectAsync(_toxiproxy.Hostname, port);
        Task timeout = Task.Delay(TimeSpan.FromSeconds(2));
        Task first = await Task.WhenAny(connect, timeout);
        return first == connect && tcp.Connected;
    }
}
