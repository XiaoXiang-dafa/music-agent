# -*- coding: utf-8 -*-
"""
天气工具 — 供 Agent 在场景化推荐前查询天气。
"""
from __future__ import annotations


def get_weather(ctx) -> dict:
    """查询当前城市天气。"""
    if ctx.weather_svc is None:
        return {"error": "天气服务未配置", "city": "", "text": "", "temp": ""}
    try:
        from modules.common import weather_hint
        w = ctx.weather_svc.get_weather()
        if "error" in w:
            return {"error": w["error"], "city": "", "text": "", "temp": ""}
        text = weather_hint(w)
        # 拆分出一个更友好的描述
        city = w.get("city", "")
        today = w.get("today", {})
        return {
            "city": city,
            "text": today.get("text_day", ""),
            "temp": f"{today.get('temp_min', '?')}-{today.get('temp_max', '?')}度",
            "hint": text,
        }
    except Exception as e:
        return {"error": str(e), "city": "", "text": "", "temp": ""}
