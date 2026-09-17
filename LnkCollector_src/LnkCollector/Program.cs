using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using Newtonsoft.Json;

namespace LnkCollector;

internal class Program
{
	[DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
	public static extern int remote_new_connect(string IP);

	[DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
	public static extern int remote_read_macro_p(int nHandle, int nMacro, double[] val);

	[DllImport("RemoteComm.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
	public static extern int remote_read_plc_variable_p_2(int nHandle, string PLCAdress, int type, long[] val);

	private static void Main(string[] args)
	{
		MqttClient mqttClient = new MqttClient();
		mqttClient.Init();
		mqttClient.ConnectServer();
		DateTime dateTime = DateTime.MinValue;
		int num = remote_new_connect("192.168.3.14");
		while (true)
		{
			if ((dateTime == DateTime.MinValue || (DateTime.Now - dateTime).TotalMilliseconds >= 15000.0) && !mqttClient.handle.IsConnected)
			{
				Console.WriteLine("MQTT 未连接，尝试初始化并重连...");
				if (!mqttClient.Init())
				{
					Console.WriteLine("MQTT 客户端初始化失败");
				}
				else
				{
					Console.WriteLine("MQTT 客户端初始化成功");
					dateTime = DateTime.Now;
					if (mqttClient.ConnectServer())
					{
						Console.WriteLine($"MQTT 客户端连接 MQTT 服务端 ( {mqttClient.clientId}:{mqttClient.clientPort} ) 成功");
					}
					else
					{
						Console.WriteLine("MQTT 重连失败，等待5秒...");
					}
				}
			}
			try
			{
				if (num >= 0)
				{
					List<object> list = new List<object>();
					long timeStamp = (long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalMilliseconds;
					double[] array = new double[1];
					remote_read_macro_p(num, 33868, array);
					list.Add(new
					{
						MeasEncoding = "WorkTime",
						MeasName = "系统加工时间",
						value = array,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("系统加工时间:" + array);
					Thread.Sleep(1000);
					double[] array2 = new double[1];
					remote_read_macro_p(num, 2097, array2);
					list.Add(new
					{
						MeasEncoding = "RunTime",
						MeasName = "系统运行时间",
						value = array2,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("系统运行时间:" + array2);
					Thread.Sleep(1000);
					double[] array3 = new double[1];
					remote_read_macro_p(num, 33565, array3);
					list.Add(new
					{
						MeasEncoding = "CutTime",
						MeasName = "切削时间",
						value = array3,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("切削时间:" + array3);
					Thread.Sleep(1000);
					double[] array4 = new double[1];
					remote_read_macro_p(num, 33869, array4);
					list.Add(new
					{
						MeasEncoding = "Products",
						MeasName = "加工零件数",
						value = array4,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("加工零件数:" + array4);
					Thread.Sleep(1000);
					long[] array5 = new long[1];
					int num2 = remote_read_plc_variable_p_2(num, "42.0", 1, array5);
					list.Add(new
					{
						MeasEncoding = "RunStatus",
						MeasName = "运行中状态",
						value = array5,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("运行中状态result:" + num2);
					Console.WriteLine("运行中状态:" + array5);
					Thread.Sleep(1000);
					long[] array6 = new long[1];
					remote_read_plc_variable_p_2(num, "42.1", 1, array6);
					list.Add(new
					{
						MeasEncoding = "StopStatus",
						MeasName = "暂停中状态",
						value = array6,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("暂停中状态:" + array6);
					Thread.Sleep(1000);
					long[] array7 = new long[1];
					remote_read_plc_variable_p_2(num, "50.14", 1, array7);
					list.Add(new
					{
						MeasEncoding = "WarnStatus",
						MeasName = "系统告警状态",
						value = array7,
						TimeStamp = timeStamp,
						DeviceEncoding = "CNC04"
					});
					Console.WriteLine("系统告警状态:" + array7);
					Thread.Sleep(1000);
					var value = new
					{
						properties = list
					};
					string text = JsonConvert.SerializeObject(value);
					Console.WriteLine("发布的 JSON 数据: ");
					Console.WriteLine(text);
					mqttClient.PublishMessage("realtime/CNC04", text);
				}
				else
				{
					num = remote_new_connect("192.168.3.14");
				}
				Thread.Sleep(1000);
			}
			catch (Exception ex)
			{
				Console.WriteLine(ex?.ToString() ?? "");
				Thread.Sleep(1000);
			}
		}
	}
}
