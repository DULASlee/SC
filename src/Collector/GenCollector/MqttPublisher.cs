using System;
using System.Text;
using HslCommunication.MQTT;

namespace GenCollector
{
    // MQTT 发布器：复刻原 LnkCollector 的报文契约（HslCommunication.MQTT）
    public class MqttPublisher
    {
        public HslCommunication.MQTT.MqttClient Handle { get; private set; }
        private SettingConfig _setting;

        public bool Init(SettingConfig setting)
        {
            _setting = setting;
            var opt = new MqttConnectionOptions
            {
                CleanSession = true,
                ClientId = "gen_" + Guid.NewGuid().ToString("N").Substring(0, 8),
                Credentials = new MqttCredential("", "")
            };
            var parts = (setting.MqttServer ?? "127.0.0.1:1883").Split(':');
            opt.IpAddress = parts[0];
            opt.Port = parts.Length > 1 && int.TryParse(parts[1], out var p) ? p : 1883;
            Handle = new HslCommunication.MQTT.MqttClient(opt);
            return true;
        }

        public bool Connect()
        {
            if (Handle == null) return false;
            return Handle.ConnectServer().IsSuccess;
        }

        public bool IsConnected => Handle != null && Handle.IsConnected;

        public bool Publish(string topic, string message)
        {
            if (Handle == null || !IsConnected || string.IsNullOrEmpty(topic) || string.IsNullOrEmpty(message))
                return false;
            return Handle.PublishMessage(new MqttApplicationMessage
            {
                Topic = topic,
                QualityOfServiceLevel = MqttQualityOfServiceLevel.AtMostOnce,
                Payload = Encoding.UTF8.GetBytes(message),
                Retain = false
            }).IsSuccess;
        }
    }
}
