using System.Runtime.CompilerServices;
using System.Text;

namespace GenCollector.Tests;

/// <summary>
/// 在程序集加载时一次性注册 CodePagesEncodingProvider，
/// 以支持 Shift-JIS / GBK / GB18030 等 Windows 代码页编码（Ini 文件可能使用）。
///
/// 这是 <c>System.Text.Encoding.GetEncoding(int)</c> 在 .NET Core / .NET 5+ 上
/// 调用非 UTF-8 代码页所必需的；未注册时调用 Encoding.GetEncoding(932) 会抛
/// <see cref="System.NotSupportedException"/>。
///
/// 由工程铁律 §4 要求保留所有编码兼容性测试，因此需要保证 provider 被注册。
/// </summary>
internal static class AssemblyInit
{
    [ModuleInitializer]
    public static void RegisterCodePages()
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
    }
}
