# -*- coding: utf-8 -*-
"""
天气查询模块 - 华风爱科 (AccuWeather 中国)
免费额度: 500次/天, 5 QPS
注册: https://platform.weathercn.com/
"""
import requests


class WeatherService:
    """华风爱科天气查询"""

    BASE_URL = "https://openapi.weathercn.com"
    LOCATION_URL = f"{BASE_URL}/locations/v1/cities/translate"
    GEOPOS_URL = f"{BASE_URL}/locations/v1/cities/geoposition/search"
    CURRENT_URL = f"{BASE_URL}/currentconditions/v1"
    FORECAST_URL = f"{BASE_URL}/forecasts/v1/daily/5day"

    def __init__(self, api_key: str, city: str = "auto"):
        self.api_key = api_key
        self.city = city

    def _get_location_key(self, city: str) -> tuple[str | None, str | None]:
        """城市名 → location key + 城市名"""
        params = {"q": city, "apikey": self.api_key, "language": "zh-cn"}
        try:
            resp = requests.get(self.LOCATION_URL, params=params, timeout=10)
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]["Key"], data[0].get("LocalizedName", city)
            elif isinstance(data, dict) and "Key" in data:
                return data["Key"], data.get("LocalizedName", city)
        except Exception as e:
            print(f"[Weather] 城市查询失败: {e}")
        return None, None

    def _auto_locate(self) -> tuple[str | None, str | None]:
        """IP 自动定位 → location key + 城市名"""
        try:
            # 用免费 IP 服务获取城市
            ip_resp = requests.get("https://ip-api.com/json/?lang=zh-CN", timeout=5)
            ip_data = ip_resp.json()
            if ip_data.get("city"):
                city = ip_data["city"]
                print(f"[Weather] IP定位: {city}")
                return self._get_location_key(city)
            # fallback: 用经纬度
            lat, lon = ip_data.get("lat"), ip_data.get("lon")
            if lat and lon:
                params = {"q": f"{lat},{lon}", "apikey": self.api_key, "language": "zh-cn"}
                resp = requests.get(self.GEOPOS_URL, params=params, timeout=10)
                data = resp.json()
                if isinstance(data, dict) and "Key" in data:
                    return data["Key"], data.get("LocalizedName", "当前城市")
        except Exception as e:
            print(f"[Weather] 自动定位失败: {e}")
        return None, None

    def get_weather(self, city: str | None = None) -> dict:
        """
        获取天气预报, 返回:
        {"city": "深圳", "today": {...}, "tomorrow": {...}, "day_after": {...}}
        或 {"error": "..."}
        """
        target = city or self.city

        if target == "auto":
            loc_key, city_name = self._auto_locate()
        else:
            loc_key, city_name = self._get_location_key(target)

        if not loc_key:
            return {"error": f"找不到城市: {target}"}

        params = {
            "apikey": self.api_key,
            "language": "zh-cn",
            "details": "true",
            "metric": "true",
        }

        try:
            # 获取 5 天预报
            url = f"{self.FORECAST_URL}/{loc_key}.json"
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if "DailyForecasts" not in data:
                return {"error": f"预报查询失败"}

            daily = data["DailyForecasts"]
            if len(daily) < 3:
                return {"error": "预报数据不足"}

            return {
                "city": city_name or target,
                "today": self._format_day(daily[0]),
                "tomorrow": self._format_day(daily[1]),
                "day_after": self._format_day(daily[2]),
            }
        except Exception as e:
            return {"error": str(e)}

    def _format_day(self, day: dict) -> dict:
        """格式化单天预报"""
        temp = day.get("Temperature", {})
        day_part = day.get("Day", {})
        night_part = day.get("Night", {})

        def _temp(val):
            """温度去 .0"""
            try:
                v = float(val)
                return str(int(v)) if v == int(v) else f"{v:.1f}"
            except (ValueError, TypeError):
                return str(val)

        return {
            "date": day.get("Date", "")[:10],
            "temp_max": _temp(temp.get("Maximum", {}).get("Value", "?")),
            "temp_min": _temp(temp.get("Minimum", {}).get("Value", "?")),
            "text_day": day_part.get("IconPhrase", "未知"),
            "text_night": night_part.get("IconPhrase", "未知"),
            "wind_day": self._format_wind(day_part.get("Wind", {})),
            "wind_night": self._format_wind(night_part.get("Wind", {})),
            "rain_prob": f"{day_part.get('RainProbability', 0)}%",
        }

    def _format_wind(self, wind: dict) -> str:
        """格式化风力"""
        if not wind:
            return "微风"
        direction = wind.get("Direction", {}).get("Localized", "")
        speed = wind.get("Speed", {}).get("Value", 0)
        unit = wind.get("Speed", {}).get("Unit", "km/h")
        if direction and direction != "无":
            return f"{direction}风 {speed}{unit}"
        return f"{speed}{unit}" if speed > 0 else "微风"

    def format_weather_message(self, weather_data: dict, greeting: str = "早安") -> str:
        """把天气数据格式化成早安消息（无emoji 无标点）"""
        if "error" in weather_data:
            return f"{greeting} 天气暂时查不到啦"

        w = weather_data
        today = w["today"]
        tomorrow = w["tomorrow"]

        tips = self._weather_tips(today)
        rain = f" 降雨概率 {today['rain_prob']}" if today['rain_prob'] != "0%" else ""

        return (
            f"{greeting} {w['city']}今天 {today['text_day']}\n"
            f"温度 {today['temp_min']}-{today['temp_max']}度  {today['wind_day']}{rain}\n"
            f"{tips}\n"
            f"明天 {tomorrow['text_day']} {tomorrow['temp_min']}~{tomorrow['temp_max']}度"
        )

    def _weather_tips(self, today: dict) -> str:
        """天气小贴士"""
        tips = []
        try:
            tmax = int(float(today["temp_max"]))
            tmin = int(float(today["temp_min"]))
        except (ValueError, KeyError):
            return "今天也要开心喔"

        if tmax >= 35:
            tips.append("注意防暑降温")
        elif tmax <= 10:
            tips.append("注意保暖")
        elif tmax - tmin >= 12:
            tips.append("早晚温差大 带件外套")

        text = today.get("text_day", "")
        if "雨" in text:
            tips.append("有雨 出门带伞")
        elif "雪" in text:
            tips.append("下雪 走路小心")

        if not tips:
            tips.append("天气不错 适合出门走走")

        return "  ".join(tips)
