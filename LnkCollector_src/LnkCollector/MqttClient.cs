using System;
using System.Text;
using HslCommunication.MQTT;

namespace LnkCollector;

public class MqttClient
{
	public HslCommunication.MQTT.MqttClient handle;

	public DateTime lastConnectTime;

	public string clientId;

	public int clientPort;

	public bool Init()
	{
		MqttConnectionOptions mqttConnectionOptions = new MqttConnectionOptions();
		mqttConnectionOptions.CleanSession = true;
		mqttConnectionOptions.IpAddress = "192.168.0.87";
		mqttConnectionOptions.Port = 1883;
		mqttConnectionOptions.ClientId = "lnk";
		mqttConnectionOptions.Credentials = new MqttCredential("", "");
		handle = new HslCommunication.MQTT.MqttClient(mqttConnectionOptions);
		handle.OnClientConnected += onClientConnected;
		return true;
	}

	public bool ConnectServer()
	{
		if (handle == null)
		{
			return false;
		}
		Console.WriteLine("连接MQTT服务端成功");
		return handle.ConnectServer().IsSuccess;
	}

	public void DisConnectServer()
	{
		Console.WriteLine("断开MQTT服务端成功");
		handle.ConnectClose();
	}

	public bool IsConnected()
	{
		return handle.IsConnected;
	}

	private void onClientConnected(HslCommunication.MQTT.MqttClient client)
	{
		clientId = client.ConnectionOptions.IpAddress;
		clientPort = client.ConnectionOptions.Port;
		Console.WriteLine("连接MQTT服务端 ( " + client.ConnectionOptions.IpAddress + ":" + client.ConnectionOptions.Port + " ) 成功");
	}

	public bool SubscribeTopic(string topic)
	{
		if (topic == null || topic == "")
		{
			return false;
		}
		return handle.SubscribeMessage(topic).IsSuccess;
	}

	public bool PublishMessage(string topic, string message)
	{
		if (topic == null || topic == "" || message == null || message == "")
		{
			return false;
		}
		return handle.PublishMessage(new MqttApplicationMessage
		{
			Topic = topic,
			QualityOfServiceLevel = MqttQualityOfServiceLevel.AtMostOnce,
			Payload = Encoding.UTF8.GetBytes(message),
			Retain = false
		}).IsSuccess;
	}
}
