# plugins/weather.py
import requests
import urllib.parse
from plugins.base import BasePlugin

def get_weather(city):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=zh&format=json"
        geo_resp = requests.get(geo_url, timeout=8).json()
        if not geo_resp.get("results"):
            return f"未找到城市：{city}"
        loc = geo_resp["results"][0]
        lat, lon, city_name = loc["latitude"], loc["longitude"], loc["name"]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
        weather = requests.get(weather_url, timeout=8).json()
        if "current_weather" not in weather:
            return "天气数据获取失败"
        cw = weather["current_weather"]
        code_map = {0:"晴朗",1:"基本晴朗",2:"部分多云",3:"多云",45:"雾",48:"雾",51:"小雨",53:"中雨",55:"大雨",61:"小雨",63:"中雨",65:"大雨",71:"小雪",73:"中雪",75:"大雪",80:"小雨",81:"中雨",82:"大雨",95:"雷雨",96:"雷雨",99:"雷雨"}
        weather_text = code_map.get(cw["weathercode"], "未知")
        return f"地点：{city_name}\n温度：{cw['temperature']}°C\n风速：{cw['windspeed']} km/h\n天气：{weather_text}"
    except:
        return "天气服务暂时不可用"

class WeatherPlugin(BasePlugin):
    name = "weather"
    priority = 40

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith("天气")

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        city = clean_message[2:].strip()
        if not city:
            self.bot.send_reply(msg_type, group_id, user_qq, "请指定城市，例如：天气 北京", at_user=(msg_type=='group'))
            return True
        result = get_weather(city)
        self.bot.send_reply(msg_type, group_id, user_qq, result, at_user=(msg_type=='group'))
        return True