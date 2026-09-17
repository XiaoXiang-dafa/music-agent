# -*- coding: utf-8 -*-
"""
音乐域工具 — 搜索 / 播放地址 / 歌词 / 个性化推荐。

统一封装 QQ 音乐与网易云两个音源，对 Agent 暴露一致的接口。
每个函数第一个参数是 AgentContext（见 tools/__init__.py）。
"""
from __future__ import annotations

from typing import Any


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:
        return {"error": str(e)}


def _injected_backend(ctx):
    return (getattr(ctx, "extra", None) or {}).get("music_backend")


def search_songs(ctx, keyword: str, source: str = "qq") -> dict:
    """在曲库搜索歌曲（默认 QQ 音乐，可切网易云）。"""
    if not keyword or not str(keyword).strip():
        return {"error": "关键词为空", "songs": []}

    keyword = str(keyword).strip()
    backend = _injected_backend(ctx)
    if backend is not None:
        raw = _safe(backend.search, keyword, source, 6)
        raw = raw if isinstance(raw, list) else []
    else:
        from modules.qqmusic import search as qq_search
        from modules.netease import search as netease_search

        if source == "netease":
            raw = _safe(netease_search, keyword, 6)
            raw = raw if isinstance(raw, list) else []
        else:
            raw = _safe(qq_search, keyword, 6)
            raw = raw if isinstance(raw, list) else []

    songs = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        songs.append({
            "id": str(r.get("id", "")),
            "name": r.get("name", ""),
            "artist": r.get("artist", ""),
            "cover": r.get("cover", ""),
            "duration": r.get("duration", 0),
            "source": source,
        })
    return {"songs": songs, "count": len(songs), "source": source}


def get_song_url(ctx, song_id: str, source: str = "qq") -> dict:
    """获取某首歌的可播放地址。"""
    if not song_id:
        return {"error": "缺少 song_id", "url": ""}
    backend = _injected_backend(ctx)
    if backend is not None:
        url = backend.song_url(str(song_id), source)
    else:
        from modules.qqmusic import song_url as qq_url
        from modules.netease import song_url as netease_url

        if source == "netease":
            try:
                url = netease_url(int(song_id))
            except Exception:
                url = ""
        else:
            url = qq_url(str(song_id))
    return {"url": url or "", "song_id": str(song_id), "source": source}


def get_lyrics(ctx, song_id: str, source: str = "qq") -> dict:
    """获取歌词。"""
    if not song_id:
        return {"error": "缺少 song_id", "lyric": ""}
    backend = _injected_backend(ctx)
    if backend is not None:
        lrc = backend.lyric(str(song_id), source)
    else:
        from modules.qqmusic import lyric as qq_lyric
        from modules.netease import lyric as netease_lyric

        if source == "netease":
            try:
                lrc = netease_lyric(int(song_id))
            except Exception:
                lrc = ""
        else:
            lrc = qq_lyric(str(song_id))

    # 返回前 1200 字符，避免过长
    if lrc and len(lrc) > 1200:
        lrc = lrc[:1200] + "\n…(截断)"
    return {"lyric": lrc or "", "song_id": str(song_id)}


def get_daily_recommendation(ctx, weather_hint: str = "") -> dict:
    """为用户生成今日个性化歌单（结合天气/时段/品味）。"""
    if ctx.music_rec is None:
        return {"error": "歌单服务不可用", "songs": []}
    try:
        if not weather_hint and ctx.weather_svc is not None:
            from modules.common import weather_hint as _weather_hint
            w = ctx.weather_svc.get_weather()
            if "error" not in w:
                weather_hint = _weather_hint(w)
        taste = ctx.char_mgr.get_music_taste() if ctx.char_mgr else ""
        songs = ctx.music_rec.get_daily_songs(weather_hint, taste)
        return {"songs": songs or [], "weather_hint": weather_hint}
    except Exception as e:
        return {"error": f"推荐失败: {e}", "songs": []}
