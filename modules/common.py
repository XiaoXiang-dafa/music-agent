# -*- coding: utf-8 -*-
"""
公共工具模块 — 消除 app.py / bot.py / cli.py 之间的重复代码
"""
import os
from datetime import datetime

_PLACEHOLDER_API_KEY = "请设置环境变量 DEEPSEEK_API_KEY"
_SECRET_PLACEHOLDERS = {
    "MISSING_API_KEY",
    "你的DeepSeek_API_KEY",
    "你的和风天气API_KEY",
    "请设置环境变量 DEEPSEEK_API_KEY",
    "请设置环境变量 WEATHER_API_KEY",
    "请设置环境变量 QQMUSIC_COOKIE",
}


def resolve_api_keys(config: dict) -> None:
    """环境变量覆盖 config 中的敏感值（原地修改）"""
    if os.environ.get("DEEPSEEK_API_KEY"):
        config["deepseek"]["api_key"] = os.environ["DEEPSEEK_API_KEY"]
    if os.environ.get("WEATHER_API_KEY"):
        config["weather"]["api_key"] = os.environ["WEATHER_API_KEY"]
    if os.environ.get("QQMUSIC_COOKIE"):
        config.setdefault("qqmusic", {})["cookie"] = os.environ["QQMUSIC_COOKIE"]


def require_deepseek_api_key(config: dict) -> str:
    """返回已解析的 DeepSeek key；缺失时以可操作错误终止启动。"""
    key = (config.get("deepseek") or {}).get("api_key", "")
    if not is_configured_secret(key):
        raise RuntimeError("缺少 DeepSeek API Key，请设置环境变量 DEEPSEEK_API_KEY")
    return key


def is_configured_secret(value: str | None) -> bool:
    """占位符与空值不算有效凭据。"""
    return bool(value and value not in _SECRET_PLACEHOLDERS)


def is_demo_mode() -> bool:
    """是否启用不访问外部服务的本地演示模式。"""
    return os.environ.get("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def morning_greeting() -> str:
    """根据当前时间返回早安问候语"""
    hour = datetime.now().hour
    if hour < 8:
        return "早安 今天起得真早"
    elif hour > 10:
        return "早啊 虽然有点晚了哈哈"
    return "早安"


def weather_hint(weather_data: dict) -> str:
    """从天气数据生成简短提示文本"""
    if not weather_data or "error" in weather_data:
        return ""
    today = weather_data.get("today", {})
    return (
        f"{weather_data.get('city', '')} "
        f"{today.get('text_day', '')} "
        f"{today.get('temp_min', '?')}-{today.get('temp_max', '?')}度"
    )


def build_morning_message(weather_svc, greeting: str = "") -> tuple[str, str]:
    """
    组装早安消息。返回 (消息文本, weather_hint)。

    只调一次天气 API，同时返回 weather_hint 供歌单复用。
    """
    if not greeting:
        greeting = morning_greeting()

    weather_part = ""
    hint = ""
    if weather_svc:
        w = weather_svc.get_weather()
        if "error" not in w:
            try:
                weather_part = weather_svc.format_weather_message(w, greeting)
            except Exception:
                weather_part = f"{greeting} 天气暂时查不到啦"
            hint = weather_hint(w)

    if not weather_part:
        weather_part = f"{greeting} 新的一天开心喔"

    return weather_part, hint
