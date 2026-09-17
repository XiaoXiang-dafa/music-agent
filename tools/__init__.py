# -*- coding: utf-8 -*-
"""
工具装配 — 把音乐域工具注册到一个 ToolRegistry，供 Agent 调用。

每个 Agent 请求会构建一个 AgentContext（绑定当前用户/会话的记忆与全局服务），
再据此生成专属的注册表。新工具只需实现一个函数并在 build_registry 里登记即可热插拔。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent import ToolRegistry

from .music import search_songs, get_song_url, get_lyrics, get_daily_recommendation
from .weather import get_weather
from .playback import play_song
from .memory import UserMemory, get_user_profile, save_favorite, remember_taste


@dataclass
class AgentContext:
    """一次 Agent 请求的上下文。"""
    client: Any
    model: str
    memory: UserMemory
    session_id: str
    weather_svc: Any = None
    music_rec: Any = None
    char_mgr: Any = None
    extra: dict = field(default_factory=dict)


# ---- 各工具的 Function Calling schema（parameters） ----

def _p(props, required):
    return {"type": "object", "properties": props, "required": required}

_SCHEMAS = {
    "search_songs": _p(
        {
            "keyword": {"type": "string", "description": "要搜索的歌名或歌手关键词"},
            "source": {"type": "string", "enum": ["qq", "netease"], "description": "音源，默认 qq"},
        },
        ["keyword"],
    ),
    "get_song_url": _p(
        {"song_id": {"type": "string", "description": "歌曲 ID（来自 search 结果）"},
         "source": {"type": "string", "enum": ["qq", "netease"], "description": "音源"}},
        ["song_id"],
    ),
    "get_lyrics": _p(
        {"song_id": {"type": "string", "description": "歌曲 ID"},
         "source": {"type": "string", "enum": ["qq", "netease"]}},
        ["song_id"],
    ),
    "get_daily_recommendation": _p(
        {"weather_hint": {"type": "string", "description": "天气梗概，可选"}}, [],
    ),
    "get_weather": _p({}, []),
    "play_song": _p(
        {"song_name": {"type": "string", "description": "用户想听的歌名"},
         "artist": {"type": "string", "description": "歌手名，可选"}},
        ["song_name"],
    ),
    "save_favorite": _p(
        {"song": {"type": "string", "description": "歌名"}, "artist": {"type": "string", "description": "歌手"}},
        ["song"],
    ),
    "remember_taste": _p(
        {"taste": {"type": "string", "description": "用户的音乐偏好描述"}}, ["taste"],
    ),
    "get_user_profile": _p({}, []),
}

_DESCRIPTIONS = {
    "search_songs": "在 QQ 音乐或网易云曲库搜索歌曲，返回歌曲 ID/歌名/歌手/封面。找到歌曲后可用 play_song 播放。",
    "get_song_url": "根据 song_id 获取某首歌的可播放地址。",
    "get_lyrics": "根据 song_id 获取某首歌的歌词。",
    "get_daily_recommendation": "结合天气/时段/用户口味生成今日个性化歌单。",
    "get_weather": "查询当前天气，用于场景化推荐。",
    "play_song": "用户想听某首时触发真实播放，返回可播放的歌曲信息与地址。",
    "save_favorite": "用户喜欢/想收藏某首歌时调用，保存到长期记忆。",
    "remember_taste": "记住用户的音乐偏好，用于个性化推荐。",
    "get_user_profile": "查看已保存的用户偏好/收藏/口味。",
}


def context_from(**kwargs) -> AgentContext:
    return AgentContext(**kwargs)


def build_registry(ctx: AgentContext) -> ToolRegistry:
    """根据上下文组装一个可用的工具注册表。"""
    reg = ToolRegistry()
    reg.register("search_songs", {"function": {"parameters": _SCHEMAS["search_songs"]}},
                 lambda **kw: search_songs(ctx, **kw), _DESCRIPTIONS["search_songs"])
    reg.register("get_song_url", {"function": {"parameters": _SCHEMAS["get_song_url"]}},
                 lambda **kw: get_song_url(ctx, **kw), _DESCRIPTIONS["get_song_url"])
    reg.register("get_lyrics", {"function": {"parameters": _SCHEMAS["get_lyrics"]}},
                 lambda **kw: get_lyrics(ctx, **kw), _DESCRIPTIONS["get_lyrics"])
    reg.register("get_daily_recommendation", {"function": {"parameters": _SCHEMAS["get_daily_recommendation"]}},
                 lambda **kw: get_daily_recommendation(ctx, **kw), _DESCRIPTIONS["get_daily_recommendation"])
    reg.register("get_weather", {"function": {"parameters": _SCHEMAS["get_weather"]}},
                 lambda **kw: get_weather(ctx, **kw), _DESCRIPTIONS["get_weather"])
    reg.register("play_song", {"function": {"parameters": _SCHEMAS["play_song"]}},
                 lambda **kw: play_song(ctx, **kw), _DESCRIPTIONS["play_song"])
    reg.register("save_favorite", {"function": {"parameters": _SCHEMAS["save_favorite"]}},
                 lambda **kw: save_favorite(ctx, **kw), _DESCRIPTIONS["save_favorite"])
    reg.register("remember_taste", {"function": {"parameters": _SCHEMAS["remember_taste"]}},
                 lambda **kw: remember_taste(ctx, **kw), _DESCRIPTIONS["remember_taste"])
    reg.register("get_user_profile", {"function": {"parameters": _SCHEMAS["get_user_profile"]}},
                 lambda **kw: get_user_profile(ctx, **kw), _DESCRIPTIONS["get_user_profile"])
    return reg


_ = context_from  # 供外部构造 AgentContext 使用
